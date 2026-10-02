# Copyright 2026 Abraham Anes - abraham@tesseratech.es
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    deca_auto_issue = fields.Boolean(
        related="company_id.deca_auto_issue", readonly=False
    )
    deca_goods_description = fields.Char(
        related="company_id.deca_goods_description", readonly=False
    )
    deca_download_expiry_days = fields.Integer(
        related="company_id.deca_download_expiry_days", readonly=False
    )
