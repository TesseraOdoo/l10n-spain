# Copyright 2026 Abraham Anes - abraham@tesseratech.es
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from werkzeug.exceptions import NotFound

from odoo import _, http
from odoo.http import content_disposition, request


class DecaController(http.Controller):
    @http.route(
        "/deca/<string:token>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def deca_download(self, token, **kwargs):
        """Public download of the DeCA pointed to by its QR code.

        The regulation requires a direct download over HTTPS without any
        authentication or intermediate page, so the URL is only protected by
        the per-delivery token. The file served is the one stored when the
        current version was issued.
        """
        picking = (
            request.env["stock.picking"]
            .sudo()
            .search([("deca_access_token", "=", token)], limit=1)
        )
        attachment = picking.deca_current_document_id.attachment_id
        if not attachment:
            raise NotFound()
        if not picking._deca_download_allowed():
            return request.make_response(
                _("This DeCA is no longer available for download."),
                status=410,
                headers=[("Content-Type", "text/plain; charset=utf-8")],
            )
        content = attachment.raw
        return request.make_response(
            content,
            headers=[
                ("Content-Type", attachment.mimetype),
                ("Content-Length", str(len(content))),
                ("Content-Disposition", content_disposition(attachment.name)),
                ("Cache-Control", "no-store"),
            ],
        )
