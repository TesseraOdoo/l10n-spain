# Copyright 2026 Abraham Anes - abraham@tesseratech.es
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models
from odoo.tools.pdf import merge_pdf

DECA_REPORT_NAME = "l10n_es_deca_oca.report_deca"


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        if (
            report.report_name == DECA_REPORT_NAME
            and res_ids
            and not self.env.context.get("deca_generating")
        ):
            documents = (
                self.env["stock.picking"]
                .browse(res_ids)
                .mapped("deca_current_document_id")
            )
            attachments = documents.mapped("attachment_id")
            if len(attachments) == len(res_ids) and all(
                att.mimetype == "application/pdf" for att in attachments
            ):
                return merge_pdf([att.raw for att in attachments]), "pdf"
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
