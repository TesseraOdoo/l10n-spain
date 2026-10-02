# Copyright 2026 Abraham Anes - abraham@tesseratech.es
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged

from .common import DecaCommon


@tagged("post_install", "-at_install")
class TestDecaController(DecaCommon, HttpCase):
    def test_public_download(self):
        self.picking.action_deca_issue()
        attachment = self.picking.deca_current_document_id.attachment_id
        response = self.url_open(f"/deca/{self.picking.deca_access_token}")
        self.assertEqual(response.status_code, 200)
        # In test mode the stored file is the HTML rendering of the report
        self.assertEqual(response.headers["Content-Type"], attachment.mimetype)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertEqual(response.content, attachment.raw)

    def test_not_found(self):
        self.assertEqual(self.url_open("/deca/does-not-exist").status_code, 404)
        # Token known but DeCA not issued yet
        self.picking._deca_ensure_access_token()
        response = self.url_open(f"/deca/{self.picking.deca_access_token}")
        self.assertEqual(response.status_code, 404)

    def test_expired_download(self):
        self.picking.move_ids.quantity = 5
        self.picking.button_validate()
        self.picking.date_done = fields.Datetime.now() - timedelta(days=8)
        response = self.url_open(f"/deca/{self.picking.deca_access_token}")
        self.assertEqual(response.status_code, 410)
