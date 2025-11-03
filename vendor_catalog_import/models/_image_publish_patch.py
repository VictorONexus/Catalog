# -*- coding: utf-8 -*-
from odoo import api, models

class ProductImageWebsitePublishPatch(models.Model):
    _inherit = 'product.image'

    @api.model_create_multi
    def create(self, vals_list):
        PI = self.env['product.image']
        has_ip  = 'is_published' in PI._fields
        has_wid = 'website_ids' in PI._fields
        websites = self.env['website'].sudo().search([])
        for vals in vals_list:
            if has_ip:
                vals.setdefault('is_published', True)
            if has_wid and websites and not vals.get('website_ids'):
                vals['website_ids'] = [(6, 0, websites.ids)]
        return super().create(vals_list)
