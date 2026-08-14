"""Inventory reservation to prevent overselling."""

from models import db, CommunityProduct


class InventoryError(ValueError):
    pass


def lock_product(product_id):
    return CommunityProduct.query.filter_by(id=product_id).with_for_update().first()


def sellable_quantity(product):
    return max(0, (product.quantity_available or 0) - (product.quantity_reserved or 0))


def reserve_stock(product, quantity):
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
    product.quantity_reserved = max(0, (product.quantity_reserved or 0) - quantity)
    if sellable_quantity(product) > 0 and product.status == "out_of_stock":
        product.status = "available"
    db.session.flush()


def finalize_stock(product, quantity):
    """After successful payment: decrement available and reserved."""
    product.quantity_available = max(0, (product.quantity_available or 0) - quantity)
    product.quantity_reserved = max(0, (product.quantity_reserved or 0) - quantity)
    if sellable_quantity(product) <= 0 and (product.quantity_available or 0) <= 0:
        product.status = "out_of_stock"
    elif sellable_quantity(product) > 0 and product.status == "out_of_stock":
        product.status = "available"
    db.session.flush()
