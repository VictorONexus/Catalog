# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.api import ValuesType
from odoo.tools.translate import html_translate

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    description_ecommerce = fields.Html(
        string="eCommerce Description",
        translate=html_translate,
        sanitize_overridable=True,
        sanitize_attributes=False,
        sanitize_form=False,
        compute='_compute_description_ecommerce',
        readonly=False
    )

    description_ecommerce_remote = fields.Html(
        string="eCommerce Description",
        translate=html_translate,
        sanitize_overridable=True,
        sanitize_attributes=False,
        sanitize_form=False,
    )

    x_vendor_stock = fields.Integer(
        string='Stock distribuidor',
        default=0,
        help='Stock informado por el proveedor (solo informativo, no inventario real).'
    )
    x_vendor_name = fields.Char(
        string='Proveedor (catálogo)',
        help='Nombre del proveedor que aporta el stock/precio.'
    )

    def _compute_description_ecommerce(self):
        for record in self:
            record.description_ecommerce = record.description_ecommerce_remote
            if record.default_code and not record.description_ecommerce_remote:
                catalog = self.env['vendor.catalog.config'].sudo()
                catalog._upsert_prod_desc(record.default_code, record)
