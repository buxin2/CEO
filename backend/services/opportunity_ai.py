"""Groq AI extraction and ranking of web search results into opportunities."""

import json
from datetime import datetime

from models import Company
from services.app_knowledge import build_ai_app_knowledge_text
from services.opportunity_search import build_url_allowlist, url_is_verified
    text = (content or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    return json.loads(text)


def extract_opportunities_for_venture(venture_key, search_results, company_context=""):
    from services.groq_key_service import get_active_groq_config, mark_key_used

    config = get_active_groq_config()
    if not config:
        raise RuntimeError("No Groq API key configured.")

    meta = venture_meta(venture_key)
    allowed_urls, allowed_domains = build_url_allowlist(search_results)
    if not search_results:
        return {"opportunities": [], "no_new_note": "No search results to analyze."}

    types_list = ", ".join(OPPORTUNITY_TYPES.keys())
    payload = json.dumps(search_results[:40], ensure_ascii=False)

    prompt = (
        f"You are an opportunity intelligence analyst for venture: {meta.get('label')}.\n"
        "ONLY extract REAL actionable opportunities from the SEARCH RESULTS below.\n"
        "An opportunity means: funding, grant, investment, competition, accelerator, tender, "
        "partnership program, pilot, pitch event, or government program with potential business value.\n\n"
        "STRICT RULES:\n"
        "- Do NOT invent programs, deadlines, or URLs.\n"
        "- source_url and apply_url MUST be URLs that appear in the search results (or same domain path).\n"
        "- If deadline is not in the snippet, leave deadline_date null.\n"
        "- If not clearly actionable, skip it.\n"
        "- Prefer official application/register pages over news articles when both exist.\n"
        "- Mark uncertain=true if eligibility or details are unclear.\n"
        "- opportunity_type must be one of: " + types_list + "\n"
        "- priority: high (very relevant + actionable), medium, low\n\n"
        f"Company / venture context:\n{company_context}\n\n"
        f"SEARCH RESULTS JSON:\n{payload}\n\n"
        "Return ONLY valid JSON:\n"
        '{"opportunities": ['
        '{"title":"...","summary":"what it is","why_matters":"why for this venture",'
        '"opportunity_type":"grant","priority":"high|medium|low",'
        '"source_name":"...","source_url":"https://...","apply_url":"https://... or empty",'
        '"apply_label":"Apply Now|Register|Learn More|...",'
        '"published_date":"YYYY-MM-DD or null","deadline_date":"YYYY-MM-DD or null",'
        '"region":"country/region","eligibility":"who can apply","verified":true,"uncertain":false}'
        "],"
        '"no_new_note":"optional message if nothing actionable found"}'
    )

    from groq import Groq

    client = Groq(api_key=config["api_key"])
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {
                "role": "system",
                "content": "You extract verified business opportunities from search snippets. Output JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=4096,
    )
    mark_key_used(config.get("key_id"))

    raw = response.choices[0].message.content or "{}"
    try:
        data = _parse_json(raw)
    except json.JSONDecodeError:
        return {"opportunities": [], "no_new_note": "AI parsing failed."}

    cleaned = []
    for item in data.get("opportunities") or []:
        src = (item.get("source_url") or "").strip()
        apply = (item.get("apply_url") or "").strip()
        if not url_is_verified(src, allowed_urls, allowed_domains):
            if apply and url_is_verified(apply, allowed_urls, allowed_domains):
                item["source_url"] = apply
                src = apply
            else:
                continue
        if apply and not url_is_verified(apply, allowed_urls, allowed_domains):
            item["apply_url"] = ""
        if not item.get("title"):
            continue
        cleaned.append(item)

    data["opportunities"] = cleaned
    return data


def build_ai_recommendation(report_date, opportunities, app_knowledge):
    from services.groq_key_service import get_active_groq_config, mark_key_used

    config = get_active_groq_config()
    if not config:
        return "Configure Groq API to receive AI recommendations."

    opp_summary = json.dumps(
        [
            {
                "title": o.title,
                "venture": o.venture_key,
                "priority": o.priority,
                "type": o.opportunity_type,
                "deadline": o.deadline_date.isoformat() if o.deadline_date else None,
                "why": (o.why_matters or "")[:300],
            }
            for o in opportunities[:20]
        ],
        ensure_ascii=False,
    )

    prompt = (
        f"Date: {report_date.isoformat()}\n"
        "Based on the admin's companies and today's opportunities, write a short personal recommendation "
        "(2-4 sentences) answering: What opportunity should they act on first today?\n"
        "Consider deadlines, priority, and fit with their ventures.\n\n"
        f"APP CONTEXT:\n{app_knowledge[:6000]}\n\n"
        f"OPPORTUNITIES:\n{opp_summary}\n"
    )

    from groq import Groq

    client = Groq(api_key=config["api_key"])
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": "You are the admin's strategic mentor."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=500,
    )
    mark_key_used(config.get("key_id"))
    return (response.choices[0].message.content or "").strip()


def chat_about_opportunities(message, opportunities_context, extra_search_results=None):
    from services.groq_key_service import get_active_groq_config, mark_key_used, is_groq_configured

    if not is_groq_configured():
        return (
            "AI is not configured. Add a Groq API key in Admin → AI Assistant, then try again."
        )
    config = get_active_groq_config()
    app_knowledge = build_ai_app_knowledge_text()
    extra = ""
    if extra_search_results:
        extra = "\nFRESH SEARCH:\n" + json.dumps(extra_search_results[:15], ensure_ascii=False)

    prompt = (
        "You help the admin understand and act on daily business opportunities.\n"
        "Use ONLY verified information from context. If you don't know, say so.\n"
        "Suggest specific opportunities from the list when relevant.\n\n"
        f"APP:\n{app_knowledge[:5000]}\n\n"
        f"CURRENT OPPORTUNITIES:\n{opportunities_context}\n"
        f"{extra}\n\n"
        f"USER QUESTION: {message}"
    )

    from groq import Groq

    client = Groq(api_key=config["api_key"])
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": "Opportunity intelligence advisor."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.35,
        max_tokens=1200,
    )
    mark_key_used(config.get("key_id"))
    return (response.choices[0].message.content or "").strip()


def parse_optional_date(value):
    if not value:
        return None
    if isinstance(value, str):
        v = value.strip()
        if not v or v.lower() == "null":
            return None
        try:
            return datetime.strptime(v[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None
