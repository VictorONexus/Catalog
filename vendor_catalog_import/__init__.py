# -*- coding: utf-8 -*-
from . import models

# Re-exportar hooks para que Odoo los encuentre como atributos del módulo
try:
    from .hooks import post_init_hook, post_load  # noqa: F401
except Exception:
    # Si hooks.py no existe por cualquier motivo, definir stubs seguros
    def post_init_hook(cr, registry):
        return
    def post_load():
        return
