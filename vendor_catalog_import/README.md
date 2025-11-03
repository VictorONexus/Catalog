Function to run in background to download images:

    def _update_product_image_now(self, tmpl_id, url):
        """Schedule immediate image download & update using a thread pool."""

        def task1(product_id, image_url, registry):
            image_data = _download_first_ok(image_url)
            if not image_data:
                _logger.warning("Failed to download image for Product ID %s", product_id)
                return

            for attempt in range(MAX_RETRIES):
                try:
                    # create a new cursor & environment inside thread
                    with registry.cursor() as cr:
                        env = api.Environment(cr, SUPERUSER_ID, {})
                        product = env['product.template'].browse(product_id)
                        if not product.exists():
                            _logger.warning("Product not found: %s", product_id)
                            return

                        try:
                            product.with_context(bin_size=False).write({
                                'image_1920': base64.b64encode(image_data)
                            })
                            cr.commit()
                            _logger.info("Updated image for Product ID %s", product_id)
                            break

                        except psycopg2.errors.SerializationFailure:
                            cr.rollback()
                            wait = 0.5 * (attempt + 1)
                            _logger.warning(
                                "Serialization failure for Product ID %s, retrying in %.1fs...",
                                product_id, wait
                            )
                            time.sleep(wait)

                        except Exception as e:
                            cr.rollback()
                            _logger.exception("Unexpected error updating Product ID %s: %s", product_id, e)
                            break
                except Exception as e_outer:
                    _logger.exception("Thread failed for Product ID %s: %s", product_id, e_outer)
                    break

        # pass registry instead of self
        time.sleep(2)
        EXECUTOR.submit(task1, tmpl_id, url, self.env.registry)

Function to download extra images Also runs in background to download extra images:

def create_images(self, item, extras, tmpl, tmpl_name, has_vendor_flag, has_vendor_url, ProductImage, sku):
        def task(item, extras, tmpl, tmpl_name, has_vendor_flag, has_vendor_url, ProductImage, sku, registry):

            for attempt in range(MAX_RETRIES):
                try:
                    # create a new cursor & environment inside thread
                    with registry.cursor() as cr:
                        env = api.Environment(cr, SUPERUSER_ID, {})
                        ProductImage = env['product.image']
                        # descargar binarios
                        binaries = []
                        referer = item.get('product_url') or item.get('url') or None
                        for url in extras:
                            content = _download(url, referer=referer)
                            if content:
                                binaries.append((url, base64.b64encode(content)))

                        created = 0
                        template = env['product.template'].browse(tmpl)
                        for url, b64 in binaries:
                            vals = {'product_tmpl_id': tmpl, 'name': tmpl_name or 'Image', 'image_1920': b64}
                            if has_vendor_flag:
                                vals['x_vendor_image'] = True
                            if has_vendor_url:
                                vals['x_vendor_image_url'] = url
                            ProductImage.create(vals)
                            created += 1

                        # también rellenar image_1..image_5 si existen
                        for i, (url, b64) in enumerate(binaries[:5], start=1):
                            f = f'image_{i}'
                            if f in template._fields:
                                template.sudo().write({f: b64})

                        if created == 0:
                            _logger.info("Vendor gallery: %s -> +0 images (sku=%s)", template.sudo().display_name, sku)
                        else:
                            _logger.info("Vendor gallery: %s -> +%d images", template.sudo().display_name, created)

                except Exception as e_outer:
                    _logger.exception("Thread failed for Product ID %s: %s", template.sudo().name, e_outer)
                    break

        # pass registry instead of self
        EXECUTOR2.submit(task, item, extras, tmpl, tmpl_name, has_vendor_flag, has_vendor_url, ProductImage, sku, self.env.registry)

Please when run from shell and you get concurrent update error, exit the shell and try again. These two functions are uptimised for parallel downlaod of images. They are both called in _upsert_product in 
1. _gallery_multi_images_patch.py and vendor_catalog.py

I have also added new field to product template to solve issue of description truncation. Product description will update via API call when user views the product:
In product_template.py, i added fields and redefined the template field.

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

Then in _infortisa_rest_patch.py, we make a single call to the API. Once this is updated, the description remains updated and complete

        # -*- coding: utf-8 -*-
    import os, re, html as _html, logging
    from odoo import models
    _logger = logging.getLogger(__name__)
    
    try:
        from odoo.tools import html_sanitize
    except Exception:
        html_sanitize = None
    
    try:
        import requests
    except Exception:
        requests = None
    
    BASE = "https://apiv2.infortisa.com"
    HDR  = "Authorization-Token"
    
    def _fetch_full_desc_infortisa(sku, app_key, base=BASE):
        if not (requests and sku and app_key):
            return None
        headers = {HDR: app_key}
        for p in (f"/api/Product/GetProductBySku?Sku={sku}",
                  f"/api/Product/GetProductByPartnumber?partnumber={sku}"):
            try:
                r = requests.get(base + p, headers=headers, timeout=12)
                if not r.ok:
                    continue
                d = r.json() or {}
                fd = d.get("FullDescription") or d.get("fulldescription")
                sd = d.get("ShortDescription") or d.get("shortdescription") or ""
                raw = (fd or sd or "").strip()
                if raw:
                    return _html.unescape(raw)
            except Exception as e:
                _logger.debug("Infortisa REST desc error on %s: %s", p, e)
        return None
    
    def _norm_html_for_cmp(s):
        if s is None:
            return ""
        t = s
        try:
            if html_sanitize:
                t = html_sanitize(t)
        except Exception:
            pass
        t = _html.unescape(t)
        t = t.replace("\r\n","\n").replace("\r","\n").replace("<br />","<br/>")
        t = re.sub(r">\s+<", "><", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t
    
    class VendorCatalogInfortisaRestDesc(models.Model):
        _inherit = "vendor.catalog.config"
    
        def _upsert_prod_desc(self, default_code, tmpl):
            if not tmpl:
                return
    
            PT = self.env["product.template"].sudo()
            if "description_ecommerce" not in PT._fields:
                return
    
            if (self.env.context or {}).get("skip_infortisa_rest"):
                return
    
    
            # usar helper centralizado (si no existe, fallback a ENV/auth_token)
            try:
                app_key = self._get_infortisa_app_key()
            except Exception:
                app_key = (os.getenv("INFORTISA_APP_KEY") or (self.auth_token or "")).strip()
    
            if not app_key:
                _logger.debug("Infortisa REST: sin API key; se deja la descripción del feed.")
                return
    
            remote_html = _fetch_full_desc_infortisa(default_code, app_key)
            if not remote_html:
                return
    
            current = (tmpl.description_ecommerce or "")
            if _norm_html_for_cmp(current) == _norm_html_for_cmp(remote_html):
                return
    
            try:
                remote_html = remote_html.replace("<br />","<br/>")
                remote_html = remote_html.replace("<td><strong>Caracteristicas</strong>", "<td valign='top'><strong>Características</strong></td>")
                remote_html = remote_html.replace("<td><strong>Características</strong>", "<td valign='top'><strong>Características</strong></td>")
                tmpl.update({"description_ecommerce": remote_html, 'description_ecommerce_remote': remote_html})
                _logger.info("Infortisa: description_ecommerce ACTUALIZADA (sku=%s, old_len=%s, new_len=%s)",
                             default_code, len(current or ""), len(remote_html or ""))
            except Exception as e:
                _logger.warning("No se pudo escribir description_ecommerce (sku=%s): %s", sku, e)
            return

Added new field so supplier info can be displayed under purchase tab

        # -*- coding: utf-8 -*-
    from odoo import models, fields

    class ProductSupplierinfo(models.Model):
        _inherit = "product.supplierinfo"
    
        x_vendor_stock_info = fields.Integer(
            string='Stock proveedor (info)',
            help='Stock reportado por el proveedor en la última importación. Solo informativo.',
            readonly=True
        )
    
        x_vendor_name = fields.Char(
            string='Proveedor (catálogo)',
            help='Nombre del proveedor que aporta el stock/precio.'
        )
Then in vendor_catalog.py this line updates the field:

        # 3) Actualiza/crea la línea "buena"
            si_vals = {
                'partner_id': self.vendor_id.id,
                'product_tmpl_id': tmpl.id,
                'product_code': sku,
                'x_vendor_stock_info': int(vals.get('x_vendor_stock') or 0),
                # add needed field here
                'x_vendor_name': tmpl.x_vendor_name,
            }
