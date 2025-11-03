# -*- coding: utf-8 -*-
{
  "name": "Vendor Catalog Import",
  "version": "18.0.1.0.0",
  "summary": "Importación de catálogo y stock de proveedores (Infortisa, etc.)",
  "category": "Inventory",
  "license": "LGPL-3",
  "author": "Nexus",
  "website": "",
  "depends": [
    "base",
    "product",
    "website_sale",
  ],
  "data": [
    "security/ir.model.access.csv",
    "data/ir_cron.xml",
    "views/vendor_catalog_views.xml",
    "views/product_supplierinfo_vendor_stock.xml",
    "views/product_list_vendor_stock.xml",
    "views/website_vendor_stock.xml"
  ],
  "post_init_hook": "post_init_hook",
  "post_load": "post_load",
  "installable": True,
  "application": False
}
