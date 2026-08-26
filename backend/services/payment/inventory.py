"""Inventory reservation to prevent overselling."""

from models import db, CommunityProduct, StoreProduct


class InventoryError(ValueError):
    pass


def lock_product(product_id):
    return CommunityProduct.query.filter_by(id=product_id).with_for_update().first()


def lock_store_product(product_id):
    return StoreProduct.query.filter_by(id=product_id).with_for_update().first()


def sellable_quantity(product):
    if isinstance(product, StoreProduct) and product.quantity_available is None:
        return None
    return max(0, (product.quantity_available or 0) - (product.quantity_reserved or 0))


def reserve_stock(product, quantity):
    if isinstance(product, StoreProduct) and product.quantity_available is None:
        return
    if (product.quantity_available or 0) <= 0:
        raise InventoryError("Product is out of stock.")
    avail = sellable_quantity(product)
    if quantity > avail:
        raise InventoryError(f"Only {avail} unit(s) available.")
    product.quantity_reserved = (product.quantity_reserved or 0) + quantity
    if sellable_quantity(product) <= 0:
        product.status = "out_of_stock"
    db.session.flush()


def release_reserved_stock(product, quantity):
    if isinstance(product, StoreProduct) and product.quantity_available is None:
        return
    product.quantity_reserved = max(0, (product.quantity_reserved or 0) - quantity)
    if sellable_quantity(product) is not None and sellable_quantity(product) > 0 and product.status == "out_of_stock":
        product.status = "active" if isinstance(product, StoreProduct) else "available"
    db.session.flush()


def finalize_stock(product, quantity):
    """After successful payment: decrement available and reserved."""
    if isinstance(product, StoreProduct) and product.quantity_available is None:
        return
    product.quantity_available = max(0, (product.quantity_available or 0) - quantity)
    product.quantity_reserved = max(0, (product.quantity_reserved or 0) - quantity)
    avail = sellable_quantity(product)
    if avail is not None and avail <= 0 and (product.quantity_available or 0) <= 0:
        product.status = "out_of_stock"
    elif avail is not None and avail > 0 and product.status == "out_of_stock":
        product.status = "active" if isinstance(product, StoreProduct) else "available"
    db.session.flush()
