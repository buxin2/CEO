"""My Ideas CRUD, search, and structured data helpers."""

import json
import re
from datetime import datetime

from models import (
    db,
    Idea,
    IdeaAttachment,
    IdeaEvent,
    IdeaLink,
    IdeaMessage,
    IDEA_PRIORITIES,
    IDEA_STATUSES,
)

DEFAULT_STRUCTURED = {
    "concept": "",
    "goal": "",
    "target_users": "",
    "target_market": "",
    "requirements": [],
    "decisions": [],
    "problems": [],
    "open_questions": [],
    "business_model": "",
    "revenue_ideas": [],
    "resources": [],
    "goals": [],
    "next_steps": [],
}


def _normalize_structured(data):
    base = dict(DEFAULT_STRUCTURED)
    if not data:
        return base
    for key in base:
        if key in data:
            base[key] = data[key]
    if not isinstance(base.get("next_steps"), list):
        base["next_steps"] = []
    for key in ("requirements", "problems", "open_questions", "revenue_ideas", "resources", "goals", "decisions"):
        if not isinstance(base.get(key), list):
            base[key] = []
    return base


def _preview_from_text(text, limit=160):
    text = (text or "").strip().replace("\n", " ")
    return text[:limit] + ("…" if len(text) > limit else "")


def list_ideas(admin_id, search=None, tag=None, archived=False, status=None):
    q = Idea.query.filter_by(admin_id=admin_id, archived=bool(archived))
    if status:
        q = q.filter(Idea.status == status)
    if tag:
        tag_lower = tag.strip().lower()
        rows = q.order_by(Idea.updated_at.desc()).all()
        return [i for i in rows if tag_lower in [t.lower() for t in i.tags()]]
    rows = q.order_by(Idea.updated_at.desc()).all()
    if search:
        needle = search.strip().lower()
        if needle:
            matched = []
            for idea in rows:
                blob = " ".join([
                    idea.title or "",
                    idea.preview or "",
                    idea.narrative_summary or "",
                    json.dumps(idea.structured()),
                ]).lower()
                msgs = IdeaMessage.query.filter_by(idea_id=idea.id).all()
                blob += " " + " ".join(m.content.lower() for m in msgs)
                if needle in blob:
                    matched.append(idea)
            return matched
    return rows


def get_idea(admin_id, idea_id):
    idea = Idea.query.filter_by(id=idea_id, admin_id=admin_id).first()
    if not idea:
        raise ValueError("Idea not found.")
    return idea


def create_idea(admin_id, title, original_text="", status="new", priority="medium", tags=None, structured=None):
    title = (title or "").strip()
    if not title:
        raise ValueError("Idea title is required.")
    original = (original_text or "").strip()
    idea = Idea(
        admin_id=admin_id,
        title=title[:500],
        preview=_preview_from_text(original or title),
        original_text=original,
        status=status if status in IDEA_STATUSES else "new",
        priority=priority if priority in IDEA_PRIORITIES else "medium",
        tags_json=json.dumps(tags or []),
        structured_json=json.dumps(_normalize_structured(structured)),
        last_worked_at=datetime.utcnow(),
    )
    db.session.add(idea)
    db.session.flush()
    add_event(idea.id, "created", "Idea created.")
    if original:
        add_message(idea.id, "user", original)
    db.session.commit()
    return idea


def update_idea(admin_id, idea_id, data):
    idea = get_idea(admin_id, idea_id)
    if data.get("title"):
        idea.title = data["title"].strip()[:500]
    if data.get("preview") is not None:
        idea.preview = (data.get("preview") or "").strip()[:500]
    if data.get("status") and data["status"] in IDEA_STATUSES:
        idea.status = data["status"]
    if data.get("priority") and data["priority"] in IDEA_PRIORITIES:
        idea.priority = data["priority"]
    if data.get("tags") is not None:
        idea.tags_json = json.dumps(data["tags"] or [])
    if data.get("structured") is not None:
        idea.structured_json = json.dumps(_normalize_structured(data["structured"]))
    if data.get("narrative_summary") is not None:
        idea.narrative_summary = (data.get("narrative_summary") or "").strip()
    idea.updated_at = datetime.utcnow()
    idea.last_worked_at = datetime.utcnow()
    db.session.commit()
    return idea


def archive_idea(admin_id, idea_id):
    idea = get_idea(admin_id, idea_id)
    idea.archived = True
    idea.status = "archived"
    idea.updated_at = datetime.utcnow()
    add_event(idea.id, "archived", "Idea archived.")
    db.session.commit()
    return idea


def restore_idea(admin_id, idea_id):
    idea = get_idea(admin_id, idea_id)
    idea.archived = False
    if idea.status == "archived":
        idea.status = "exploring"
    idea.updated_at = datetime.utcnow()
    add_event(idea.id, "restored", "Idea restored from archive.")
    db.session.commit()
    return idea


def delete_idea(admin_id, idea_id):
    idea = get_idea(admin_id, idea_id)
    db.session.delete(idea)
    db.session.commit()


def add_message(idea_id, role, content):
    msg = IdeaMessage(idea_id=idea_id, role=role[:20], content=(content or "").strip())
    db.session.add(msg)
    idea = Idea.query.get(idea_id)
    if idea:
        idea.updated_at = datetime.utcnow()
        idea.last_worked_at = datetime.utcnow()
    db.session.flush()
    return msg


def list_messages(idea_id, limit=200):
    return (
        IdeaMessage.query.filter_by(idea_id=idea_id)
        .order_by(IdeaMessage.created_at.asc())
        .limit(limit)
        .all()
    )


def add_event(idea_id, event_type, description):
    row = IdeaEvent(
        idea_id=idea_id,
        event_type=(event_type or "note")[:40],
        description=(description or "").strip(),
    )
    db.session.add(row)
    db.session.flush()
    return row


def add_link(idea_id, link_type, link_id, label=""):
    existing = IdeaLink.query.filter_by(idea_id=idea_id, link_type=link_type, link_id=link_id).first()
    if existing:
        return existing
    row = IdeaLink(
        idea_id=idea_id,
        link_type=link_type[:30],
        link_id=int(link_id),
        label=(label or "")[:255],
    )
    db.session.add(row)
    db.session.flush()
    return row


def add_attachment(idea_id, url, title="", kind="url"):
    row = IdeaAttachment(
        idea_id=idea_id,
        url=(url or "").strip()[:500],
        title=(title or "").strip()[:255],
        kind=(kind or "url")[:30],
    )
    db.session.add(row)
    db.session.commit()
    return row


def merge_structured(idea, patch):
    current = _normalize_structured(idea.structured())
    for key, val in (patch or {}).items():
        if key in current and val is not None:
            current[key] = val
    idea.structured_json = json.dumps(_normalize_structured(current))
    idea.updated_at = datetime.utcnow()
    idea.last_worked_at = datetime.utcnow()
    db.session.flush()
    return current


def add_list_item(idea, field, text):
    if not text:
        return
    data = _normalize_structured(idea.structured())
    items = data.get(field) or []
    text = text.strip()
    if text and text not in items:
        items.append(text)
    data[field] = items
    idea.structured_json = json.dumps(data)
    db.session.flush()


def remove_list_item(idea, field, text):
    data = _normalize_structured(idea.structured())
    items = data.get(field) or []
    text = (text or "").strip()
    data[field] = [x for x in items if x != text]
    idea.structured_json = json.dumps(data)
    db.session.flush()


def add_decision(idea, text):
    if not text:
        return
    data = _normalize_structured(idea.structured())
    decisions = data.get("decisions") or []
    entry = {"text": text.strip(), "at": datetime.utcnow().isoformat()}
    decisions.append(entry)
    data["decisions"] = decisions
    idea.structured_json = json.dumps(data)
    add_event(idea.id, "decision", text.strip())
    db.session.flush()


def add_next_step(idea, text):
    if not text:
        return
    data = _normalize_structured(idea.structured())
    steps = data.get("next_steps") or []
    step_id = max([s.get("id", 0) for s in steps if isinstance(s, dict)] or [0]) + 1
    steps.append({"id": step_id, "text": text.strip(), "done": False})
    data["next_steps"] = steps
    idea.structured_json = json.dumps(data)
    db.session.flush()


def complete_next_step(idea, step_id=None, text=None):
    data = _normalize_structured(idea.structured())
    steps = data.get("next_steps") or []
    for step in steps:
        if not isinstance(step, dict):
            continue
        if step_id and step.get("id") == step_id:
            step["done"] = True
        elif text and step.get("text") == text.strip():
            step["done"] = True
    data["next_steps"] = steps
    idea.structured_json = json.dumps(data)
    db.session.flush()


def ideas_summary_for_ai(admin_id, limit=12):
    rows = (
        Idea.query.filter_by(admin_id=admin_id, archived=False)
        .order_by(Idea.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": i.id,
            "title": i.title,
            "status": i.status,
            "priority": i.priority,
            "preview": i.preview,
            "tags": i.tags(),
            "updated_at": i.updated_at.isoformat() if i.updated_at else None,
        }
        for i in rows
    ]


def detect_new_idea_intent(message):
    text = (message or "").strip().lower()
    patterns = [
        r"\bnew idea\b",
        r"\bi have an idea\b",
        r"\bi've got an idea\b",
        r"\bi was thinking\b",
        r"\bjust thought of\b",
        r"\blet's capture\b",
        r"\bcapture this idea\b",
    ]
    return any(re.search(p, text) for p in patterns)
