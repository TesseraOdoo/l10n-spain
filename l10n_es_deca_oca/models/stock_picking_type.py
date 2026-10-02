# Copyright 2026 Abraham Anes - abraham@tesseratech.es
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    deca_required = fields.Boolean(
        string="DeCA required",
        help="Propose the DeCA as required on every transfer of this operation "
        "type. It can still be unticked on each transfer.",
    )
