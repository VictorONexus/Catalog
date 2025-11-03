# -*- coding: utf-8 -*-
import json, importlib
from odoo import models
from odoo.exceptions import UserError
from odoo.tools.translate import _

class VendorCatalogKwargsInject(models.Model):
    _inherit = "vendor.catalog.config"

    def _fetch_items(self):
        module_name = getattr(self, 'python_module', None) or getattr(self, 'py_module', None)
        func_name   = getattr(self, 'python_callable', None) or getattr(self, 'py_callable', None)
        raw_kwargs  = getattr(self, 'python_kwargs', None) or getattr(self, 'params_json', None) or "{}"

        try:
            kwargs = raw_kwargs if isinstance(raw_kwargs, dict) else json.loads(raw_kwargs or "{}")
        except Exception as e:
            raise UserError(_("Parámetros JSON inválidos: %s") % e)

        ctx = self.env.context or {}
        if (ctx.get('ignore_limit') or ctx.get('from_shell')) and isinstance(kwargs, dict):
            kwargs.pop('limit', None)

        # --- inyectar/normalizar valores por defecto ---
        if isinstance(kwargs, dict):
            app_key = kwargs.get('app_key')
            if not app_key:  # sobreescribe si None o ""
                try:
                    app_key = self._get_infortisa_app_key()
                except Exception:
                    app_key = ""
                kwargs['app_key'] = app_key or ""

            cmap = kwargs.get('category_map_path')
            if not cmap:
                try:
                    cmap = self._get_category_map_path()
                except Exception:
                    cmap = ""
                kwargs['category_map_path'] = cmap or ""

        if not module_name or not func_name:
            raise UserError(_("Faltan módulo o función Python en la configuración."))

        mod = importlib.import_module(module_name)
        func = getattr(mod, func_name, None)
        if not callable(func):
            raise UserError(_("La función %s no existe en %s") % (func_name, module_name))

        res = func(**kwargs) or []
        if not isinstance(res, list):
            res = list(res)
        return res
