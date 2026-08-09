"""Products, services, and earnings scoped to a company."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from models import db, Company, Employee, Product, Service, Earning, get_week_bounds
from routes.auth import login_required

catalog_bp = Blueprint("catalog", __name__)


def _get_company(company_id):
    company = Company.query.get(company_id)
    if not company:
        return None, (jsonify({"error": "Company not found."}), 404)
    return company, None


def _parse_amount(value):
    if value is None:
        return None, "Amount is required."
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None, "Amount must be a valid number."
    if amount <= 0:
        return None, "Amount must be greater than zero."
    return amount, None


def _parse_date(value, default=None):
    if not value:
        return default, None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date(), None
    except ValueError:
        return None, "Date must be YYYY-MM-DD."


def _earnings_summary(company_id):
    today = date.today()
    week_start, week_end = get_week_bounds(today)
    month_start = today.replace(day=1)

    def _sum(*extra_filters):
        q = db.session.query(func.coalesce(func.sum(Earning.amount), 0)).filter(
            Earning.company_id == company_id
        )
        for f in extra_filters:
            q = q.filter(f)
        return float(q.scalar() or 0)

    return {
        "today": _sum(Earning.earned_date == today),
        "this_week": _sum(
            Earning.earned_date >= week_start,
            Earning.earned_date <= week_end,
        ),
        "this_month": _sum(
            Earning.earned_date >= month_start,
            Earning.earned_date <= today,
        ),
        "total": _sum(),
    }


# --- Products ---


@catalog_bp.route("/api/companies/<int:company_id>/products", methods=["GET"])
@login_required
def list_products(company_id):
    company, err = _get_company(company_id)
    if err:
        return err
    items = company.products.order_by(Product.name.asc()).all()
    return jsonify([p.to_dict() for p in items])


@catalog_bp.route("/api/companies/<int:company_id>/products", methods=["POST"])
@login_required
def create_product(company_id):
    company, err = _get_company(company_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    if not name:
        return jsonify({"error": "Product name is required."}), 400

    product = Product(company_id=company.id, name=name, description=description)
    db.session.add(product)
    db.session.commit()
    return jsonify(product.to_dict()), 201


@catalog_bp.route("/api/companies/<int:company_id>/products/<int:product_id>", methods=["PUT"])
@login_required
def update_product(company_id, product_id):
    company, err = _get_company(company_id)
    if err:
        return err

    product = Product.query.filter_by(id=product_id, company_id=company.id).first()
    if not product:
        return jsonify({"error": "Product not found."}), 404

    data = request.get_json(silent=True) or {}
    if data.get("name") is not None:
        name = data["name"].strip()
        if not name:
            return jsonify({"error": "Product name cannot be empty."}), 400
        product.name = name
    if data.get("description") is not None:
        product.description = data["description"].strip()

    db.session.commit()
    return jsonify(product.to_dict())


@catalog_bp.route("/api/companies/<int:company_id>/products/<int:product_id>", methods=["DELETE"])
@login_required
def delete_product(company_id, product_id):
    company, err = _get_company(company_id)
    if err:
        return err

    product = Product.query.filter_by(id=product_id, company_id=company.id).first()
    if not product:
        return jsonify({"error": "Product not found."}), 404

    db.session.delete(product)
    db.session.commit()
    return jsonify({"success": True})


# --- Services ---


@catalog_bp.route("/api/companies/<int:company_id>/services", methods=["GET"])
@login_required
def list_services(company_id):
    company, err = _get_company(company_id)
    if err:
        return err
    items = company.services.order_by(Service.name.asc()).all()
    return jsonify([s.to_dict() for s in items])


@catalog_bp.route("/api/companies/<int:company_id>/services", methods=["POST"])
@login_required
def create_service(company_id):
    company, err = _get_company(company_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    if not name:
        return jsonify({"error": "Service name is required."}), 400

    service = Service(company_id=company.id, name=name, description=description)
    db.session.add(service)
    db.session.commit()
    return jsonify(service.to_dict()), 201


@catalog_bp.route("/api/companies/<int:company_id>/services/<int:service_id>", methods=["PUT"])
@login_required
def update_service(company_id, service_id):
    company, err = _get_company(company_id)
    if err:
        return err

    service = Service.query.filter_by(id=service_id, company_id=company.id).first()
    if not service:
        return jsonify({"error": "Service not found."}), 404

    data = request.get_json(silent=True) or {}
    if data.get("name") is not None:
        name = data["name"].strip()
        if not name:
            return jsonify({"error": "Service name cannot be empty."}), 400
        service.name = name
    if data.get("description") is not None:
        service.description = data["description"].strip()

    db.session.commit()
    return jsonify(service.to_dict())


@catalog_bp.route("/api/companies/<int:company_id>/services/<int:service_id>", methods=["DELETE"])
@login_required
def delete_service(company_id, service_id):
    company, err = _get_company(company_id)
    if err:
        return err

    service = Service.query.filter_by(id=service_id, company_id=company.id).first()
    if not service:
        return jsonify({"error": "Service not found."}), 404

    db.session.delete(service)
    db.session.commit()
    return jsonify({"success": True})


# --- Earnings ---


@catalog_bp.route("/api/companies/<int:company_id>/earnings", methods=["GET"])
@login_required
def list_earnings(company_id):
    company, err = _get_company(company_id)
    if err:
        return err

    earnings = (
        Earning.query.filter_by(company_id=company.id)
        .order_by(Earning.earned_date.desc(), Earning.created_at.desc())
        .all()
    )
    today_earnings = [e for e in earnings if e.earned_date == date.today()]

    return jsonify({
        "summary": _earnings_summary(company.id),
        "today_breakdown": [e.to_dict(include_employee=True) for e in today_earnings],
        "records": [e.to_dict(include_employee=True) for e in earnings],
    })


@catalog_bp.route("/api/companies/<int:company_id>/earnings", methods=["POST"])
@login_required
def create_earning(company_id):
    company, err = _get_company(company_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    employee_id = data.get("employee_id")
    employee_name = (data.get("employee_name") or "").strip()

    employee = None
    if employee_id:
        employee = Employee.query.filter_by(id=employee_id, company_id=company.id).first()
    elif employee_name:
        matches = [
            e for e in company.employees.all()
            if e.name.lower() == employee_name.lower()
            or employee_name.lower() in e.name.lower()
        ]
        if len(matches) == 1:
            employee = matches[0]
        elif len(matches) > 1:
            return jsonify({"error": f"Multiple employees match '{employee_name}'."}), 400

    if not employee:
        return jsonify({"error": "Employee not found in this company."}), 400

    amount, amount_err = _parse_amount(data.get("amount"))
    if amount_err:
        return jsonify({"error": amount_err}), 400

    earned_date, date_err = _parse_date(data.get("earned_date"), default=date.today())
    if date_err:
        return jsonify({"error": date_err}), 400

    note = (data.get("note") or "").strip()
    earning = Earning(
        company_id=company.id,
        employee_id=employee.id,
        amount=amount,
        earned_date=earned_date,
        note=note,
    )
    db.session.add(earning)
    db.session.commit()

    result = earning.to_dict(include_employee=True)
    result["summary"] = _earnings_summary(company.id)
    return jsonify(result), 201


@catalog_bp.route("/api/companies/<int:company_id>/earnings/<int:earning_id>", methods=["PUT"])
@login_required
def update_earning(company_id, earning_id):
    company, err = _get_company(company_id)
    if err:
        return err

    earning = Earning.query.filter_by(id=earning_id, company_id=company.id).first()
    if not earning:
        return jsonify({"error": "Earning not found."}), 404

    data = request.get_json(silent=True) or {}

    if data.get("employee_id") is not None:
        employee = Employee.query.filter_by(
            id=data["employee_id"], company_id=company.id
        ).first()
        if not employee:
            return jsonify({"error": "Employee not found in this company."}), 400
        earning.employee_id = employee.id

    if data.get("amount") is not None:
        amount, amount_err = _parse_amount(data.get("amount"))
        if amount_err:
            return jsonify({"error": amount_err}), 400
        earning.amount = amount

    if data.get("earned_date") is not None:
        earned_date, date_err = _parse_date(data.get("earned_date"))
        if date_err:
            return jsonify({"error": date_err}), 400
        earning.earned_date = earned_date

    if data.get("note") is not None:
        earning.note = data["note"].strip()

    db.session.commit()
    result = earning.to_dict(include_employee=True)
    result["summary"] = _earnings_summary(company.id)
    return jsonify(result)


@catalog_bp.route("/api/companies/<int:company_id>/earnings/<int:earning_id>", methods=["DELETE"])
@login_required
def delete_earning(company_id, earning_id):
    company, err = _get_company(company_id)
    if err:
        return err

    earning = Earning.query.filter_by(id=earning_id, company_id=company.id).first()
    if not earning:
        return jsonify({"error": "Earning not found."}), 404

    db.session.delete(earning)
    db.session.commit()
    return jsonify({"success": True, "summary": _earnings_summary(company.id)})
