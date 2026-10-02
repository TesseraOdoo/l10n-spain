# Copyright 2026 Abraham Anes - abraham@tesseratech.es
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import formatLang

from .common import DecaCommon


@tagged("post_install", "-at_install")
class TestDecaDocument(DecaCommon):
    def test_defaults_from_picking(self):
        # Proposed from the operation type, whatever the shipping method
        self.assertTrue(self.picking.deca_required)
        self.warehouse.out_type_id.deca_required = False
        self.assertFalse(self._create_picking().deca_required)
        self.warehouse.out_type_id.deca_required = True
        self.assertEqual(self.picking.deca_carrier_partner_id, self.carrier_partner)
        self.assertEqual(self.picking.deca_vehicle_plate, "1234BCD")
        self.assertEqual(self.picking.deca_trailer_plate, "R5678BBC")
        self.assertFalse(self.picking.deca_goods_description)
        self.assertEqual(self.picking.deca_state, "none")
        self.assertFalse(self.picking.deca_url)

    def test_issue(self):
        # Not in draft
        draft = self._create_picking(confirm=False)
        draft.action_deca_issue()
        self.assertEqual(draft.deca_state, "none")
        # Missing mandatory data blocks the issue with an explicit message
        self.picking.deca_vehicle_plate = False
        self.carrier_partner.vat = False
        with self.assertRaises(UserError) as error:
            self.picking.with_context(lang="en_US").action_deca_issue()
        self.assertIn("Vehicle plate", str(error.exception))
        self.assertIn("Effective carrier VAT", str(error.exception))
        self.assertEqual(self.picking.deca_state, "none")
        # Issue: snapshot, file and token
        self.picking.deca_vehicle_plate = "1234 bcd"
        self.carrier_partner.vat = "ESA12345674"
        self.picking.action_deca_issue()
        self.assertEqual(self.picking.deca_state, "issued")
        doc = self.picking.deca_current_document_id
        self.assertEqual(doc.version, 1)
        self.assertTrue(doc.is_current)
        self.assertFalse(doc.change_reason)
        self.assertEqual(doc.shipper_vat, "ESB12345674")
        self.assertIn("Valencia", doc.shipper_address)
        self.assertNotIn("\n\n", doc.shipper_address)
        self.assertEqual(doc.carrier_name, "Transportes Efectivos S.A.")
        self.assertEqual(doc.carrier_vat, "ESA12345674")
        self.assertEqual(doc.vehicle_plate, "1234BCD")
        self.assertEqual(doc.trailer_plate, "R5678BBC")
        self.assertEqual(doc.driver_name, "Conductor Demo")
        self.assertAlmostEqual(doc.gross_weight, 50.0)
        self.assertEqual(doc.goods_description, "Semilla de maíz")
        # A manual gross weight takes precedence over the computed one and
        # survives the validation, which recomputes shipping_weight
        heavy = self._create_picking()
        heavy.deca_gross_weight = 1234.5
        heavy.move_ids.quantity = 5
        heavy.button_validate()
        self.assertAlmostEqual(heavy.deca_current_document_id.gross_weight, 1234.5)
        self.assertEqual(
            doc.transport_date,
            fields.Date.context_today(self.picking, self.picking.scheduled_date),
        )
        self.assertIn("Madrid", doc.destination_address)
        self.assertTrue(doc.origin_address)
        self.assertTrue(doc.attachment_id.raw)
        self.assertEqual(doc.attachment_id.res_model, doc._name)
        self.assertEqual(doc.attachment_id.res_id, doc.id)
        token = self.picking.deca_access_token
        self.assertTrue(token)
        self.assertTrue(self.picking.deca_url.endswith(f"/deca/{token}"))
        self.assertIn(token, self.picking._deca_get_qr_src())
        # Issuing again without changes keeps the version and the token
        self.picking.action_deca_issue()
        self.assertEqual(self.picking.deca_document_count, 1)
        self.assertEqual(self.picking.deca_access_token, token)
        # The company default is proposed on new deliveries
        self.company.deca_goods_description = "Semillas"
        other = self._create_picking()
        self.assertEqual(other.deca_goods_description, "Semillas")

    def test_change_after_issue(self):
        # Before the issue, changes leave no trace
        self.picking.deca_vehicle_plate = "0000AAA"
        self.assertEqual(self.picking.deca_document_count, 0)
        self.picking.action_deca_issue()
        first_file = self.picking.deca_current_document_id.attachment_id
        # Once issued, a direct change without reason is refused
        with self.assertRaises(UserError):
            self.picking.deca_vehicle_plate = "9999 zzz"
        # The update wizard, run by a plain stock user, proposes the current
        # values and asks the reason
        user = self.env["res.users"].create(
            {
                "name": "Stock user",
                "login": "deca_user",
                "groups_id": [(6, 0, [self.env.ref("stock.group_stock_user").id])],
            }
        )
        wizard = (
            self.env["l10n_es.deca.update"]
            .with_user(user)
            .with_context(active_id=self.picking.id)
            .create({"change_reason": "Cambio de tractora por avería"})
        )
        self.assertEqual(wizard.deca_vehicle_plate, "0000AAA")
        self.assertEqual(wizard.deca_carrier_partner_id, self.carrier_partner)
        wizard.write({"deca_vehicle_plate": "9999 zzz", "deca_notes": "Frágil"})
        wizard.action_confirm()
        doc = self.picking.deca_current_document_id
        self.assertEqual(doc.version, 2)
        self.assertEqual(doc.vehicle_plate, "9999ZZZ")
        self.assertEqual(doc.notes, "Frágil")
        self.assertEqual(doc.change_reason, "Cambio de tractora por avería")
        self.assertEqual(doc._get_previous_values("vehicle_plate"), ["0000AAA"])
        self.assertEqual(doc._get_previous_values("notes"), [])
        self.assertEqual(doc._get_previous_values("trailer_plate"), [])
        # New file per version, the previous one is kept
        self.assertTrue(doc.attachment_id)
        self.assertNotEqual(doc.attachment_id, first_file)
        self.assertTrue(first_file.exists())
        # Confirming the wizard without changes refreshes nothing new
        self.env["l10n_es.deca.update"].with_context(active_id=self.picking.id).create(
            {"change_reason": "Sin cambios"}
        ).action_confirm()
        self.assertEqual(self.picking.deca_document_count, 2)
        # Programmatic changes state the reason through the context
        self.picking.with_context(deca_change_reason="Cambio de conductor").write(
            {"deca_driver_name": "Otro Conductor"}
        )
        self.assertEqual(self.picking.deca_document_count, 3)
        self.assertEqual(
            self.picking.deca_current_document_id.change_reason, "Cambio de conductor"
        )

    def test_auto_issue_on_validation(self):
        # Missing data blocks the validation of a delivery requiring a DeCA
        self.picking.deca_vehicle_plate = False
        self.picking.move_ids.quantity = 5
        with self.assertRaises(UserError):
            self.picking.button_validate()
        self.picking.deca_vehicle_plate = "1234BCD"
        self.picking.button_validate()
        self.assertEqual(self.picking.state, "done")
        self.assertEqual(self.picking.deca_state, "issued")
        self.assertEqual(self.picking.deca_document_count, 1)
        # Not required, or automatic issue disabled: nothing is issued
        other = self._create_picking()
        other.deca_required = False
        other.move_ids.quantity = 5
        other.button_validate()
        self.assertEqual(other.deca_state, "none")
        self.company.deca_auto_issue = False
        third = self._create_picking()
        third.move_ids.quantity = 5
        third.button_validate()
        self.assertEqual(third.deca_state, "none")

    def test_validation_refreshes_issued_version(self):
        self.picking.action_deca_issue()
        self.picking.move_ids.quantity = 3
        self.picking.with_context(skip_backorder=True).button_validate()
        self.assertEqual(self.picking.state, "done")
        doc = self.picking.deca_current_document_id
        self.assertEqual(doc.version, 2)
        self.assertTrue(doc.change_reason)
        self.assertAlmostEqual(doc.gross_weight, 30.0)
        self.assertEqual(
            doc._get_previous_values("gross_weight"),
            [formatLang(self.env, 50.0, digits=2)],
        )

    def test_download_expiry(self):
        self.picking.move_ids.quantity = 5
        self.picking.button_validate()
        self.assertTrue(self.picking._deca_download_allowed())
        self.picking.date_done = fields.Datetime.now() - timedelta(days=8)
        self.assertFalse(self.picking._deca_download_allowed())
        self.company.deca_download_expiry_days = 0
        self.assertTrue(self.picking._deca_download_allowed())

    def test_versions_are_immutable_for_users(self):
        self.picking.action_deca_issue()
        user = self.env["res.users"].create(
            {
                "name": "Stock manager",
                "login": "deca_manager",
                "groups_id": [(6, 0, [self.env.ref("stock.group_stock_manager").id])],
            }
        )
        doc = self.picking.deca_current_document_id.with_user(user)
        self.assertEqual(doc.vehicle_plate, "1234BCD")
        self.assertTrue(doc.attachment_id.raw)
        with self.assertRaises(AccessError):
            doc.write({"vehicle_plate": "HACKED"})
        # The issued file cannot be deleted either, not even by the manager
        with self.assertRaises(AccessError):
            doc.attachment_id.unlink()
