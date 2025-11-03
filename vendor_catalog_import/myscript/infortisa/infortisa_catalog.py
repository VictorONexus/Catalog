# -*- coding: utf-8 -*-
"""
Infortisa -> items normalizados para Odoo.
- Lee CSV de tarifa EXT (GetFileV5EXT) autenticando por query/header/bearer.
- Normaliza numéricos (ES), peso, imagen principal y extras.
- Opcional: aplica mapeo de categorías desde CSV (category_map_path).
"""
import os, io, csv, re, unicodedata
from urllib.parse import urlparse
try:
    import requests
except Exception:
    requests = None

BASE = "https://apiv2.infortisa.com"
CSV_EXT_URL = f"{BASE}/api/Tarifa/GetFileV5EXT"

# ------------------------------ helpers ------------------------------
def _strip_accents(s):
    if s is None: return ""
    nfkd = unicodedata.normalize("NFKD", str(s))
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch) and ord(ch) < 128)

def _norm_key(s: str) -> str:
    s = _strip_accents(s or "").lower().strip()
    return re.sub(r"\s+", " ", s)

def _to_float_es(val):
    if val is None:
        return 0.0
    s = str(val).replace("\u00a0"," ").strip()
    s = s.replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "")
    s = s.replace(",", ".")
    try:
        return float(s) if s else 0.0
    except Exception:
        m = re.search(r"[-+]?\d*\.?\d+", s or "")
        return float(m.group()) if m else 0.0

def _to_int(val):
    try:
        return int(round(float(str(val).replace(",", ".").strip())))
    except Exception:
        return 0

def _peso_from_row(row):
    """Peso en KG leyendo múltiples formas de columna."""
    raw = (row.get('PESO') or row.get('Peso') or row.get('peso') or
           row.get('WEIGHT') or row.get('Weight') or row.get('weight') or '')
    raw = str(raw or "").strip()
    if not raw:
        return 0.0
    txt = raw.replace(",", ".").lower()
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*([a-z]*)', txt)
    if not m:
        try:
            return float(txt)
        except Exception:
            return 0.0
    val = float(m.group(1))
    unit = m.group(2)
    if unit.startswith('g'):
        val /= 1000.0
    return round(val, 6)

def _col(row, candidates):
    keys = {_norm_key(k): k for k in row.keys()}
    for c in candidates:
        k = keys.get(_norm_key(c))
        if k is not None:
            v = row.get(k)
            if v not in (None, "", "null", "None"):
                return str(v).strip()
    return ""

def _sum_stock(r):
    total = 0
    for k in ("STOCKCENTRAL","STOCKPALMA","STOCKEXTERNO","STOCK","STOCKWEB","UNIDADES","DISPONIBLE","DISPONIBLES"):
        total += _to_int(r.get(k))
    if total:
        return total
    for k, v in r.items():
        nk = _norm_key(k)
        if "stock" in nk or "dispon" in nk:
            total += _to_int(v)
    return total

def _normalize_image_url(url: str):
    if not url: return None
    s = str(url).strip()
    try: urlparse(s)
    except Exception: pass
    return s or None

def _desc_to_html(raw: str) -> str:
    if not raw: return ""
    txt = str(raw).replace("\r\n","\n").replace("\r","\n").strip()
    # Si ya parece HTML, respétalo
    if "<" in txt and ">" in txt:
        return txt
    # Viñetas por líneas o separadores comunes -> <br/>
    parts = [p.strip() for p in re.split(r"\s*[•\-]\s+|\n+", txt) if p.strip()]
    return "<br/>".join(parts) if parts else txt

def _read_csv_sniff(text: str) -> csv.DictReader:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except Exception:
        class _D: delimiter = ';'
        dialect = _D()
    return csv.DictReader(io.StringIO(text), dialect=dialect)

def _fetch_csv(app_key: str, mode="query", header_name: str = "X-Api-Key"):
    if not requests:
        raise RuntimeError("requests no disponible en el entorno.")
    params, headers = {}, {}
    if mode == "query":
        params["user"] = app_key
    elif mode == "header":
        headers[header_name] = app_key
    elif mode == "bearer":
        headers["Authorization"] = f"Bearer {app_key}"
    r = requests.get(CSV_EXT_URL, params=params, headers=headers, timeout=120)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text

# --------- category mapping (CSV: izquierda=origen, derecha=destino) ----------
import io as _mm_io, csv as _mm_csv, re as _mm_re, os as _mm_os, unicodedata as _mm_unic, difflib as _mm_diff

def _mm_norm_key(s: str) -> str:
    if s is None:
        return ""
    # normaliza espacios raros (NBSP), quita acentos, minúsculas, reemplaza & y /
    t = str(s).replace("\u00a0", " ").replace("\u2007", " ").replace("\u202f", " ")
    nfkd = _mm_unic.normalize("NFKD", t)
    t = "".join(ch for ch in nfkd if not _mm_unic.combining(ch)).lower()
    t = t.replace("&", " y ").replace("/", " / ")
    return _mm_re.sub(r"\s+", " ", "".join(ch for ch in t if ord(ch) < 128 or ch.isspace())).strip()

def _mm_csv_reader(text: str) -> _mm_csv.DictReader:
    sample = text[:4096]
    try:
        dialect = _mm_csv.Sniffer().sniff(sample, delimiters=";,|\t")
    except Exception:
        class _D: delimiter = ';'
        dialect = _D()
    return _mm_csv.DictReader(_mm_io.StringIO(text), dialect=dialect)

def _mm_read_file(path: str) -> str:
    last = None
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except Exception as e:
            last = e
    raise last

def _mm_pick_headers(fieldnames_low: dict):
    src_cands = [
        "categoría infortisa","categoria infortisa","infortisa",
        "categoría de producto","categoria de producto",
        "categoría","categoria","origen"
    ]
    dst_cands = [
        "categoría final","categoria final","final","destino",
        "mi categoría","mi categoria"
    ]
    src = next((fieldnames_low.get(k) for k in src_cands if fieldnames_low.get(k)), None)
    dst = next((fieldnames_low.get(k) for k in dst_cands if fieldnames_low.get(k)), None)
    if not src and dst:
        for orig in fieldnames_low.values():
            if orig and orig != dst:
                src = orig; break
    return src, dst

def _mm_load_cat_map(path: str) -> dict:
    if not path or not _mm_os.path.exists(path):
        return {}
    try:
        txt = _mm_read_file(path)
        rdr = _mm_csv_reader(txt)
        fl = { (c or "").strip().lower(): c for c in (rdr.fieldnames or []) }
        src, dst = _mm_pick_headers(fl)
        if not (src and dst):
            return {}
        mapping = {}
        for row in rdr:
            s = (row.get(src) or "").strip()
            d = (row.get(dst) or "").strip()
            if s:
                mapping[_mm_norm_key(s)] = d or s
        return mapping
    except Exception:
        return {}

def _mm_find_map(mapping: dict, src_text: str):
    if not mapping:
        return None
    key = _mm_norm_key(src_text)
    if key in mapping:
        return mapping[key]
    # prefijo/sufijo
    for k in mapping.keys():
        if key.startswith(k) or key.endswith(k) or k.startswith(key):
            return mapping[k]
    # fuzzy suave
    cands = _mm_diff.get_close_matches(key, mapping.keys(), n=1, cutoff=0.92)
    return mapping[cands[0]] if cands else None

# ------------------------------ entrypoints ------------------------------
def get_items(app_key=None, auth_mode="query", header_name="X-Api-Key",
              min_stock=1, limit=None, vendor_name=None, **kwargs):
    """
    Parámetros útiles en python_kwargs (Odoo):
      {
        "app_key": "...si no usas ENV...",
        "auth_mode": "query|header|bearer",
        "header_name": "Authorization-Token",
        "min_stock": 1,
        "limit": 500,
        "category_map_path": "/ruta/a/infortisa_categorias_final.csv",
        "vendor_name": "Infortisa"
      }
    """
    app_key = (app_key or os.getenv("INFORTISA_APP_KEY") or "").strip()
    if not app_key:
        raise RuntimeError("Falta APP KEY (INFORTISA_APP_KEY o parámetro).")

    try: min_stock = int(min_stock or 0)
    except Exception: min_stock = 0
    lim = int(limit) if (isinstance(limit, (int, str)) and str(limit).isdigit()) else None

    csv_text = _fetch_csv(app_key, mode=auth_mode, header_name=header_name)
    reader = _read_csv_sniff(csv_text)

    NAME = ['titulo','título','name','title']
    CODE = ['codigointerno','codigo','código','sku','ref','referencia','productcode','itemcode']
    BAR  = ['ean/upc','ean','barcode','código barras','codigo barras']
    IMG  = ['imagen','image','image_url','urlimagen','foto','picture','pictureurl']
    DESC = ['ficha','descripcion','descripción','description','desc']
    FAM1 = ['titulofamilia','familia']
    FAM2 = ['titulosubfamilia','subfamilia']
    FAM3 = ['tituloseccion','seccion','sección']
    PRICE = ['precio','pvd','pvp','precio venta','precioventa','precio_base','precio unitario','coste']
    URLP = ['product_url','url','web_url','link','enlace','urlproducto','url producto','pagina','página']

    _c = lambda r, cands: _col(r, cands)
    items = []
    for row in reader:
        try:
            name = _c(row, NAME)
            if not name:
                continue

            price = _to_float_es(_c(row, PRICE) or row.get("PRECIO"))
            stock_total = _sum_stock(row)
            if price <= 0 or stock_total < min_stock:
                continue

            sku = _c(row, CODE)
            barcode = _c(row, BAR)
            image_url = _normalize_image_url(_c(row, IMG))
            if not image_url:
                # política: sin imagen => descartar
                continue

            desc_html = _desc_to_html(_c(row, DESC))
            category = (_c(row, FAM2) or _c(row, FAM1) or _c(row, FAM3)) or None
            prod_url  = _c(row, URLP) or None

            # extras (si el CSV trae columnas de imágenes adicionales)
            raw_extra = (row.get('IMAGENES_ADICIONALES') or row.get('Imagenes_Adicionales') or
                         row.get('imagenes_adicionales') or row.get('AdditionalProductPictures') or '')
            extra_urls = []
            if raw_extra:
                parts = re.split(r'[|\n;, \t]+', str(raw_extra).strip())
                for u in parts:
                    u = (u or '').strip()
                    if not u: continue
                    if u.startswith('//'): u = 'https:' + u
                    if u.startswith(('http://','https://')) and u != image_url and u not in extra_urls:
                        extra_urls.append(u)

            item = {
                "name": name,
                "sku": sku or barcode,
                "cost": float(f"{price:.2f}"),
                "list_price": None,
                "barcode": barcode or None,
                "image_url": image_url,
                "category": category,
                "vendor_code": sku or None,
                "vendor_name": (vendor_name or "Infortisa").strip(),
                "vendor_stock": int(stock_total),
                "weight": _peso_from_row(row)
            }
            if prod_url:
                item['product_url'] = prod_url
            if desc_html:
                item["description_ecommerce"] = desc_html
                item["website_description"]   = desc_html
            if extra_urls:
                item["images"] = extra_urls
                item["gallery"] = extra_urls
                item["image_urls"] = extra_urls

            items.append(item)
            if lim and len(items) >= lim:
                break
        except Exception:
            continue

    # Mapeo de categorías (si se facilitó CSV)
    cat_map_path = kwargs.get("category_map_path") or kwargs.get("category_map_csv")
    mapping = _mm_load_cat_map(cat_map_path) if cat_map_path else {}
    if mapping:
        for it in items:
            src = it.get("category") or ""
            dst = _mm_find_map(mapping, src) or src
            it["category"] = dst
            it["public_category"] = dst

    return items

# Alias por compatibilidad
def get_items_mapped(**kwargs):
    return get_items(**kwargs)

# ========== [PATCH] CSV robusto ante ';' en entidades HTML ==========
# Si el proveedor no pone comillas en FICHA y hay entidades (&oacute;), el ';'
# se interpreta como separador. Para evitarlo, protegemos esos ';' antes de parsear.

import re as _vc_re, io as _vc_io, csv as _vc_csv

def _read_csv_sniff(text: str):
    """
    Reemplaza temporalmente ';' en entidades HTML (&xxxx;) por un marcador,
    parsea con separador ';' y luego restaura las entidades en cada celda.
    """
    if not isinstance(text, str):
        text = str(text or "")
    # protege &...;  (nombres o numéricas, p. ej. &#241;)
    safe = _vc_re.sub(r'&([A-Za-z0-9#]{1,20});', r'§E:\1§', text)

    rdr = _vc_csv.DictReader(_vc_io.StringIO(safe), delimiter=';')  # Infortisa usa ';'

    def _restore(row):
        out = {}
        for k, v in (row or {}).items():
            if isinstance(v, str):
                v = _vc_re.sub(r'§E:([A-Za-z0-9#]{1,20})§', r'&\1;', v)
            out[k] = v
        return out

    # devolvemos un iterador que restaura por fila (sin cargar todo en memoria)
    class _Iter:
        def __iter__(self_inner):
            for r in rdr:
                yield _restore(r)
    return _Iter()
# ========== [/PATCH] ==========
