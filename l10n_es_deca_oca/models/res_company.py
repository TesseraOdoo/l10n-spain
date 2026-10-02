# Copyright 2026 Abraham Anes - abraham@tesseratech.es
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    deca_auto_issue = fields.Boolean(
        string="Issue the DeCA on validation",
        default=True,
        help="Issue the DeCA automatically when a delivery that requires it "
        "is validated. The validation fails if mandatory DeCA data is missing.",
    )
    deca_goods_description = fields.Char(
        string="Default nature of the goods",
        help="Proposed as nature of the goods on every delivery requiring a DeCA.",
    )
    deca_download_expiry_days = fields.Integer(
        string="DeCA download period (days)",
        default=7,
        help="Days after the delivery is done during which the DeCA can still "
        "be downloaded from its QR code. The regulation allows disabling the "
        "download seven calendar days after the end of the service. "
        "Set 0 to keep the download always available.",
    )
