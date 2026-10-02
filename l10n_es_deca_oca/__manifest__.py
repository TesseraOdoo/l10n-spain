# Copyright 2026 Abraham Anes - abraham@tesseratech.es
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    "name": "DeCA - Documento electrónico de Control Administrativo",
    "summary": "Electronic administrative control document for road freight "
    "transport in Spain (DeCA)",
    "version": "18.0.1.0.0",
    "category": "Inventory/Delivery",
    "author": "Tesseratech Solutions S.L., Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-spain",
    "license": "AGPL-3",
    "depends": ["stock_delivery", "delivery_carrier_partner"],
    "data": [
        "security/ir.model.access.csv",
        "security/deca_security.xml",
        "wizard/deca_update_views.xml",
        "views/deca_document_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_picking_type_views.xml",
        "views/res_config_settings_views.xml",
        "report/deca_report.xml",
        "report/deca_report_templates.xml",
    ],
    "installable": True,
    "maintainers": ["Abranes"],
}
