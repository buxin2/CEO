"""Public store customer accounts (email+password or phone+password)."""

import re

from flask import session
from sqlalchemy import func, or_

from models import db, StoreAccountHelpRequest, StoreCustomer, StoreOrder

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_phone(raw):
    text = str(raw or "").strip()
    kept = "".join(ch for ch in text if ch.isdigit() or ch == "+")
    digits = "".join(ch for ch in kept if ch.isdigit())
    if len(digits) < 7:
        return ""
    if kept.startswith("+"):
        return "+" + digits
    return digits


def _email_ok(email):
    email = (email or "").strip().lower()
    return bool(_EMAIL_RE.match(email))


def current_store_customer():
    cid = session.get("store_customer_id")
    if not cid:
        return None
    return StoreCustomer.query.get(cid)


def login_store_customer(customer):
    session["store_customer_id"] = customer.id
    session.permanent = True


def logout_store_customer():
    session.pop("store_customer_id", None)


def attach_orders_to_customer(customer):
    q = StoreOrder.query.filter(StoreOrder.store_customer_id.is_(None))
    email = (customer.email or "").strip().lower()
    phone = customer.phone or ""
    rows = q.filter(
        or_(
            func.lower(StoreOrder.customer_email) == email,
            StoreOrder.customer_phone == phone,
        )
    ).all()
    for order in rows:
        order.store_customer_id = customer.id
    if rows:
        db.session.commit()
    return len(rows)


def register_store_customer(data):
    name = (data.get("full_name") or data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = normalize_phone(data.get("phone"))
    password = data.get("password") or ""
    if not name:
        raise ValueError("Full name is required.")
    if not _email_ok(email):
        raise ValueError("A valid email is required.")
    if not phone:
        raise ValueError("A valid phone number is required.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    if StoreCustomer.query.filter_by(email=email).first():
        raise ValueError("An account with this email already exists. Sign in instead.")
    if StoreCustomer.query.filter_by(phone=phone).first():
        raise ValueError("An account with this phone number already exists. Sign in instead.")
    customer = StoreCustomer(full_name=name[:255], email=email[:255], phone=phone[:32])
    customer.set_password(password)
    db.session.add(customer)
    db.session.commit()
    attach_orders_to_customer(customer)
    login_store_customer(customer)
    return customer


def login_with_email(email, password):
    email = (email or "").strip().lower()
    if not _email_ok(email) or not password:
        raise ValueError("Email and password are required.")
    customer = StoreCustomer.query.filter_by(email=email).first()
    if not customer or not customer.check_password(password):
        raise ValueError("Invalid email or password.")
    attach_orders_to_customer(customer)
    login_store_customer(customer)
    return customer


def login_with_phone(phone, password):
    phone = normalize_phone(phone)
    if not phone or not password:
        raise ValueError("Phone number and password are required.")
    customer = StoreCustomer.query.filter_by(phone=phone).first()
    if not customer or not customer.check_password(password):
        raise ValueError("Invalid phone number or password.")
    attach_orders_to_customer(customer)
    login_store_customer(customer)
    return customer


def create_help_request(data):
    name = (data.get("full_name") or data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    message = (data.get("message") or "").strip()
    if not name:
        raise ValueError("Your name is required.")
    if not email and not phone:
        raise ValueError("Add your email or phone number so we can find your account.")
    if len(message) < 8:
        raise ValueError("Tell us what you need help with (at least a short sentence).")
    row = StoreAccountHelpRequest(
        full_name=name[:255],
        email=email[:255],
        phone=phone[:64],
        message=message[:4000],
        status="pending",
    )
    db.session.add(row)
    db.session.commit()
    return row


def list_help_requests():
    return StoreAccountHelpRequest.query.order_by(StoreAccountHelpRequest.created_at.desc()).limit(200).all()


def mark_help_request(request_id, status):
    row = StoreAccountHelpRequest.query.get(request_id)
    if not row:
        raise ValueError("Request not found.")
    if status not in ("pending", "done"):
        raise ValueError("Invalid status.")
    row.status = status
    db.session.commit()
    return row


def list_customer_orders(customer):
    return (
        StoreOrder.query.filter_by(store_customer_id=customer.id)
        .order_by(StoreOrder.created_at.desc())
        .all()
    )
