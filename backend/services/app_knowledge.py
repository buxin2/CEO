"""Full live app knowledge text for the AI assistant system prompt."""

from datetime import date

from models import Company, Employee, Product, Service, get_week_bounds
from routes.catalog import _earnings_summary

_MAX_KNOWLEDGE_CHARS = 14000
_DESC_CLIP = 200
_PRODUCT_DESC_CLIP = 120


def _clip(text, max_len):
    t = (text or "").strip().replace("\n", " ")
    if len(t) <= max_len:
        return t
    return t[:max_len].rstrip() + "…"


def _employee_week_label(stats):
    total = stats.get("total") or 0
    pending = stats.get("pending") or 0
    completed = stats.get("completed") or 0
    pct = stats.get("completion_pct") or 0
    if total == 0:
        return "no tasks assigned this week"
    if pending == 0:
        return f"all {total} tasks completed — doing well"
    if pct >= 70:
        return f"{completed}/{total} tasks done — progressing"
    return f"{completed}/{total} tasks done, {pending} pending — needs follow-up"


def build_ai_app_knowledge_text():
    """
    Build a comprehensive, compact snapshot of everything in the admin app
    so Chat mode can advise without claiming missing data.
    """
    today = date.today()
    week_start, week_end = get_week_bounds(today)

    lines = [
        f"Date: {today.isoformat()} · App week (Mon–Sun): {week_start.isoformat()} to {week_end.isoformat()}",
        "App pages: Dashboard, Companies, Communities, AI Assistant (Chat/Manage), Mentor, "
        "My Timetable, News, and per-company Employees, Tasks, Products, Services, Earnings, Group chat.",
        "",
    ]

    companies = Company.query.order_by(Company.name.asc()).all()
    total_pending = 0

    for company in companies:
        stats = company.get_week_stats(week_start, week_end)
        total_pending += stats.get("pending") or 0
        earnings = _earnings_summary(company.id)

        lines.append(f"### {company.name}")
        if company.description:
            lines.append(f"About: {_clip(company.description, _DESC_CLIP)}")

        lines.append(
            f"Company tasks this week: {stats.get('completed', 0)}/{stats.get('total', 0)} completed, "
            f"{stats.get('pending', 0)} pending."
        )
        lines.append(
            f"Earnings: today {earnings['today']}, this week {earnings['this_week']}, "
            f"this month {earnings['this_month']}, all-time {earnings['total']}."
        )

        employees = company.employees.order_by(Employee.name.asc()).all()
        if employees:
            lines.append("Employees (name · role · task progress this week):")
            for emp in employees:
                es = emp.get_week_stats(week_start, week_end)
                role = emp.position or "no role set"
                lines.append(f"  • {emp.name} · {role} · {_employee_week_label(es)}")
        else:
            lines.append("Employees: none")

        products = company.products.order_by(Product.name.asc()).all()
        if products:
            lines.append("Products:")
            for prod in products:
                extra = f" — {_clip(prod.description, _PRODUCT_DESC_CLIP)}" if prod.description else ""
                lines.append(f"  • {prod.name}{extra}")
        else:
            lines.append("Products: none listed yet")

        services = company.services.order_by(Service.name.asc()).all()
        if services:
            lines.append("Services:")
            for svc in services:
                extra = f" — {_clip(svc.description, _PRODUCT_DESC_CLIP)}" if svc.description else ""
                lines.append(f"  • {svc.name}{extra}")
        else:
            lines.append("Services: none listed yet")

        lines.append("")

    try:
        from services.community_service import community_ai_summary

        lines.append(community_ai_summary())
        lines.append("")
    except Exception:
        pass

    lines.insert(
        3,
        f"Totals: {len(companies)} companies · {Employee.query.count()} employees · "
        f"{total_pending} pending tasks app-wide this week.",
    )

    text = "\n".join(lines)
    if len(text) > _MAX_KNOWLEDGE_CHARS:
        return _build_compressed_knowledge(companies, week_start, week_end, today)
    return text


def _build_compressed_knowledge(companies, week_start, week_end, today):
    """Smaller snapshot if the full text would exceed token limits."""
    lines = [
        f"Date: {today.isoformat()} · Week: {week_start.isoformat()} to {week_end.isoformat()}",
        f"Companies ({len(companies)}):",
    ]
    for company in companies:
        stats = company.get_week_stats(week_start, week_end)
        earn = _earnings_summary(company.id)
        emp_names = [
            f"{e.name} ({e.position or '?'})"
            for e in company.employees.order_by(Employee.name.asc()).all()
        ]
        prod_names = [p.name for p in company.products.order_by(Product.name.asc()).all()]
        svc_names = [s.name for s in company.services.order_by(Service.name.asc()).all()]
        lines.append(
            f"- {company.name}: employees [{', '.join(emp_names) or 'none'}]; "
            f"products [{', '.join(prod_names) or 'none'}]; "
            f"services [{', '.join(svc_names) or 'none'}]; "
            f"tasks {stats.get('completed', 0)}/{stats.get('total', 0)}; "
            f"earnings week {earn['this_week']}."
        )
    return "\n".join(lines)
