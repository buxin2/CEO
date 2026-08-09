"""Build application snapshot for AI timetable planning."""

from datetime import date, timedelta

from models import (
    Company,
    Employee,
    Task,
    Product,
    Service,
    Earning,
    TimetableItem,
    PlannerGoal,
    get_week_bounds,
)
from routes.catalog import _earnings_summary


def period_keys_for(reference=None):
    ref = reference or date.today()
    week_start, week_end = get_week_bounds(ref)
    return {
        "daily": ref.isoformat(),
        "weekly": week_start.isoformat(),
        "monthly": ref.strftime("%Y-%m"),
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
    }


def build_planner_snapshot(reference_date=None):
    """Aggregate live app data for AI decision-making."""
    today = reference_date or date.today()
    keys = period_keys_for(today)
    week_start, week_end = get_week_bounds(today)

    companies_data = []
    for company in Company.query.order_by(Company.name.asc()).all():
        stats = company.get_week_stats(week_start, week_end)
        earnings = _earnings_summary(company.id)
        pending_employees = []
        for emp in company.employees:
            pending = emp.tasks.filter(
                Task.week_start == week_start,
                Task.week_end == week_end,
                Task.status == "pending",
            ).count()
            if pending:
                pending_employees.append({"name": emp.name, "pending_tasks": pending})

        companies_data.append({
            "id": company.id,
            "name": company.name,
            "employee_count": company.employees.count(),
            "products_count": company.products.count(),
            "services_count": company.services.count(),
            "week_task_stats": stats,
            "earnings": earnings,
            "employees_with_pending_tasks": pending_employees,
            "has_group": company.group is not None,
        })

    # Recent timetable completion patterns (last 7 days)
    week_ago = today - timedelta(days=7)
    recent_items = TimetableItem.query.filter(
        TimetableItem.plan_date >= week_ago,
        TimetableItem.plan_date <= today,
    ).all()
    recent_total = len(recent_items)
    recent_done = len([i for i in recent_items if i.completed])
    completion_rate = round((recent_done / recent_total) * 100) if recent_total else None

    goals = {
        "monthly": [
            g.to_dict()
            for g in PlannerGoal.query.filter_by(
                scope="monthly", period_key=keys["monthly"]
            ).order_by(PlannerGoal.position.asc()).all()
        ],
        "weekly": [
            g.to_dict()
            for g in PlannerGoal.query.filter_by(
                scope="weekly", period_key=keys["weekly"]
            ).order_by(PlannerGoal.position.asc()).all()
        ],
        "daily": [
            g.to_dict()
            for g in PlannerGoal.query.filter_by(
                scope="daily", period_key=keys["daily"]
            ).order_by(PlannerGoal.position.asc()).all()
        ],
    }

    return {
        "reference_date": today.isoformat(),
        "period_keys": keys,
        "companies": companies_data,
        "totals": {
            "companies": len(companies_data),
            "pending_tasks_this_week": sum(
                c["week_task_stats"]["pending"] for c in companies_data
            ),
            "earnings_today_all_companies": sum(
                c["earnings"]["today"] for c in companies_data
            ),
        },
        "goals": goals,
        "recent_timetable_completion_rate_pct": completion_rate,
        "recent_timetable_items_tracked": recent_total,
    }
