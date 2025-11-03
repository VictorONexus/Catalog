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
