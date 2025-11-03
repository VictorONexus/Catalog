# -*- coding: utf-8 -*-
import base64
from odoo import models, api, SUPERUSER_ID
from .vendor_catalog import _download_first_ok  # ya existe en tu módulo
import psycopg2
from concurrent.futures import ThreadPoolExecutor
import time
import logging
_logger = logging.getLogger(__name__)
MAX_RETRIES = 5
THREADS = 5

class ProductTemplateGallerySafe(models.Model):
    _inherit = 'product.template'

    def _update_product_image_now(self, urls, ids, replace):
        """Schedule immediate image download & update using a thread pool."""

        def task(urls, replace, ids, registry):

            for attempt in range(MAX_RETRIES):
                try:
                    # create a new cursor & environment inside thread
                    with registry.cursor() as cr:
                        env = api.Environment(cr, SUPERUSER_ID, {})
                        Image = env['product.image'].sudo()
                        web_ids = env['website'].sudo().search([]).ids
                        template = env['product.template'].browse(ids)
                        for tmpl in template:
                            dom_all = [('product_tmpl_id', '=', tmpl.id)]
                            # 1) Si piden reemplazar: borra vendor-images y cualquier imagen sin binario
                            if replace:
                                dom_vendor = list(dom_all)
                                if 'x_vendor_image' in Image._fields:
                                    dom_vendor.append(('x_vendor_image', '=', True))
                                Image.search(dom_vendor).unlink()
                            Image.search(dom_all + [('image_1920', '=', False)]).unlink()

                            # 2) Secuencia base
                            seq = max(Image.search(dom_all).mapped('sequence') or [0]) + 10

                            # 3) Descargar y crear SOLO si hay binario
                            created = 0
                            for i, u in enumerate(urls or [], start=1):
                                content = _download_first_ok(u)
                                if not content:
                                    continue
                                vals = {
                                    'product_tmpl_id': tmpl.id,
                                    'image_1920': base64.b64encode(content),
                                    'sequence': seq + i,
                                    'name': tmpl.name or 'Image',
                                }
                                if 'is_published' in Image._fields:
                                    vals['is_published'] = True
                                if web_ids and 'website_ids' in Image._fields:
                                    vals['website_ids'] = [(6, 0, web_ids)]
                                if 'x_vendor_image' in Image._fields:
                                    vals['x_vendor_image'] = True
                                if 'x_vendor_image_url' in Image._fields:
                                    vals['x_vendor_image_url'] = u
                                Image.create(vals);
                                created += 1

                except Exception as e_outer:
                    _logger.exception("Thread failed for Product ID %s: %s", tmpl.name, e_outer)
                    break

        # pass registry instead of self
        executor = ThreadPoolExecutor(max_workers=THREADS)
        executor.submit(task, urls, replace, ids, self.env.registry)

    def vc_apply_gallery_urls(self, urls, replace=False):
        self._update_product_image_now(urls, replace, self.ids)
        return True
