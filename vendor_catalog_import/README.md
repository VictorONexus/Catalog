# vendor_catalog_import

Updates includes:
1. download of images via background thread, this makes the process more faster. For product images, the function below was added for this purpose.

   ```def _update_product_image_now(self, tmpl_id, url):
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
        EXECUTOR.submit(task1, tmpl_id, url, self.env.registry)```
