"""Daily opportunity report generation, storage, and group distribution."""

import hashlib
import json
import threading
from datetime import datetime, timedelta

from flask import current_app

from models import (
    db,
    Company,
    GroupMessage,
    OpportunityItem,
    OpportunityReport,
    OpportunityUserState,
)
from services.app_knowledge import build_ai_app_knowledge_text
from services.app_time import app_today, parse_date_iso
from services.opportunity_ai import (
    build_ai_recommendation,
    chat_about_opportunities,
    extract_opportunities_for_venture,
    parse_optional_date,
)
from services.opportunity_search import collect_venture_search_results, search_web
from services.opportunity_ventures import VENTURES, venture_meta
from services.planner_service import create_timetable_item
from utils import create_group_for_company

_generating_lock = threading.Lock()
_is_generating = False


def match_company_for_venture(venture_key):
    venture = next((v for v in VENTURES if v["key"] == venture_key), None)
    if not venture:
        return None
    patterns = venture.get("company_patterns") or []
    companies = Company.query.order_by(Company.name.asc()).all()
    for company in companies:
        name_lower = company.name.lower()
        for pattern in patterns:
            if pattern in name_lower:
                return company.id
    return None


def _dedupe_key(title, url):
    raw = f"{(title or '').strip().lower()}|{(url or '').strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _recent_dedupe_keys(days=14):
    cutoff = app_today() - timedelta(days=days)
    keys = set()
    reports = OpportunityReport.query.filter(OpportunityReport.report_date >= cutoff).all()
    for report in reports:
        for item in report.opportunities:
            if item.dedupe_key:
                keys.add(item.dedupe_key)
    return keys


def get_report_for_date(report_date):
    return OpportunityReport.query.filter_by(report_date=report_date).first()


def list_report_dates(limit=60):
    rows = (
        OpportunityReport.query.filter_by(status="complete")
        .order_by(OpportunityReport.report_date.desc())
        .limit(limit)
        .all()
    )
    return [r.report_date.isoformat() for r in rows]


def generation_status():
    today = app_today()
    report = get_report_for_date(today)
    return {
        "today": today.isoformat(),
        "is_generating": _is_generating,
        "report": report.to_dict(include_counts=True) if report else None,
    }


def post_to_company_group(company_id, content, admin_id):
    company = Company.query.get(company_id)
    if not company:
        return False
    if not company.group:
        group = create_group_for_company(company)
        db.session.add(group)
        db.session.commit()
    group = company.group
    if not group:
        return False
    msg = GroupMessage(
        group_id=group.id,
        admin_id=admin_id,
        content=content.strip(),
    )
    db.session.add(msg)
    db.session.commit()
    return True


def _format_group_alert(item, venture):
    emoji = venture.get("emoji", "📰")
    type_meta = venture_meta(item.venture_key).get("type_labels", {})
    type_label = type_meta.get(item.opportunity_type, item.opportunity_type)
    lines = [
        f"{emoji} **Opportunity Alert**",
        f"**{item.title}**",
        f"Type: {type_label}",
    ]
    if item.deadline_date:
        lines.append(f"⏰ Deadline: {item.deadline_date.isoformat()}")
    if item.why_matters:
        lines.append(item.why_matters[:400])
    if item.apply_url:
        lines.append(f"👉 Apply: {item.apply_url}")
    if item.source_url:
        lines.append(f"🔗 Details: {item.source_url}")
    return "\n".join(lines)


def _post_top_to_groups(items, admin_id, max_per_venture=2):
    by_venture = {}
    for item in items:
        if item.priority != "high" or not item.verified or item.uncertain:
            continue
        bucket = by_venture.setdefault(item.venture_key, [])
        if len(bucket) < max_per_venture:
            bucket.append(item)

    for venture_key, venture_items in by_venture.items():
        venture = venture_meta(venture_key)
        company_id = match_company_for_venture(venture_key)
        if not company_id:
            continue
        for item in venture_items:
            if item.posted_to_group:
                continue
            content = _format_group_alert(item, venture)
            if post_to_company_group(company_id, content, admin_id):
                item.posted_to_group = True
    db.session.commit()


def generate_daily_report(report_date=None, admin_id=None, force=False):
    """Generate full daily opportunity report (sync)."""
    global _is_generating

    if report_date is None:
        report_date = app_today()

    with _generating_lock:
        if _is_generating:
            return get_report_for_date(report_date)
        _is_generating = True

    report = get_report_for_date(report_date)
    if report and report.status == "complete" and not force:
        with _generating_lock:
            _is_generating = False
        return report

    if not report:
        report = OpportunityReport(report_date=report_date, status="generating")
        db.session.add(report)
        db.session.commit()
    else:
        report.status = "generating"
        report.error_message = ""
        OpportunityItem.query.filter_by(report_id=report.id).delete()
        db.session.commit()

    try:
        app_knowledge = build_ai_app_knowledge_text()
        recent_keys = _recent_dedupe_keys()
        all_items = []

        for venture in VENTURES:
            company_id = match_company_for_venture(venture["key"])
            company = Company.query.get(company_id) if company_id else None
            company_ctx = f"Venture: {venture['label']}"
            if company:
                company_ctx += f"\nCompany in app: {company.name}\n{company.description or ''}"

            search_results = collect_venture_search_results(venture)
            ai_data = extract_opportunities_for_venture(
                venture["key"], search_results, company_ctx + "\n" + app_knowledge[:2000]
            )

            for raw in ai_data.get("opportunities") or []:
                src_url = (raw.get("source_url") or "").strip()
                apply_url = (raw.get("apply_url") or "").strip()
                key = _dedupe_key(raw.get("title"), apply_url or src_url)
                if key in recent_keys:
                    continue

                priority = (raw.get("priority") or "medium").lower()
                if priority not in ("high", "medium", "low"):
                    priority = "medium"

                opp_type = (raw.get("opportunity_type") or "other").lower()
                item = OpportunityItem(
                    report_id=report.id,
                    venture_key=venture["key"],
                    company_id=company_id,
                    title=(raw.get("title") or "Opportunity")[:500],
                    summary=(raw.get("summary") or "")[:2000],
                    why_matters=(raw.get("why_matters") or "")[:2000],
                    opportunity_type=opp_type,
                    priority=priority,
                    source_name=(raw.get("source_name") or "")[:255],
                    source_url=src_url[:1000],
                    apply_url=apply_url[:1000],
                    apply_label=(raw.get("apply_label") or "Learn More")[:80],
                    published_date=parse_optional_date(raw.get("published_date")),
                    deadline_date=parse_optional_date(raw.get("deadline_date")),
                    region=(raw.get("region") or "")[:255],
                    eligibility=(raw.get("eligibility") or "")[:2000],
                    verified=bool(raw.get("verified", True)),
                    uncertain=bool(raw.get("uncertain", False)),
                    dedupe_key=key,
                )
                db.session.add(item)
                all_items.append(item)
                recent_keys.add(key)

        db.session.flush()
        items = list(report.opportunities)
        recommendation = build_ai_recommendation(report_date, items, app_knowledge)

        counts = {}
        high_count = 0
        for v in VENTURES:
            v_items = [i for i in items if i.venture_key == v["key"]]
            counts[v["key"]] = len(v_items)
        for i in items:
            if i.priority == "high":
                high_count += 1

        top_titles = [
            i.title for i in sorted(
                items,
                key=lambda x: (0 if x.priority == "high" else 1 if x.priority == "medium" else 2),
            )[:5]
        ]

        summary = {
            "total": len(items),
            "high_priority": high_count,
            "by_venture": counts,
            "top_titles": top_titles,
        }

        report.summary_json = json.dumps(summary)
        report.ai_recommendation = recommendation
        report.status = "complete"
        report.generated_at = datetime.utcnow()
        db.session.commit()

        if admin_id:
            _post_top_to_groups(items, admin_id)
        else:
            from models import Admin

            first_admin = Admin.query.order_by(Admin.id.asc()).first()
            if first_admin:
                _post_top_to_groups(items, first_admin.id)

        return report
    except Exception as exc:
        current_app.logger.exception("Daily opportunity report failed")
        report.status = "failed"
        report.error_message = str(exc)[:500]
        db.session.commit()
        raise
    finally:
        with _generating_lock:
            _is_generating = False


def trigger_generate_async(report_date=None, admin_id=None, force=False):
    """Background generation for slow Render cold starts."""
    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            try:
                generate_daily_report(report_date, admin_id=admin_id, force=force)
            except Exception:
                pass

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def ensure_today_report(admin_id=None):
    today = app_today()
    report = get_report_for_date(today)
    if report and report.status == "complete":
        return report
    if report and report.status == "generating" and _is_generating:
        return report
    if not _is_generating:
        trigger_generate_async(today, admin_id=admin_id)
    return report or get_report_for_date(today)


def filter_opportunities(
    report,
    venture=None,
    opp_type=None,
    priority=None,
    admin_id=None,
    include_not_relevant=False,
):
    items = list(report.opportunities.all())
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda i: (priority_rank.get(i.priority, 9), i.id))

    if venture and venture != "all":
        items = [i for i in items if i.venture_key == venture]
    if opp_type and opp_type != "all":
        items = [i for i in items if i.opportunity_type == opp_type]
    if priority and priority != "all":
        items = [i for i in items if i.priority == priority]

    if admin_id and not include_not_relevant:
        not_rel = {
            s.opportunity_id
            for s in OpportunityUserState.query.filter_by(
                admin_id=admin_id, status="not_relevant"
            ).all()
        }
        items = [i for i in items if i.id not in not_rel]

    return items


def set_opportunity_state(opportunity_id, admin_id, status):
    if status not in ("saved", "applied", "not_relevant", "none"):
        raise ValueError("Invalid status.")

    item = OpportunityItem.query.get(opportunity_id)
    if not item:
        raise ValueError("Opportunity not found.")

    row = OpportunityUserState.query.filter_by(
        opportunity_id=opportunity_id, admin_id=admin_id
    ).first()

    if status == "none":
        if row:
            db.session.delete(row)
        db.session.commit()
        return item.to_dict(admin_id=admin_id)

    if not row:
        row = OpportunityUserState(
            opportunity_id=opportunity_id, admin_id=admin_id, status=status
        )
        db.session.add(row)
    else:
        row.status = status
    db.session.commit()
    return item.to_dict(admin_id=admin_id)


def list_saved_opportunities(admin_id):
    rows = (
        OpportunityUserState.query.filter_by(admin_id=admin_id, status="saved")
        .order_by(OpportunityUserState.updated_at.desc())
        .all()
    )
    result = []
    for row in rows:
        if row.opportunity:
            result.append(row.opportunity.to_dict(admin_id=admin_id))
    return result


def add_opportunity_to_timetable(opportunity_id, admin_id, plan_date=None, start_time=None, end_time=None):
    item = OpportunityItem.query.get(opportunity_id)
    if not item:
        raise ValueError("Opportunity not found.")

    if plan_date is None:
        plan_date = app_today()
    elif isinstance(plan_date, str):
        plan_date = parse_date_iso(plan_date)

    title = f"Prepare: {item.title[:120]}"
    desc_parts = []
    if item.deadline_date:
        desc_parts.append(f"Deadline: {item.deadline_date.isoformat()}")
    if item.apply_url:
        desc_parts.append(f"Apply: {item.apply_url}")
    if item.why_matters:
        desc_parts.append(item.why_matters[:500])

    timetable = create_timetable_item(
        plan_date,
        {
            "title": title,
            "description": "\n".join(desc_parts),
            "priority": "high" if item.priority == "high" else "medium",
            "category": "planning",
            "link_type": "news_opportunity",
            "link_opportunity_id": item.id,
            "link_label": "Open Opportunity",
            "start_time": start_time or "10:00",
            "end_time": end_time or "11:00",
        },
    )
    return timetable


def news_chat(message, admin_id, do_search=False):
    today = app_today()
    report = get_report_for_date(today)
    context_items = []
    if report and report.status == "complete":
        for item in report.opportunities.limit(40):
            context_items.append(item.to_dict(admin_id=admin_id))

    extra = None
    if do_search:
        extra = search_web(message, max_results=8)

    context = json.dumps(context_items, ensure_ascii=False, default=str)
    return chat_about_opportunities(message, context, extra_search_results=extra)


def serialize_report(report, admin_id=None, venture=None, opp_type=None, priority=None):
    items = filter_opportunities(report, venture, opp_type, priority, admin_id=admin_id)
    data = report.to_dict(include_counts=True)
    data["opportunities"] = [i.to_dict(admin_id=admin_id) for i in items]
    data["ventures"] = [
        {
            "key": v["key"],
            "label": v["label"],
            "emoji": v["emoji"],
            "count": len([i for i in items if i.venture_key == v["key"]]),
        }
        for v in VENTURES
    ]
    return data
