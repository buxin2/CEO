from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from models import Company, Employee, get_week_bounds
from routes.auth import login_required

admin_bp = Blueprint("admin", __name__)


def _parse_week_param():
    """Read an optional ?week_start=YYYY-MM-DD query param and return week bounds."""
    week_start_str = request.args.get("week_start")
    if week_start_str:
        try:
            ref = datetime.strptime(week_start_str, "%Y-%m-%d").date()
            return get_week_bounds(ref)
        except ValueError:
            pass
    return get_week_bounds()


@admin_bp.route("/api/dashboard")
@login_required
def api_dashboard():
    week_start, week_end = _parse_week_param()

    companies = Company.query.order_by(Company.name.asc()).all()

    total_companies = len(companies)
    total_employees = Employee.query.count()

    total_tasks = 0
    completed_tasks = 0

    company_list = []
    for c in companies:
        stats = c.get_week_stats(week_start, week_end)
        total_tasks += stats["total"]
        completed_tasks += stats["completed"]
        company_data = c.to_dict()
        company_data["stats"] = stats
        company_list.append(company_data)

    pending_tasks = total_tasks - completed_tasks
    completion_pct = round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    return jsonify({
        "summary": {
            "total_companies": total_companies,
            "total_employees": total_employees,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "completion_pct": completion_pct,
        },
        "companies": company_list,
        "week": {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "prev_week_start": (week_start - timedelta(days=7)).isoformat(),
            "next_week_start": (week_start + timedelta(days=7)).isoformat(),
        },
    })
