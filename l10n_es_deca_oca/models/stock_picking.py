# Copyright 2026 Abraham Anes - abraham@tesseratech.es
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import re
from datetime import timedelta

from werkzeug.urls import url_quote_plus

from odoo import _, api, fields, models
from odoo.exceptions import UserError

DECA_TRACKED_FIELDS = (
    "deca_carrier_partner_id",
    "deca_driver_name",
    "deca_vehicle_plate",
    "deca_trailer_plate",
    "deca_special_authorization",
    "deca_notes",
    "deca_goods_description",
    "deca_gross_weight",
)
DECA_PLATE_FIELDS = ("deca_vehicle_plate", "deca_trailer_plate")


class StockPicking(models.Model):
    _inherit = "stock.picking"

    deca_required = fields.Boolean(
        string="DeCA required",
        compute="_compute_deca_required",
        store=True,
        readonly=False,
        copy=False,
        help="Whether this delivery needs an electronic administrative control "
        "document (DeCA). Proposed from the operation type.",
    )
    deca_carrier_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Effective carrier",
        compute="_compute_deca_carrier_partner_id",
        store=True,
        readonly=False,
        copy=False,
        help="Holder of the transport authorisation that actually carries the "
        "goods. Proposed from the transporter of the shipping method.",
    )
    deca_driver_name = fields.Char(string="Driver", copy=False)
    deca_vehicle_plate = fields.Char(string="Vehicle plate", size=16, copy=False)
    deca_trailer_plate = fields.Char(
        string="Trailer plate",
        size=16,
        copy=False,
        help="Plate of the trailer or semi-trailer, if any.",
    )
    deca_special_authorization = fields.Text(
        string="Special traffic authorisation",
        copy=False,
        help="Special traffic authorisation required by the vehicle, if any.",
    )
    deca_notes = fields.Text(string="DeCA observations", copy=False)
    deca_gross_weight = fields.Float(
        string="Gross weight (kg)",
        digits="Stock Weight",
        copy=False,
        help="Gross weight printed on the DeCA. If empty, the weight for "
        "shipping of the transfer is used, which Odoo recomputes from the "
        "validated quantities and packages.",
    )
    deca_goods_description = fields.Text(
        string="Nature of the goods",
        default=lambda self: self.env.company.deca_goods_description,
        copy=False,
        help="Printed on the DeCA. Proposed from the company settings; if empty, "
        "the names of the products are used.",
    )
    deca_access_token = fields.Char(
        string="DeCA access token", copy=False, readonly=True, index=True
    )
    deca_document_ids = fields.One2many(
        comodel_name="l10n_es.deca.document",
        inverse_name="picking_id",
        string="DeCA versions",
        readonly=True,
        copy=False,
    )
    deca_document_count = fields.Integer(compute="_compute_deca_current_document_id")
    deca_current_document_id = fields.Many2one(
        comodel_name="l10n_es.deca.document",
        string="Current DeCA version",
        compute="_compute_deca_current_document_id",
    )
    deca_state = fields.Selection(
        selection=[("none", "Not issued"), ("issued", "Issued")],
        string="DeCA status",
        compute="_compute_deca_state",
        store=True,
    )
    deca_url = fields.Char(string="DeCA download URL", compute="_compute_deca_url")

    _sql_constraints = [
        (
            "deca_access_token_unique",
            "UNIQUE(deca_access_token)",
            "The DeCA access token must be unique.",
        )
    ]

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends("picking_type_id.deca_required")
    def _compute_deca_required(self):
        for picking in self:
            picking.deca_required = picking.picking_type_id.deca_required

    @api.depends("carrier_id.partner_id")
    def _compute_deca_carrier_partner_id(self):
        for picking in self:
            picking.deca_carrier_partner_id = (
                picking.carrier_id.partner_id or picking.deca_carrier_partner_id
            )

    @api.depends("deca_document_ids")
    def _compute_deca_current_document_id(self):
        for picking in self:
            documents = picking.deca_document_ids.sorted(
                lambda doc: (doc.version, doc.id), reverse=True
            )
            picking.deca_current_document_id = fields.first(documents)
            picking.deca_document_count = len(documents)

    @api.depends("deca_document_ids")
    def _compute_deca_state(self):
        for picking in self:
            picking.deca_state = "issued" if picking.deca_document_ids else "none"

    @api.depends("deca_access_token")
    def _compute_deca_url(self):
        for picking in self:
            picking.deca_url = (
                f"{picking.get_base_url()}/deca/{picking.deca_access_token}"
                if picking.deca_access_token
                else False
            )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model
    def _deca_normalize_plate(self, plate):
        return re.sub(r"[\s\-]+", "", plate).upper() if plate else plate

    def _deca_normalize_vals(self, vals):
        for field_name in DECA_PLATE_FIELDS:
            if vals.get(field_name):
                vals[field_name] = self._deca_normalize_plate(vals[field_name])
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._deca_normalize_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._deca_normalize_vals(vals)
        res = super().write(vals)
        if any(field_name in vals for field_name in DECA_TRACKED_FIELDS):
            # Changing the data of an issued DeCA (e.g. a new plate during the
            # service) must leave a trace: issue a new version with its reason,
            # given by the update wizard through the context.
            self.filtered("deca_document_ids")._deca_create_version(
                self.env.context.get("deca_change_reason")
            )
        return res

    def _action_done(self):
        res = super()._action_done()
        pickings = self.filtered(
            lambda p: p.state == "done" and p.picking_type_code == "outgoing"
        )
        issued = pickings.filtered("deca_document_ids")
        # Validated quantities may change the weight: refresh the version.
        issued._deca_create_version(_("Delivery validated"))
        (pickings - issued).filtered(
            lambda p: p.deca_required and p.company_id.deca_auto_issue
        ).action_deca_issue()
        return res

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_deca_issue(self):
        """Issue the DeCA (or a new version of it) for these deliveries."""
        pickings = self.filtered(
            lambda p: p.picking_type_code == "outgoing"
            and p.state not in ("draft", "cancel")
        )
        pickings._deca_check_required_data()
        pickings._deca_ensure_access_token()
        pickings._deca_create_version()
        return True

    def action_deca_view_documents(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "l10n_es_deca_oca.action_l10n_es_deca_document"
        )
        action["domain"] = [("picking_id", "=", self.id)]
        action["context"] = {"search_default_picking_id": self.id}
        return action

    # ------------------------------------------------------------------
    # Business helpers (meant to be extended)
    # ------------------------------------------------------------------
    def _deca_get_origin_partner(self):
        """Partner whose address is printed as place of origin."""
        self.ensure_one()
        return (
            self.picking_type_id.warehouse_id.partner_id or self.company_id.partner_id
        )

    def _deca_get_gross_weight(self):
        """Gross weight of the goods in kilograms."""
        self.ensure_one()
        if self.deca_gross_weight:
            return self.deca_gross_weight
        weight = self.shipping_weight or self.weight
        weight_uom = self.env[
            "product.template"
        ]._get_weight_uom_id_from_ir_config_parameter()
        kg_uom = self.env.ref("uom.product_uom_kgm")
        if weight and weight_uom != kg_uom:
            weight = weight_uom._compute_quantity(weight, kg_uom)
        return weight

    def _deca_get_missing_data(self):
        """Labels of the mandatory DeCA data (art. 6 Orden FOM/2861/2012)
        that are missing on this delivery."""
        self.ensure_one()
        missing = []
        shipper = self.company_id.partner_id
        if not shipper.vat:
            missing.append(_("Company VAT"))
        if not (shipper.street and shipper.city):
            missing.append(_("Company address"))
        if not self.deca_carrier_partner_id:
            missing.append(_("Effective carrier"))
        elif not self.deca_carrier_partner_id.vat:
            missing.append(_("Effective carrier VAT"))
        if not self.deca_vehicle_plate:
            missing.append(_("Vehicle plate"))
        if self._deca_get_gross_weight() <= 0:
            missing.append(_("Gross weight"))
        if not self._deca_get_origin_partner():
            missing.append(_("Origin address"))
        if not self.partner_id:
            missing.append(_("Delivery address"))
        return missing

    def _deca_check_required_data(self):
        errors = []
        for picking in self:
            missing = picking._deca_get_missing_data()
            if missing:
                errors.append(
                    _(
                        "%(picking)s: %(fields)s",
                        picking=picking.name,
                        fields=", ".join(missing),
                    )
                )
        if errors:
            raise UserError(
                _("The DeCA cannot be issued, the following data is missing:\n%s")
                % "\n".join(errors)
            )

    def _deca_ensure_access_token(self):
        for picking in self.filtered(lambda p: not p.deca_access_token):
            picking.deca_access_token = self.env[
                "ir.attachment"
            ]._generate_access_token()

    @api.model
    def _deca_format_address(self, partner, with_name=False):
        """Address of ``partner`` as printed on the DeCA, one line per element
        and without the blank lines left by empty address fields."""
        if not partner:
            return False
        lines = [partner.name] if with_name else []
        lines += partner._display_address(without_company=True).splitlines()
        return "\n".join(line.strip() for line in lines if line and line.strip())

    def _deca_prepare_version_values(self):
        """Snapshot of the data printed on the DeCA."""
        self.ensure_one()
        shipper = self.company_id.partner_id
        carrier = self.deca_carrier_partner_id
        origin = self._deca_get_origin_partner()
        destination = self.partner_id
        return {
            "picking_id": self.id,
            "shipper_name": shipper.name,
            "shipper_vat": shipper.vat,
            "shipper_address": self._deca_format_address(shipper),
            "carrier_name": carrier.name,
            "carrier_vat": carrier.vat,
            "carrier_address": self._deca_format_address(carrier),
            "driver_name": self.deca_driver_name,
            "vehicle_plate": self.deca_vehicle_plate,
            "trailer_plate": self.deca_trailer_plate,
            "origin_address": self._deca_format_address(origin, with_name=True),
            "destination_name": destination.display_name,
            "destination_address": self._deca_format_address(destination),
            "transport_date": fields.Date.context_today(self, self.scheduled_date),
            "gross_weight": self._deca_get_gross_weight(),
            "goods_description": self.deca_goods_description
            or self.company_id.deca_goods_description
            or ", ".join(dict.fromkeys(self.move_ids.product_id.mapped("name"))),
            "special_authorization": self.deca_special_authorization,
            "notes": self.deca_notes,
        }

    def _deca_create_version(self, reason=None):
        """Issue a new DeCA version, with its PDF file, for each delivery whose
        printed data changed since its current version. A reason is required
        to modify an issued DeCA. Returns the versions created."""
        Document = self.env["l10n_es.deca.document"]
        created = Document
        for picking in self:
            values = picking._deca_prepare_version_values()
            current = picking.deca_current_document_id
            if current and current._snapshot_equals(values):
                if not current.attachment_id:
                    # File lost (e.g. data issued before an upgrade): restore it
                    current._generate_attachment()
                continue
            if current and not reason:
                raise UserError(
                    _(
                        "%(picking)s: the DeCA is already issued, use the update "
                        "wizard to state the reason of the change.",
                        picking=picking.name,
                    )
                )
            values["version"] = current.version + 1 if current else 1
            values["change_reason"] = reason if current else False
            document = Document.create(values)
            document._generate_attachment()
            created |= document
        return created

    def _deca_download_allowed(self):
        """Whether the public download of the DeCA is still allowed."""
        self.ensure_one()
        days = self.company_id.deca_download_expiry_days
        if not days or self.state != "done" or not self.date_done:
            return True
        return fields.Datetime.now() <= self.date_done + timedelta(days=days)

    def _deca_get_qr_src(self, size=160):
        self.ensure_one()
        value = url_quote_plus(self.deca_url or "")
        return (
            f"/report/barcode/?barcode_type=QR&value={value}&width={size}&height={size}"
        )
