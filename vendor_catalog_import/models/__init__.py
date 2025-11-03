# -*- coding: utf-8 -*-

# --- MODELOS BASE ---
from . import vendor_catalog              # define 'vendor.catalog.config'
from . import product_template
from . import product_supplierinfo
from . import product_image
from . import settings

# --- PATCHES CONSERVADOS ---
from . import _infortisa_rest_patch       # Descripción e-commerce desde REST Infortisa
from . import _gallery_multi_images_patch # Galería extra robusta (derivaciones/scrape)
from . import _ecom_public_category_patch # Categorías públicas eCommerce
from . import _config_helpers
from . import _kwargs_inject_patch
