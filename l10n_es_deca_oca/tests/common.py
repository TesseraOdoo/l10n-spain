# Copyright 2026 Abraham Anes - abraham@tesseratech.es
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import common


class DecaCommon(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_vat_validation=True))
        cls.company = cls.env.company
        cls.company.write({"deca_auto_issue": True, "deca_download_expiry_days": 7})
        cls.spain = cls.env.ref("base.es")
        cls.company.partner_id.write(
            {
                "vat": "ESB12345674",
                "street": "Calle del Cargador 1",
                "zip": "46001",
                "city": "Valencia",
                "country_id": cls.spain.id,
            }
        )
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.warehouse.out_type_id.deca_required = True
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Cliente Destino S.L.",
                "street": "Avenida del Destinatario 25",
                "zip": "28001",
                "city": "Madrid",
                "country_id": cls.spain.id,
            }
        )
        cls.carrier_partner = cls.env["res.partner"].create(
            {
                "name": "Transportes Efectivos S.A.",
                "vat": "ESA12345674",
                "street": "Polígono del Transporte 7",
                "zip": "46980",
                "city": "Paterna",
                "country_id": cls.spain.id,
                "is_company": True,
            }
        )
        cls.delivery_product = cls.env["product.product"].create(
            {"name": "Transporte", "type": "service", "sale_ok": False}
        )
        cls.carrier = cls.env["delivery.carrier"].create(
            {
                "name": "Transporte terrestre",
                "delivery_type": "fixed",
                "fixed_price": 0,
                "product_id": cls.delivery_product.id,
                "partner_id": cls.carrier_partner.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Semilla de maíz", "type": "consu", "weight": 10}
        )
        cls.picking = cls._create_picking()

    @classmethod
    def _create_picking(cls, qty=5.0, confirm=True):
        picking_type = cls.warehouse.out_type_id
        picking = cls.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "partner_id": cls.customer.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": cls.customer.property_stock_customer.id,
                "carrier_id": cls.carrier.id,
                "deca_vehicle_plate": "1234 bcd",
                "deca_trailer_plate": "r-5678-bbc",
                "deca_driver_name": "Conductor Demo",
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": cls.product.name,
                            "product_id": cls.product.id,
                            "product_uom_qty": qty,
                            "product_uom": cls.product.uom_id.id,
                            "location_id": picking_type.default_location_src_id.id,
                            "location_dest_id": cls.customer.property_stock_customer.id,
                        },
                    )
                ],
            }
        )
        if confirm:
            picking.action_confirm()
        return picking
