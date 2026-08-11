"""Owner profile for the AI assistant — who the admin is (sole user of this AI)."""

import os

from flask import current_app

from models import db, Admin, AiOwnerProfile, PlannerSettings

_MAX_PROFILE_PROMPT_CHARS = 2500

_GENERIC_NAMES = frozenset({"admin", "ceo", "user", "owner", "boss"})

_DEFAULT_PROFILE_TEXT = (
    "You speak only with the owner and CEO of this management system. "
    "No employees or other people use this AI chat — only this one admin. "
    "They run every company in the app (products, services, earnings, and team tasks). "
    "Know them personally: greet them by name, remember they are your only user, "
    "and advise them as a long-term mentor and strategic business partner."
)


def _configured_display_name():
    try:
        return (current_app.config.get("ADMIN_DISPLAY_NAME") or "").strip()
    except RuntimeError:
        return (os.environ.get("ADMIN_DISPLAY_NAME") or "").strip()


def _default_display_name(admin):
    configured = _configured_display_name()
    if configured:
        return configured
    if not admin:
        return "CEO"
    local = (admin.email or "").split("@")[0].strip()
    if local:
        candidate = local.replace(".", " ").replace("_", " ").title()
        if candidate.lower() not in _GENERIC_NAMES:
            return candidate
    return "CEO"


def _is_generic_name(name):
    return not name or name.strip().lower() in _GENERIC_NAMES


def resolve_owner_display_name(admin_id=None):
    """Best name to use when talking to the user (never generic 'Admin' if we can avoid it)."""
    profile = get_owner_profile(admin_id)
    if not profile:
        return _configured_display_name() or "CEO"

    admin = profile.admin or Admin.query.get(profile.admin_id)
    name = (profile.display_name or "").strip()
    if name and not _is_generic_name(name):
        return name

    configured = _configured_display_name()
    if configured:
        return configured

    return _default_display_name(admin)


def build_name_address_rules(admin_id=None):
    """Short mandatory instruction so Groq always uses the real name."""
    name = resolve_owner_display_name(admin_id)
    return (
        f"THE USER'S NAME IS {name}. "
        f"You MUST call them '{name}' — in greetings, advice, and every reply. "
        f"NEVER call them 'Admin', 'the admin', 'user', or 'CEO' unless their name is literally that."
    )


def get_planner_personal_notes():
    settings = PlannerSettings.query.first()
    if not settings:
        return ""
    return (settings.personal_notes or "").strip()


def get_owner_profile(admin_id):
    """Return profile row for admin, creating with defaults if missing."""
    if not admin_id:
        profile = AiOwnerProfile.query.first()
        if profile:
            return profile
        admin = Admin.query.order_by(Admin.id.asc()).first()
        admin_id = admin.id if admin else None
        if not admin_id:
            return None

    profile = AiOwnerProfile.query.filter_by(admin_id=admin_id).first()
    if profile:
        _maybe_upgrade_generic_name(profile)
        return profile

    admin = Admin.query.get(admin_id)
    profile = AiOwnerProfile(
        admin_id=admin_id,
        display_name=_default_display_name(admin),
        profile_text=_DEFAULT_PROFILE_TEXT,
    )
    db.session.add(profile)
    db.session.commit()
    return profile


def _maybe_upgrade_generic_name(profile):
    """Replace generic display names (e.g. Admin from login email) with configured real name."""
    configured = _configured_display_name()
    if not configured:
        return
    current = (profile.display_name or "").strip()
    if _is_generic_name(current) and current.lower() != configured.lower():
        profile.display_name = configured[:120]
        db.session.commit()


def update_owner_profile(admin_id, display_name=None, profile_text=None):
    profile = get_owner_profile(admin_id)
    if not profile:
        raise ValueError("No admin account found.")

    if display_name is not None:
        profile.display_name = (display_name or "").strip()[:120]
    if profile_text is not None:
        profile.profile_text = (profile_text or "").strip()

    db.session.commit()
    return profile


def ensure_owner_display_names(app):
    """On startup: apply ADMIN_DISPLAY_NAME when profile still has a generic name."""
    configured = (app.config.get("ADMIN_DISPLAY_NAME") or "").strip()
    if not configured:
        return
    for profile in AiOwnerProfile.query.all():
        if _is_generic_name(profile.display_name):
            profile.display_name = configured[:120]
    db.session.commit()


def build_ai_owner_profile_text(admin_id=None):
    """Compact block for the AI system prompt."""
    profile = get_owner_profile(admin_id)
    if not profile:
        name = _configured_display_name() or "CEO"
        return (
            "WHO YOU ARE TALKING TO:\n"
            f"Name: {name}\n"
            + build_name_address_rules(admin_id)
        )

    admin = profile.admin or Admin.query.get(profile.admin_id)
    name = resolve_owner_display_name(admin_id)
    bio = (profile.profile_text or "").strip() or _DEFAULT_PROFILE_TEXT
    if len(bio) > _MAX_PROFILE_PROMPT_CHARS:
        bio = bio[:_MAX_PROFILE_PROMPT_CHARS].rstrip() + "…"

    lines = [
        "WHO YOU ARE TALKING TO (sole user — no one else chats with you):",
        f"Name: {name}",
        build_name_address_rules(admin_id),
    ]
    if admin and admin.email:
        lines.append(f"Login email: {admin.email}")
    lines.append(f"About them: {bio}")

    planner_notes = get_planner_personal_notes()
    if planner_notes:
        clipped = planner_notes
        if len(clipped) > 800:
            clipped = clipped[:800].rstrip() + "…"
        lines.append(f"Personal planner notes (from My Timetable): {clipped}")

    lines.append(
        "You are their private mentor — not a generic assistant for their staff."
    )
    return "\n".join(lines)
