# -*- coding: utf-8 -*-
import os
from odoo import models
from odoo.modules.module import get_module_resource

class VendorCatalogConfigHelpers(models.Model):
    _inherit = "vendor.catalog.config"

    def _get_infortisa_app_key(self):
        """Clave API robusta: kwargs -> auth_token -> ir.config_parameter -> ENV."""
        try:
            kw = self._parse_kwargs_if_any() or {}
        except Exception:
            kw = {}
        ICP = self.env['ir.config_parameter'].sudo()
        candidates = [
            (kw.get('app_key') if isinstance(kw, dict) else None),
            (self.auth_token or '').strip(),
            (ICP.get_param('vendor_catalog_import.infortisa_app_key') or '').strip(),
            (ICP.get_param('infortisa.app_key') or '').strip(),
            (os.getenv('INFORTISA_APP_KEY') or '').strip(),
        ]
        for cand in candidates:
            if cand:
                return cand
        return ''

    def _get_category_map_path(self):
        """Ruta CSV: kwargs -> parámetro del sistema -> fichero del módulo."""
        try:
            kw = self._parse_kwargs_if_any() or {}
        except Exception:
            kw = {}
        path = (kw.get('category_map_path') if isinstance(kw, dict) else None)
        if path:
            return path
        ICP = self.env['ir.config_parameter'].sudo()
        param = (ICP.get_param('vendor_catalog_import.infortisa_category_map_path') or '').strip()
        if param:
            return param
        return get_module_resource('vendor_catalog_import', 'data', 'infortisa_categorias_final.csv')
