# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)

BAD_TERMS = ['show_360_images', 'product_360', '360_view']
SKIP_MODS = [
    'ts_ecommerce_product_360_view','product_multi_images','product_warranty',
    'rest_api_odoo','rma','rma_sale','payment_mollie_official','web_login_styles',
    'pos_company_logo','d_social_video','invoice_format_editor','base_account_budget',
    'import_bill_of_materials_in_mrp','infortisa_orders',
]

def _deactivate_bad_views(env):
    View = env['ir.ui.view'].sudo()
    # 1) Por contenido XML (arch_db)
    for term in BAD_TERMS:
        recs = View.search([('arch_db', 'ilike', term), ('active', '=', True)])
        if recs:
            _logger.info("Deactivating %d views by term '%s'", len(recs), term)
            recs.write({'active': False})

    # 2) Por módulo en la key (xml_id)
    for mod in SKIP_MODS:
        recs = View.search([('key', 'ilike', mod + '.%'), ('active', '=', True)])
        if recs:
            _logger.info("Deactivating %d views from module key like %s.%%", len(recs), mod)
            recs.write({'active': False})

def post_init_hook(cr, registry):
    from odoo.api import Environment
    env = Environment(cr, 1, {})  # admin
    _deactivate_bad_views(env)

def post_load():
    # No DB access here; keep empty
    return
