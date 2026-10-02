# Copyright 2026 Abraham Anes - abraham@tesseratech.es
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models

# Picking fields editable from the wizard, in the order they are proposed
WIZARD_FIELDS = (
    "deca_carrier_partner_id",
    "deca_driver_name",
    "deca_vehicle_plate",
    "deca_trailer_plate",
    "deca_gross_weight",
    "deca_goods_description",
    "deca_special_authorization",
    "deca_notes",
)


class L10nEsDecaUpdate(models.TransientModel):
    """Modify the data of an issued DeCA stating the reason of the change,
    as required by the Resolución de 5 de junio de 2026 (apartado Quinto)."""

    _name = "l10n_es.deca.update"
    _description = "Update an issued DeCA"

    picking_id = fields.Many2one(
        comodel_name="stock.picking", required=True, readonly=True
    )
    deca_carrier_partner_id = fields.Many2one(
        comodel_name="res.partner", string="Effective carrier"
    )
    deca_driver_name = fields.Char(string="Driver")
    deca_vehicle_plate = fields.Char(string="Vehicle plate", size=16)
    deca_trailer_plate = fields.Char(string="Trailer plate", size=16)
    deca_gross_weight = fields.Float(string="Gross weight (kg)", digits="Stock Weight")
    deca_goods_description = fields.Text(string="Nature of the goods")
    deca_special_authorization = fields.Text(string="Special traffic authorisation")
    deca_notes = fields.Text(string="DeCA observations")
    change_reason = fields.Text(string="Reason of the change", required=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        picking_id = values.get("picking_id") or self.env.context.get("active_id")
        picking = self.env["stock.picking"].browse(picking_id)
        if picking:
            values["picking_id"] = picking.id
            for name in WIZARD_FIELDS:
                value = picking[name]
                values[name] = value.id if isinstance(value, models.Model) else value
        return values

    def action_confirm(self):
        self.ensure_one()
        picking = self.picking_id.with_context(deca_change_reason=self.change_reason)
        values = {}
        for name in WIZARD_FIELDS:
            value = self[name]
            value = value.id if isinstance(value, models.Model) else value
            current = picking[name]
            current = current.id if isinstance(current, models.Model) else current
            if (value or False) != (current or False):
                values[name] = value
        if values:
            picking.write(values)
        else:
            # Nothing changed on the transfer itself, but the printed data may
            # have (e.g. an address): refresh the version anyway
            picking._deca_create_version(self.change_reason)
        return {"type": "ir.actions.act_window_close"}
