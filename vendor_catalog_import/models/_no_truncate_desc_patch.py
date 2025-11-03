# -*- coding: utf-8 -*-
from odoo import models

class VendorCatalogNoTruncateDescPatch(models.Model):
    _inherit = 'vendor.catalog.config'

    def _upsert_product(self, item):
        res = super()._upsert_product(item)
        tmpl = res[0] if isinstance(res, (list, tuple)) else res
        if not tmpl:
            return res

        html1 = (item.get('description_ecommerce') or '').strip()
        html2 = (item.get('website_description') or '').strip()
        # quédate con la más larga (la no recortada)
        longest = html1 if len(html1) >= len(html2) else html2

        if longest:
            try:
                vals = {'description_ecommerce': longest}
                # sincroniza website_description si existe y está vacío o es más corta
                if hasattr(tmpl, 'website_description'):
                    curw = (tmpl.website_description or '')
                    if len(longest) > len(curw):
                        vals['website_description'] = longest
                tmpl.sudo().write(vals)
            except Exception:
                pass
        return res
