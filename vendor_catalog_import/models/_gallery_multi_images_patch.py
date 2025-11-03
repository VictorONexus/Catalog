# -*- coding: utf-8 -*-
import logging, base64, re
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode, quote
from odoo import models, api, SUPERUSER_ID
from concurrent.futures import ThreadPoolExecutor
import time
import atexit
_logger = logging.getLogger(__name__)
MAX_RETRIES = 1
THREADS = 5
EXECUTOR2 = ThreadPoolExecutor(max_workers=THREADS)
atexit.register(lambda: EXECUTOR2.shutdown(wait=False))

try:
    import requests
except Exception:
    requests = None

_logger = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
REQ_KW = {
    "timeout": 25,
    "headers": {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    "allow_redirects": True,
}

def _safe_url(u: str) -> str:
    """Escapa espacios/caracteres raros en la ruta de la URL."""
    try:
        if not u:
            return u
        p = urlsplit(u)
        path = quote(p.path, safe="/._-")
        q = p.query
        return urlunsplit((p.scheme, p.netloc, path, q, p.fragment))
    except Exception:
        return u

def _iter_getpicture_variants(url: str):
    """Para endpoints getpicture de Infortisa probamos action=large/normal/None."""
    if not url:
        return
    url = _safe_url(url)
    yield url
    try:
        parts = urlsplit(url)
        if "getpicture" not in (parts.path or "").lower():
            return
        qs = parse_qs(parts.query, keep_blank_values=True)
        def build(new_qs):
            return urlunsplit((parts.scheme or "https", parts.netloc, parts.path,
                               urlencode(new_qs, doseq=True), parts.fragment))
        for action in ("large", "normal", None):
            new = dict(qs)
            if action is None:
                new.pop("action", None)
            else:
                new["action"] = [action]
            yield build(new)
    except Exception:
        return

def _download(url, referer=None):
    if not (requests and url):
        return None
    url = _safe_url(url)
    headers = dict(REQ_KW["headers"])
    if referer:
        headers["Referer"] = referer
    kw = dict(REQ_KW, headers=headers)

    candidates = list(_iter_getpicture_variants(url)) or [url]
    for candidate in candidates:
        try:
            kw.setdefault('timeout', (3, 8))

            # Reutilizar conexiones (pool) para acelerar descargas repetidas

            _rq = requests

            try:

                _SESSION

            except NameError:

                from requests.adapters import HTTPAdapter

                try:

                    from urllib3.util.retry import Retry

                    _retry = Retry(total=1, backoff_factor=0.25, status_forcelist=[502,503,504], allowed_methods=["GET","HEAD"])

                except Exception:

                    _retry = None

                _SESSION = _rq.Session()

                ha = HTTPAdapter(pool_connections=40, pool_maxsize=40, max_retries=_retry) if _retry else HTTPAdapter(pool_connections=40, pool_maxsize=40)

                _SESSION.mount('http://', ha)

                _SESSION.mount('https://', ha)

            r = _SESSION.get(candidate, **kw)
            if r.ok and r.content:
                return r.content
            _logger.debug("Vendor gallery: HTTP %s on %s", getattr(r, "status_code", "?"), candidate)
        except Exception as e:
            _logger.debug("Vendor gallery: error %s on %s", e, candidate)
            continue
    return None

def _derive_infortisa_variants(main_url: str, sku: str):
    """
    A partir de una URL tipo .../AAACET0216_800.jpg o .../AAACET0216.jpg
    genera candidatos:
      base_2.jpg / base-2.jpg / base_800_2.jpg / base_2_800.jpg
      y también base_ImgAdi1..5.jpg
    """
    out = []
    if not (main_url and sku):
        return out
    u = _safe_url(main_url)
    try:
        parts = urlsplit(u)
        dirname, fname = parts.path.rsplit('/', 1)
        stem, ext = fname.rsplit('.', 1)
        ext = ext.lower()
        base_url = urlunsplit((parts.scheme, parts.netloc, dirname, parts.query, parts.fragment))
    except Exception:
        return out

    bases = {stem}

    # Si termina en _1 o -1, probar también la base sin el 1
    if re.search(r'([_-])1$', stem):
        bases.add(re.sub(r'([_-])1$', r'\1', stem))

    # Detectar tamaño (_800, -800, _1024...)
    m = re.search(r'(.*?)([_-](?:600|700|800|900|1000|1024))$', stem)
    size = None
    if m:
        pre, size = m.groups()
        bases.update({pre, pre + size})

    cand = []
    for b in list(bases):
        for i in range(2, 6):
            cand += [f"{b}_{i}", f"{b}-{i}"]
        cand += [f"{b}_ImgAdi1", f"{b}_ImgAdi2", f"{b}_ImgAdi3", f"{b}_ImgAdi4", f"{b}_ImgAdi5"]

    if size:
        pre = re.sub(rf'{re.escape(size)}$', '', stem)
        for i in range(2, 6):
            cand += [f"{pre}{size}_{i}", f"{pre}_{i}{size}", f"{pre}-{i}{size}"]

    seen = set()
    for c in cand:
        url = f"{base_url}/{c}.{ext}"
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out

def _scrape_infortisa_gallery(page_url: str):
    """Plan C: descargar HTML de la ficha y extraer imágenes conocidas."""
    urls = []
    if not (requests and page_url and "infortisa.com" in page_url):
        return urls
    try:
        r = requests.get(page_url, **REQ_KW)
        if not (r.ok and r.text):
            return urls
        html = r.text
        urls += re.findall(r'https?://(?:www\.)?infortisa\.com/images/product/large/[^\s"\'<>]+\.jpe?g', html, re.I)
        urls += re.findall(r'https?://recursos\.infortisa\.com/[^\s"\'<>]+\.jpe?g', html, re.I)
    except Exception as e:
        _logger.debug("Vendor gallery: scrape error %s on %s", e, page_url)
    seen, out = set(), []
    for u in urls:
        u = _safe_url(u)
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:12]

class VendorCatalogGalleryPatch(models.Model):
    _inherit = "vendor.catalog.config"

    def _normalize_extra_urls(self, item):
        """Recoge urls de todas las claves típicas y limpia duplicados."""
        urls = []
        key_sets = [
            ('images','extra_images','gallery','image_urls','attachments'),
            ('img_adi1','img_adi2','img_adi3','imgadi1','imgadi2','imgadi3',
             'image1','image2','image3','image4','image5','secondary_image','secondary_images'),
        ]
        for keys in key_sets:
            for k in keys:
                v = item.get(k)
                if isinstance(v, (list, tuple, set)):
                    urls += [u for u in v if isinstance(u, str) and u.startswith(('http://','https://'))]
                elif isinstance(v, str) and v.startswith(('http://','https://')):
                    urls.append(v)

        seen, out = set(), []
        for u in urls:
            u = _safe_url(u)
            if u and u not in seen:
                seen.add(u)
                out.append(u)

        main = item.get('image_url') or item.get('image') or item.get('main_image')
        if isinstance(main, str):
            out = [u for u in out if _safe_url(u) != _safe_url(main)]
        return out[:12]

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


    def _upsert_product(self, item):
        res = super()._upsert_product(item)
        tmpl = res[0] if isinstance(res, (list, tuple)) else res
        if not tmpl:
            return res

        # --- GATE: no descargar/crear extras salvo que se pida explícitamente ---
        ctx = (self.env.context or {})
        if not ((ctx.get('replace_gallery') or ctx.get('load_extra_images')) and not ctx.get('ignore_extra_images')):
            return res

        ProductImage = self.env['product.image'].sudo()
        has_vendor_flag = 'x_vendor_image' in ProductImage._fields
        has_vendor_url  = 'x_vendor_image_url' in ProductImage._fields

        # limpiar galería si se pide replace_gallery
        if ctx.get('replace_gallery'):
            dom = [('product_tmpl_id', '=', tmpl.id)]
            if has_vendor_flag:
                dom.append(('x_vendor_image', '=', True))
            ProductImage.search(dom).unlink()

        sku = (item.get('default_code') or item.get('sku') or tmpl.default_code or '').strip().upper()

        # Plan A: extras directos del feed
        extras = self._normalize_extra_urls(item)

        # Plan B: derivar variantes típicas de Infortisa a partir de la principal
        if not extras:
            main = item.get('image_url') or item.get('image') or getattr(tmpl, 'image_url', False)
            if isinstance(main, str) and 'infortisa' in main:
                extras = _derive_infortisa_variants(main, sku)

        # Plan C: rascar la ficha web si sigue vacío
        if not extras:
            for k in ('product_url','url','web_url','link'):
                page = item.get(k)
                if isinstance(page, str) and 'infortisa.com' in page:
                    extras = _scrape_infortisa_gallery(page)
                    break
        if extras:
            self.create_images(item, extras, tmpl.id, tmpl.name, has_vendor_flag, has_vendor_url, ProductImage, sku)
        return res
