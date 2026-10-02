# Copyright 2026 Abraham Anes - abraham@tesseratech.es
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import io

from odoo import api, fields, models
from odoo.tools import float_compare, format_date, formatLang
from odoo.tools.pdf import PdfFileReader, PdfFileWriter

HISTORY_FIELDS = (
    "carrier_name",
    "carrier_vat",
    "driver_name",
    "vehicle_plate",
    "trailer_plate",
    "transport_date",
    "gross_weight",
    "goods_description",
    "special_authorization",
    "notes",
)


class L10nEsDecaDocument(models.Model):
    _name = "l10n_es.deca.document"
    _description = "DeCA version"
    _order = "picking_id, version desc, id desc"

    picking_id = fields.Many2one(
        comodel_name="stock.picking",
        required=True,
        ondelete="cascade",
        index=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="picking_id.company_id", store=True, index=True
    )
    version = fields.Integer(required=True, readonly=True)
    date = fields.Datetime(
        string="Issue date",
        required=True,
        readonly=True,
        default=fields.Datetime.now,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Issued by",
        readonly=True,
        default=lambda self: self.env.user,
    )
    attachment_id = fields.Many2one(
        comodel_name="ir.attachment",
        string="PDF file",
        readonly=True,
        ondelete="restrict",
        help="File issued for this version. It must be kept for at least one "
        "year and cannot be deleted while the version exists.",
    )
    change_reason = fields.Text(
        readonly=True, help="Reason of the change with respect to the previous version."
    )
    # Contractual shipper (art. 6.a)
    shipper_name = fields.Char(readonly=True)
    shipper_vat = fields.Char(readonly=True)
    shipper_address = fields.Text(readonly=True)
    # Effective carrier (art. 6.b)
    carrier_name = fields.Char(readonly=True)
    carrier_vat = fields.Char(readonly=True)
    carrier_address = fields.Text(readonly=True)
    driver_name = fields.Char(readonly=True)
    # Vehicle (art. 6.g)
    vehicle_plate = fields.Char(readonly=True)
    trailer_plate = fields.Char(readonly=True)
    # Origin and destination (art. 6.c)
    origin_address = fields.Text(readonly=True)
    destination_name = fields.Char(readonly=True)
    destination_address = fields.Text(readonly=True)
    # Goods (art. 6.d) and date (art. 6.f)
    transport_date = fields.Date(readonly=True)
    gross_weight = fields.Float(
        string="Gross weight (kg)", digits="Stock Weight", readonly=True
    )
    goods_description = fields.Text(readonly=True)
    # Special authorisation (art. 6.e) and observations (art. 6.h)
    special_authorization = fields.Text(readonly=True)
    notes = fields.Text(readonly=True)
    is_current = fields.Boolean(compute="_compute_is_current")

    _sql_constraints = [
        (
            "picking_version_unique",
            "UNIQUE(picking_id, version)",
            "A DeCA version number can only be used once per transfer.",
        )
    ]

    @api.depends("picking_id.name", "version")
    def _compute_display_name(self):
        for doc in self:
            doc.display_name = f"DeCA {doc.picking_id.name} v{doc.version}"

    @api.depends("picking_id.deca_current_document_id")
    def _compute_is_current(self):
        for doc in self:
            doc.is_current = doc.picking_id.deca_current_document_id == doc

    @api.model
    def _get_snapshot_fields(self):
        """Fields copied from the picking when a version is issued."""
        return [
            "shipper_name",
            "shipper_vat",
            "shipper_address",
            "carrier_name",
            "carrier_vat",
            "carrier_address",
            "driver_name",
            "vehicle_plate",
            "trailer_plate",
            "origin_address",
            "destination_name",
            "destination_address",
            "transport_date",
            "gross_weight",
            "goods_description",
            "special_authorization",
            "notes",
        ]

    @api.model
    def _values_equal(self, field_name, value_a, value_b):
        field = self._fields[field_name]
        if field.type == "float":
            digits = field.get_digits(self.env) or (16, 3)
            return (
                float_compare(
                    value_a or 0.0, value_b or 0.0, precision_digits=digits[1]
                )
                == 0
            )
        return (value_a or False) == (value_b or False)

    def _snapshot_equals(self, values):
        """Whether ``values`` holds the same snapshot as this version."""
        self.ensure_one()
        return all(
            self._values_equal(name, self[name], values.get(name))
            for name in self._get_snapshot_fields()
        )

    def _format_value(self, field_name):
        self.ensure_one()
        value = self[field_name]
        if not value:
            return ""
        field = self._fields[field_name]
        if field.type == "date":
            return format_date(self.env, value)
        if field.type == "float":
            return formatLang(self.env, value, digits=field.get_digits(self.env)[1])
        return str(value)

    def _get_previous_values(self, field_name):
        """Formatted values of ``field_name`` in the previous versions of the
        same picking that differ from the value of this version.

        The printed DeCA strikes these values through, right below the value
        in force, so the history of changes is visible on the document.
        """
        self.ensure_one()
        previous = self.picking_id.deca_document_ids.filtered(
            lambda doc: doc.version < self.version
        ).sorted("version")
        values = []
        for doc in previous:
            if self._values_equal(field_name, doc[field_name], self[field_name]):
                continue
            formatted = doc._format_value(field_name)
            if formatted and formatted not in values:
                values.append(formatted)
        return values

    def _generate_attachment(self):
        """Render the DeCA of this version and store it as the PDF file that
        the QR code will serve. The creation date of the file is the issue of
        the first version and the modification date the issue of this one."""
        self.ensure_one()
        report = self.env.ref("l10n_es_deca_oca.action_report_deca")
        content, report_type = report.with_context(
            deca_generating=True
        )._render_qweb_pdf(report.id, res_ids=self.picking_id.ids)
        if report_type == "pdf":
            content = self._set_pdf_metadata(content)
        # The file hangs from the version, read-only for every user, so it
        # cannot be removed from the chatter of the transfer by mistake
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": f"{self.display_name}.{report_type}".replace("/", "-"),
                    "raw": content,
                    "mimetype": (
                        "application/pdf" if report_type == "pdf" else "text/html"
                    ),
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
        )
        self.sudo().attachment_id = attachment

    def _set_pdf_metadata(self, content):
        first = self.picking_id.deca_document_ids.sorted("version")[:1] or self
        reader = PdfFileReader(io.BytesIO(content), strict=False)
        writer = PdfFileWriter()
        writer.appendPagesFromReader(reader)
        metadata = {
            "/Title": self.display_name,
            "/Subject": "Documento electrónico de Control Administrativo",
            "/CreationDate": self._pdf_date(first.date),
            "/ModDate": self._pdf_date(self.date),
        }
        (getattr(writer, "add_metadata", None) or writer.addMetadata)(metadata)
        stream = io.BytesIO()
        writer.write(stream)
        return stream.getvalue()

    @staticmethod
    def _pdf_date(value):
        # Odoo stores naive datetimes in UTC
        return value.strftime("D:%Y%m%d%H%M%SZ")
