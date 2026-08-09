from flask import current_app


def frontend_url(path=""):
    """Build a URL on the deployed frontend (GitHub Pages)."""
    base = current_app.config["FRONTEND_URL"].rstrip("/")
    if not path:
        return base
    return f"{base}/{path.lstrip('/')}"


def task_link_for_token(token):
    """Employee task link served by the static frontend."""
    return frontend_url(f"task.html?token={token}")


def group_link_for_token(token):
    """Company group chat link served by the static frontend."""
    return frontend_url(f"group.html?token={token}")


def create_group_for_company(company):
    """Create the company group chat (one per company)."""
    from models import CompanyGroup

    existing = CompanyGroup.query.filter_by(company_id=company.id).first()
    if existing:
        return existing
    group = CompanyGroup(company_id=company.id)
    return group
