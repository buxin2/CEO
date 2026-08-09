"""Owner profile for the AI assistant — who the admin is (sole user of this AI)."""

from models import db, Admin, AiOwnerProfile, PlannerSettings

_MAX_PROFILE_PROMPT_CHARS = 2500

_DEFAULT_PROFILE_TEXT = (
    "You speak only with the owner and CEO of this management system. "
    "No employees or other people use this AI chat — only this one admin. "
    "They run every company in the app (products, services, earnings, and team tasks). "
    "Know them personally: greet them by name, remember they are your only user, "
    "and advise them as a long-term mentor and strategic business partner."
)


def _default_display_name(admin):
    if not admin:
        return "CEO"
    local = (admin.email or "").split("@")[0].strip()
    if local:
        return local.replace(".", " ").replace("_", " ").title()
    return "CEO"


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
        admin_id = Admin.query.order_by(Admin.id.asc()).first()
        admin_id = admin_id.id if admin_id else None
        if not admin_id:
            return None

    profile = AiOwnerProfile.query.filter_by(admin_id=admin_id).first()
    if profile:
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


def build_ai_owner_profile_text(admin_id=None):
    """Compact block for the AI system prompt."""
    profile = get_owner_profile(admin_id)
    if not profile:
        return (
            "WHO YOU ARE TALKING TO:\n"
            "The sole admin and CEO of this app. Only one person uses this AI.\n"
        )

    admin = profile.admin or Admin.query.get(profile.admin_id)
    name = (profile.display_name or "").strip() or _default_display_name(admin)
    bio = (profile.profile_text or "").strip() or _DEFAULT_PROFILE_TEXT
    if len(bio) > _MAX_PROFILE_PROMPT_CHARS:
        bio = bio[:_MAX_PROFILE_PROMPT_CHARS].rstrip() + "…"

    lines = [
        "WHO YOU ARE TALKING TO (sole user — no one else chats with you):",
        f"Name: {name}",
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
        "Always address this person personally. You are their private mentor — "
        "not a generic assistant for their staff."
    )
    return "\n".join(lines)
