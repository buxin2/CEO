"""Public store customer accounts (email+password or phone+password)."""

import re
from datetime import datetime

from flask import current_app, request, session
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from models import db, StoreAccountHelpRequest, StoreCustomer, StoreCustomerNotice, StoreOrder

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
    if cid:
        row = StoreCustomer.query.get(cid)
        if row:
            return row
    token = (request.headers.get("X-Store-Token") or "").strip()
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        return None
    return customer_from_store_token(token)


def issue_store_token(customer_id):
    from itsdangerous import URLSafeTimedSerializer

    serializer = URLSafeTimedSerializer(str(current_app.config["SECRET_KEY"]), salt="store-customer-v1")
    return serializer.dumps({"id": int(customer_id)})


def customer_from_store_token(token):
    from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

    serializer = URLSafeTimedSerializer(str(current_app.config["SECRET_KEY"]), salt="store-customer-v1")
    try:
        data = serializer.loads(token, max_age=60 * 60 * 24 * 14)
    except (BadSignature, SignatureExpired, Exception):
        return None
    cid = (data or {}).get("id")
    if not cid:
        return None
    return StoreCustomer.query.get(cid)


def customer_auth_payload(customer):
    return {
        "customer": customer.to_dict(),
        "store_token": issue_store_token(customer.id),
        "unread_notices": unread_notice_count(customer),
    }


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
        raise ValueError("Enter your full name.")
    if not email:
        raise ValueError("Enter your email.")
    if not _email_ok(email):
        raise ValueError("Enter a valid email address.")
    if not phone:
        raise ValueError("Enter a valid phone number.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    if StoreCustomer.query.filter_by(email=email).first():
        raise ValueError("This email has already been used. Sign in instead.")
    if StoreCustomer.query.filter_by(phone=phone).first():
        raise ValueError("This phone number has already been used. Sign in instead.")
    customer = StoreCustomer(full_name=name[:255], email=email[:255], phone=phone[:32], has_password=True)
    customer.set_password(password)
    db.session.add(customer)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("This email or phone number has already been used. Sign in instead.")
    attach_orders_to_customer(customer)
    login_store_customer(customer)
    return customer


def login_with_email(email, password):
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("Enter your email.")
    if not _email_ok(email):
        raise ValueError("Enter a valid email address.")
    if not password:
        raise ValueError("Enter your password.")
    customer = StoreCustomer.query.filter_by(email=email).first()
    if not customer:
        raise ValueError("No account with this email. Create an account first.")
    if customer.google_sub and not customer.has_password:
        raise ValueError("This account uses Google. Click Sign in with Google.")
    if not customer.check_password(password):
        raise ValueError("This is the wrong password.")
    attach_orders_to_customer(customer)
    login_store_customer(customer)
    return customer


def login_with_phone(phone, password):
    raw = str(phone or "").strip()
    if not raw:
        raise ValueError("Enter your phone number.")
    phone = normalize_phone(raw)
    if not phone:
        raise ValueError("Enter a valid phone number.")
    if not password:
        raise ValueError("Enter your password.")
    customer = StoreCustomer.query.filter_by(phone=phone).first()
    if not customer:
        raise ValueError("No account with this phone number. Create an account first.")
    if customer.google_sub and not customer.has_password:
        raise ValueError("This account uses Google. Click Sign in with Google.")
    if not customer.check_password(password):
        raise ValueError("This is the wrong password.")
    attach_orders_to_customer(customer)
    login_store_customer(customer)
    return customer


def google_client_id():
    from flask import current_app

    return (current_app.config.get("GOOGLE_CLIENT_ID") or "").strip()


def login_with_google_credential(credential, nonce=None):
    import secrets

    client_id = google_client_id()
    if not client_id:
        raise ValueError("Google sign-in is not configured yet.")
    token = (credential or "").strip()
    if not token:
        raise ValueError("Google sign-in did not finish. Try again.")
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        info = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
    except Exception as exc:
        raise ValueError("Google sign-in failed. Try again.") from exc
    if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError("Google sign-in failed. Try again.")
    expected_nonce = (nonce or "").strip()
    if expected_nonce and info.get("nonce") and info.get("nonce") != expected_nonce:
        raise ValueError("Google sign-in expired. Try again.")
    email = (info.get("email") or "").strip().lower()
    if not email or not info.get("email_verified"):
        raise ValueError("Google did not share a verified email. Use another Google account.")
    sub = str(info.get("sub") or "").strip()
    if not sub:
        raise ValueError("Google sign-in failed. Try again.")
    name = (info.get("name") or email.split("@")[0]).strip()[:255]

    customer = StoreCustomer.query.filter_by(google_sub=sub).first()
    if not customer:
        customer = StoreCustomer.query.filter_by(email=email).first()
        if customer:
            customer.google_sub = sub
            if not (customer.full_name or "").strip():
                customer.full_name = name
        else:
            customer = StoreCustomer(
                full_name=name,
                email=email[:255],
                phone=None,
                google_sub=sub,
                has_password=False,
            )
            customer.set_password(secrets.token_urlsafe(32))
            db.session.add(customer)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Could not create this Google account. Try email sign-in.")
    attach_orders_to_customer(customer)
    login_store_customer(customer)
    return customer


def login_with_google_code(code, redirect_uri, code_verifier=""):
    import os

    import requests

    client_id = google_client_id()
    secret = (current_app.config.get("GOOGLE_CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()
    if not client_id:
        raise ValueError("Google sign-in is not configured yet.")
    if not secret:
        raise ValueError("Google phone sign-in needs GOOGLE_CLIENT_SECRET on the server (Render).")
    code = (code or "").strip()
    redirect_uri = (redirect_uri or "").strip()
    if not code or not redirect_uri:
        raise ValueError("Google sign-in did not finish. Try again.")
    payload = {
        "code": code,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    if secret:
        payload["client_secret"] = secret
    verifier = (code_verifier or "").strip()
    if verifier:
        payload["code_verifier"] = verifier
    try:
        resp = requests.post("https://oauth2.googleapis.com/token", data=payload, timeout=20)
        body = resp.json() if resp.content else {}
    except Exception as exc:
        raise ValueError("Google sign-in failed. Try again.") from exc
    jwt = (body.get("id_token") or "").strip()
    if not jwt:
        detail = str(body.get("error_description") or body.get("error") or "")
        if "client_secret" in detail.lower() or body.get("error") in ("invalid_client", "unauthorized_client"):
            raise ValueError("Google phone sign-in needs the Client secret on the server. Add GOOGLE_CLIENT_SECRET in Render.")
        raise ValueError(detail or "Google sign-in failed. Try again.")
    return login_with_google_credential(jwt)


def update_customer_phone(customer, phone):
    phone = normalize_phone(phone)
    if not phone:
        raise ValueError("Enter a valid phone number.")
    other = StoreCustomer.query.filter(StoreCustomer.phone == phone, StoreCustomer.id != customer.id).first()
    if other:
        raise ValueError("This phone number has already been used.")
    customer.phone = phone[:32]
    db.session.commit()
    return customer


def change_store_password(customer, current_password, new_password):
    if not current_password:
        raise ValueError("Enter the password you use now.")
    if not customer.check_password(current_password):
        raise ValueError("This is the wrong password. Use the password you sign in with now.")
    if len(new_password or "") < 6:
        raise ValueError("New password must be at least 6 characters.")
    if current_password == new_password:
        raise ValueError("Choose a different new password.")
    customer.set_password(new_password)
    customer.has_password = True
    db.session.commit()
    return customer


def create_customer_notice(customer, title, body, kind="message"):
    row = StoreCustomerNotice(
        store_customer_id=customer.id,
        title=(title or "Message from store admin")[:255],
        body=(body or "")[:4000],
        kind=(kind or "message")[:40],
    )
    db.session.add(row)
    db.session.commit()
    return row


def list_customer_notices(customer):
    return (
        StoreCustomerNotice.query.filter_by(store_customer_id=customer.id)
        .order_by(StoreCustomerNotice.created_at.desc())
        .limit(50)
        .all()
    )


def unread_notice_count(customer):
    if not customer:
        return 0
    return StoreCustomerNotice.query.filter_by(store_customer_id=customer.id, read_at=None).count()


def mark_notice_read(customer, notice_id):
    row = StoreCustomerNotice.query.filter_by(id=notice_id, store_customer_id=customer.id).first()
    if not row:
        raise ValueError("Message not found.")
    if not row.read_at:
        row.read_at = datetime.utcnow()
        db.session.commit()
    return row


def mark_all_notices_read(customer):
    rows = StoreCustomerNotice.query.filter_by(store_customer_id=customer.id, read_at=None).all()
    now = datetime.utcnow()
    for row in rows:
        row.read_at = now
    if rows:
        db.session.commit()
    return len(rows)


def find_customer_by_contact(email=None, phone=None):
    email = (email or "").strip().lower()
    if email:
        row = StoreCustomer.query.filter_by(email=email).first()
        if row:
            return row
    phone = normalize_phone(phone)
    if phone:
        return StoreCustomer.query.filter_by(phone=phone).first()
    return None


def list_store_customers(query=""):
    q = StoreCustomer.query.order_by(StoreCustomer.created_at.desc())
    text = (query or "").strip().lower()
    if text:
        like = f"%{text}%"
        q = q.filter(
            or_(
                func.lower(StoreCustomer.full_name).like(like),
                func.lower(StoreCustomer.email).like(like),
                StoreCustomer.phone.like(like),
            )
        )
    return q.limit(300).all()


def get_store_customer(customer_id):
    row = StoreCustomer.query.get(customer_id)
    if not row:
        raise ValueError("User not found.")
    return row


def admin_set_customer_password(customer_id, password, extra_message=""):
    if len(password or "") < 6:
        raise ValueError("Password must be at least 6 characters.")
    customer = get_store_customer(customer_id)
    customer.set_password(password)
    customer.has_password = True
    note = (extra_message or "").strip()
    body = note + ("\n\n" if note else "")
    body += (
        "Your new password is: "
        + password
        + "\n\nSign in with this password. If you want to change it, enter this password first, then choose a new one."
    )
    db.session.add(StoreCustomerNotice(
        store_customer_id=customer.id,
        title="New password from store admin",
        body=body[:4000],
        kind="password",
    ))
    db.session.commit()
    return customer


def admin_message_customer(customer_id, title, body):
    customer = get_store_customer(customer_id)
    text = (body or "").strip()
    if not text:
        raise ValueError("Write a message for the customer.")
    return create_customer_notice(customer, title or "Message from store admin", text, "message")


def create_help_request(data):
    name = (data.get("full_name") or data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    message = (data.get("message") or "").strip()
    if not name:
        raise ValueError("Enter your name.")
    if not email and not phone:
        raise ValueError("Add your email or phone number so we can find your account.")
    if email and not _email_ok(email.lower()):
        raise ValueError("Enter a valid email address, or leave email blank and use your phone.")
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


def help_request_dict(row):
    data = row.to_dict()
    matched = find_customer_by_contact(row.email, row.phone)
    if matched:
        data["customer"] = matched.to_dict(include_admin=True)
    return data


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
