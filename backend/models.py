import secrets
from datetime import datetime, date, timedelta

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def generate_token(length=24):
    """Generate a secure random URL-safe token for employee links."""
    return secrets.token_urlsafe(length)


def get_week_bounds(reference_date=None):
    """Return (monday, sunday) date objects for the week containing reference_date."""
    if reference_date is None:
        reference_date = date.today()
    monday = reference_date - timedelta(days=reference_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


class Admin(db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employees = db.relationship(
        "Employee", backref="company", cascade="all, delete-orphan", lazy="dynamic"
    )
    group = db.relationship(
        "CompanyGroup", backref="company", uselist=False, cascade="all, delete-orphan"
    )
    products = db.relationship(
        "Product", backref="company", cascade="all, delete-orphan", lazy="dynamic"
    )
    services = db.relationship(
        "Service", backref="company", cascade="all, delete-orphan", lazy="dynamic"
    )
    earnings = db.relationship(
        "Earning", backref="company", cascade="all, delete-orphan", lazy="dynamic"
    )

    def to_dict(self, include_stats=False, week_start=None, week_end=None):
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "employee_count": self.employees.count(),
        }
        if include_stats:
            data["stats"] = self.get_week_stats(week_start, week_end)
        return data

    def get_week_stats(self, week_start=None, week_end=None):
        if week_start is None or week_end is None:
            week_start, week_end = get_week_bounds()

        total = 0
        completed = 0
        for employee in self.employees:
            tasks = employee.tasks.filter(
                Task.week_start == week_start, Task.week_end == week_end
            ).all()
            total += len(tasks)
            completed += len([t for t in tasks if t.status == "completed"])

        pending = total - completed
        pct = round((completed / total) * 100) if total > 0 else 0
        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "completion_pct": pct,
        }


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), default="")
    position = db.Column(db.String(255), default="")
    unique_token = db.Column(db.String(64), unique=True, nullable=False, index=True, default=generate_token)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = db.relationship(
        "Task", backref="employee", cascade="all, delete-orphan", lazy="dynamic"
    )

    def to_dict(self, include_stats=False, week_start=None, week_end=None):
        data = {
            "id": self.id,
            "company_id": self.company_id,
            "name": self.name,
            "email": self.email,
            "position": self.position,
            "unique_token": self.unique_token,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_stats:
            data["stats"] = self.get_week_stats(week_start, week_end)
        return data

    def get_week_stats(self, week_start=None, week_end=None):
        if week_start is None or week_end is None:
            week_start, week_end = get_week_bounds()

        tasks = self.tasks.filter(
            Task.week_start == week_start, Task.week_end == week_end
        ).all()
        total = len(tasks)
        completed = len([t for t in tasks if t.status == "completed"])
        pending = total - completed
        pct = round((completed / total) * 100) if total > 0 else 0
        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "completion_pct": pct,
        }


class CompanyGroup(db.Model):
    __tablename__ = "company_groups"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), unique=True, nullable=False)
    group_token = db.Column(db.String(64), unique=True, nullable=False, index=True, default=generate_token)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship("GroupMember", backref="group", cascade="all, delete-orphan", lazy="dynamic")
    messages = db.relationship("GroupMessage", backref="group", cascade="all, delete-orphan", lazy="dynamic")
    join_requests = db.relationship("GroupJoinRequest", backref="group", cascade="all, delete-orphan", lazy="dynamic")

    def display_name(self):
        return f"{self.company.name} Group"

    def to_dict(self, include_link=False):
        data = {
            "id": self.id,
            "company_id": self.company_id,
            "company_name": self.company.name,
            "group_name": self.display_name(),
            "member_count": self.active_member_count(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_link:
            data["group_token"] = self.group_token
        return data

    def active_member_count(self):
        return GroupMember.query.filter_by(group_id=self.id).filter(
            GroupMember.removed_at.is_(None)
        ).count()


class GroupMember(db.Model):
    __tablename__ = "group_members"
    __table_args__ = (db.UniqueConstraint("group_id", "employee_id", name="uq_group_employee"),)

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("company_groups.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    removed_at = db.Column(db.DateTime, nullable=True)

    employee = db.relationship("Employee", backref="group_memberships")


class GroupMessage(db.Model):
    __tablename__ = "group_messages"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("company_groups.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("group_messages.id"), nullable=True)
    content = db.Column(db.Text, nullable=False, default="")
    image_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    employee = db.relationship("Employee", backref="group_messages")
    admin = db.relationship("Admin", backref="group_messages")
    parent = db.relationship("GroupMessage", remote_side=[id], backref="replies")
    reactions = db.relationship("GroupMessageReaction", backref="message", cascade="all, delete-orphan")

    def to_dict(self, include_replies=False):
        likes = sum(1 for r in self.reactions if r.reaction == "like")
        dislikes = sum(1 for r in self.reactions if r.reaction == "dislike")
        reply_count = GroupMessage.query.filter_by(parent_id=self.id, deleted_at=None).count()

        sender_name = "Admin"
        sender_role = "Administrator"
        if self.employee_id and self.employee:
            sender_name = self.employee.name
            sender_role = self.employee.position or "Team member"
        elif self.admin_id and self.admin:
            sender_name = "Admin"
            sender_role = "Administrator"

        data = {
            "id": self.id,
            "group_id": self.group_id,
            "employee_id": self.employee_id,
            "admin_id": self.admin_id,
            "parent_id": self.parent_id,
            "content": self.content or "",
            "image_url": self.image_url or "",
            "message_type": "image" if self.image_url else "text",
            "sender_name": sender_name,
            "sender_role": sender_role,
            "is_admin": self.admin_id is not None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "likes": likes,
            "dislikes": dislikes,
            "reply_count": reply_count,
        }

        if self.parent_id and self.parent and not self.parent.deleted_at:
            data["parent_preview"] = {
                "id": self.parent.id,
                "sender_name": self.parent.employee.name if self.parent.employee else "Admin",
                "content": self.parent.content[:200],
            }

        if include_replies:
            replies = (
                GroupMessage.query.filter_by(parent_id=self.id, deleted_at=None)
                .order_by(GroupMessage.created_at.asc())
                .all()
            )
            data["replies"] = [r.to_dict() for r in replies]

        return data


class GroupMessageReaction(db.Model):
    __tablename__ = "group_message_reactions"
    __table_args__ = (db.UniqueConstraint("message_id", "employee_id", name="uq_message_employee_reaction"),)

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("group_messages.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    reaction = db.Column(db.String(10), nullable=False)


class GroupJoinRequest(db.Model):
    __tablename__ = "group_join_requests"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("company_groups.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(255), default="")
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "group_id": self.group_id,
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, default="")
    priority = db.Column(db.String(20), default="medium")  # low, medium, high
    due_date = db.Column(db.Date, nullable=True)
    week_start = db.Column(db.Date, nullable=False, index=True)
    week_end = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), default="pending")  # pending, completed
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "week_start": self.week_start.isoformat() if self.week_start else None,
            "week_end": self.week_end.isoformat() if self.week_end else None,
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Earning(db.Model):
    __tablename__ = "earnings"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    earned_date = db.Column(db.Date, nullable=False, index=True)
    note = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = db.relationship("Employee", backref="earnings")

    def to_dict(self, include_employee=False):
        data = {
            "id": self.id,
            "company_id": self.company_id,
            "employee_id": self.employee_id,
            "amount": float(self.amount),
            "earned_date": self.earned_date.isoformat() if self.earned_date else None,
            "note": self.note or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_employee and self.employee:
            data["employee_name"] = self.employee.name
        return data


class PlannerGoal(db.Model):
    __tablename__ = "planner_goals"

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(20), nullable=False, index=True)  # monthly, weekly, daily
    period_key = db.Column(db.String(32), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    position = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "scope": self.scope,
            "period_key": self.period_key,
            "title": self.title,
            "completed": self.completed,
            "position": self.position,
        }


class OpportunityReport(db.Model):
    """Daily AI-generated opportunity intelligence report."""

    __tablename__ = "opportunity_reports"

    id = db.Column(db.Integer, primary_key=True)
    report_date = db.Column(db.Date, nullable=False, unique=True, index=True)
    status = db.Column(db.String(20), default="pending", index=True)  # pending, generating, complete, failed
    summary_json = db.Column(db.Text, default="{}")
    ai_recommendation = db.Column(db.Text, default="")
    error_message = db.Column(db.String(500), default="")
    generated_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    opportunities = db.relationship(
        "OpportunityItem", backref="report", cascade="all, delete-orphan", lazy="dynamic"
    )

    def to_dict(self, include_counts=False):
        data = {
            "id": self.id,
            "report_date": self.report_date.isoformat() if self.report_date else None,
            "status": self.status,
            "ai_recommendation": self.ai_recommendation or "",
            "error_message": self.error_message or "",
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
        }
        try:
            import json

            data["summary"] = json.loads(self.summary_json or "{}")
        except json.JSONDecodeError:
            data["summary"] = {}
        if include_counts:
            data["total_count"] = self.opportunities.count()
        return data


class OpportunityItem(db.Model):
    """A single verified opportunity discovered for a venture."""

    __tablename__ = "opportunity_items"

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("opportunity_reports.id"), nullable=False, index=True)
    venture_key = db.Column(db.String(40), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True, index=True)
    title = db.Column(db.String(500), nullable=False)
    summary = db.Column(db.Text, default="")
    why_matters = db.Column(db.Text, default="")
    opportunity_type = db.Column(db.String(40), default="other", index=True)
    priority = db.Column(db.String(20), default="medium", index=True)
    source_name = db.Column(db.String(255), default="")
    source_url = db.Column(db.String(1000), default="")
    apply_url = db.Column(db.String(1000), default="")
    apply_label = db.Column(db.String(80), default="Learn More")
    published_date = db.Column(db.Date, nullable=True)
    deadline_date = db.Column(db.Date, nullable=True)
    region = db.Column(db.String(255), default="")
    eligibility = db.Column(db.Text, default="")
    verified = db.Column(db.Boolean, default=True)
    uncertain = db.Column(db.Boolean, default=False)
    dedupe_key = db.Column(db.String(64), index=True)
    posted_to_group = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship("Company")
    user_states = db.relationship(
        "OpportunityUserState", backref="opportunity", cascade="all, delete-orphan", lazy="dynamic"
    )

    def to_dict(self, admin_id=None):
        from services.opportunity_ventures import venture_meta

        meta = venture_meta(self.venture_key)
        state = None
        if admin_id:
            row = OpportunityUserState.query.filter_by(
                opportunity_id=self.id, admin_id=admin_id
            ).first()
            state = row.status if row else "none"

        days_left = None
        urgent = False
        if self.deadline_date:
            days_left = (self.deadline_date - date.today()).days
            urgent = days_left is not None and 0 <= days_left <= 7

        return {
            "id": self.id,
            "report_id": self.report_id,
            "venture_key": self.venture_key,
            "venture_label": meta.get("label", self.venture_key),
            "venture_emoji": meta.get("emoji", ""),
            "company_id": self.company_id,
            "company_name": self.company.name if self.company else None,
            "title": self.title,
            "summary": self.summary or "",
            "why_matters": self.why_matters or "",
            "opportunity_type": self.opportunity_type,
            "opportunity_type_label": meta.get("type_labels", {}).get(
                self.opportunity_type, self.opportunity_type
            ),
            "priority": self.priority,
            "source_name": self.source_name or "",
            "source_url": self.source_url or "",
            "apply_url": self.apply_url or "",
            "apply_label": self.apply_label or "Learn More",
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "deadline_date": self.deadline_date.isoformat() if self.deadline_date else None,
            "deadline_days_left": days_left,
            "deadline_urgent": urgent,
            "region": self.region or "",
            "eligibility": self.eligibility or "",
            "verified": self.verified,
            "uncertain": self.uncertain,
            "posted_to_group": self.posted_to_group,
            "user_state": state,
        }


class OpportunityUserState(db.Model):
    """Per-admin saved / applied / not-relevant state."""

    __tablename__ = "opportunity_user_states"

    id = db.Column(db.Integer, primary_key=True)
    opportunity_id = db.Column(
        db.Integer, db.ForeignKey("opportunity_items.id"), nullable=False, index=True
    )
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=False, index=True)
    status = db.Column(db.String(20), default="saved")  # saved, applied, not_relevant
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("opportunity_id", "admin_id", name="uq_opportunity_admin_state"),
    )


class TimetableItem(db.Model):
    __tablename__ = "timetable_items"

    id = db.Column(db.Integer, primary_key=True)
    plan_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.String(5), nullable=False, default="09:00")
    end_time = db.Column(db.String(5), nullable=False, default="10:00")
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, default="")
    priority = db.Column(db.String(20), default="medium")  # high, medium, low
    category = db.Column(db.String(50), default="work")
    link_type = db.Column(db.String(40), default="none")
    link_company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    link_opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunity_items.id"), nullable=True)
    link_label = db.Column(db.String(120), default="")
    completed = db.Column(db.Boolean, default=False)
    position = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    link_company = db.relationship("Company")
    link_opportunity = db.relationship("OpportunityItem", foreign_keys=[link_opportunity_id])

    def to_dict(self, include_link=False):
        data = {
            "id": self.id,
            "plan_date": self.plan_date.isoformat() if self.plan_date else None,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "category": self.category,
            "link_type": self.link_type or "none",
            "link_company_id": self.link_company_id,
            "link_opportunity_id": self.link_opportunity_id,
            "link_label": self.link_label or "",
            "completed": self.completed,
            "position": self.position,
        }
        if include_link:
            from services.planner_service import build_item_link_url

            data["link_url"] = build_item_link_url(self)
            if self.link_company:
                data["link_company_name"] = self.link_company.name
        return data


class PlannerSettings(db.Model):
    __tablename__ = "planner_settings"

    id = db.Column(db.Integer, primary_key=True)
    personal_notes = db.Column(db.Text, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AiOwnerProfile(db.Model):
    """Persistent profile for the sole admin user — included in every AI system prompt."""

    __tablename__ = "ai_owner_profiles"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=False, unique=True, index=True)
    display_name = db.Column(db.String(120), default="")
    profile_text = db.Column(db.Text, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    admin = db.relationship("Admin", backref=db.backref("ai_owner_profile", uselist=False))

    def to_dict(self):
        return {
            "display_name": self.display_name or "",
            "profile_text": self.profile_text or "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MentorSettings(db.Model):
    __tablename__ = "mentor_settings"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=False, unique=True, index=True)
    quiet_start = db.Column(db.String(5), default="22:00")
    quiet_end = db.Column(db.String(5), default="07:00")
    reminder_interval_minutes = db.Column(db.Integer, default=30)
    max_reminders = db.Column(db.Integer, default=3)
    voice_responses = db.Column(db.Boolean, default=True)
    proactive_enabled = db.Column(db.Boolean, default=True)
    context_notes = db.Column(db.Text, default="")
    timezone_country = db.Column(db.String(80), default="")
    timezone_city = db.Column(db.String(80), default="")
    timezone_id = db.Column(db.String(64), default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "quiet_start": self.quiet_start or "22:00",
            "quiet_end": self.quiet_end or "07:00",
            "reminder_interval_minutes": self.reminder_interval_minutes or 30,
            "max_reminders": self.max_reminders or 3,
            "voice_responses": bool(self.voice_responses),
            "proactive_enabled": bool(self.proactive_enabled),
            "context_notes": self.context_notes or "",
            "timezone_country": self.timezone_country or "",
            "timezone_city": self.timezone_city or "",
            "timezone_id": self.timezone_id or "",
        }


class MentorProblem(db.Model):
    __tablename__ = "mentor_problems"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True, index=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="open", index=True)  # open, pending, resolved
    priority = db.Column(db.String(20), default="medium")
    next_action = db.Column(db.Text, default="")
    follow_up_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    company = db.relationship("Company")

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "company_name": self.company.name if self.company else None,
            "title": self.title,
            "description": self.description or "",
            "status": self.status,
            "priority": self.priority,
            "next_action": self.next_action or "",
            "follow_up_at": self.follow_up_at.isoformat() if self.follow_up_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MentorMessage(db.Model):
    __tablename__ = "mentor_messages"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # user, assistant, proactive
    content = db.Column(db.Text, nullable=False)
    meta_json = db.Column(db.Text, default="{}")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        import json

        meta = {}
        try:
            meta = json.loads(self.meta_json or "{}")
        except json.JSONDecodeError:
            pass
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "meta": meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MentorCheckIn(db.Model):
    __tablename__ = "mentor_check_ins"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=False, index=True)
    kind = db.Column(db.String(40), default="scheduled")  # scheduled, hourly, follow_up, morning, evening
    title = db.Column(db.String(500), default="")
    message = db.Column(db.Text, nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(20), default="pending", index=True)  # pending, sent, responded, cancelled
    response = db.Column(db.Text, default="")
    response_type = db.Column(db.String(40), default="")
    reminder_count = db.Column(db.Integer, default=0)
    timetable_item_id = db.Column(db.Integer, db.ForeignKey("timetable_items.id"), nullable=True)
    problem_id = db.Column(db.Integer, db.ForeignKey("mentor_problems.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    timetable_item = db.relationship("TimetableItem")
    problem = db.relationship("MentorProblem")

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title or "",
            "message": self.message,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "status": self.status,
            "response": self.response or "",
            "response_type": self.response_type or "",
            "reminder_count": self.reminder_count or 0,
            "timetable_item_id": self.timetable_item_id,
            "problem_id": self.problem_id,
        }


class GroqApiKey(db.Model):
    __tablename__ = "groq_api_keys"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    encrypted_key = db.Column(db.Text, nullable=False)
    model = db.Column(db.String(120), default="")
    is_active = db.Column(db.Boolean, default=False, index=True)
    last_tested_at = db.Column(db.DateTime, nullable=True)
    last_test_status = db.Column(db.String(40), default="")
    last_test_message = db.Column(db.String(500), default="")
    last_used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_masked=True):
        from services.groq_key_service import mask_api_key, decrypt_api_key

        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "provider": "Groq",
            "is_active": self.is_active,
            "model": self.model or "",
            "last_tested_at": self.last_tested_at.isoformat() if self.last_tested_at else None,
            "last_test_status": self.last_test_status or "",
            "last_test_message": self.last_test_message or "",
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_masked:
            plain = decrypt_api_key(self.encrypted_key)
            data["masked_key"] = mask_api_key(plain)
        return data


class CloudinarySettings(db.Model):
    """Singleton Cloudinary config for group chat image uploads."""

    __tablename__ = "cloudinary_settings"

    id = db.Column(db.Integer, primary_key=True)
    cloud_name = db.Column(db.String(80), default="")
    encrypted_api_key = db.Column(db.Text, default="")
    encrypted_api_secret = db.Column(db.Text, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------- Community ----------


DEFAULT_COMMUNITY_REGISTRATION_FIELDS = [
    {"key": "full_name", "label": "Full name", "type": "text", "required": True, "builtin": True},
    {"key": "username", "label": "Username", "type": "text", "required": True, "builtin": True},
    {"key": "email", "label": "Email", "type": "email", "required": True, "builtin": True},
    {"key": "password", "label": "Password", "type": "password", "required": True, "builtin": True},
    {"key": "background", "label": "Background", "type": "textarea", "required": False, "builtin": True},
    {"key": "why_join", "label": "Why do you want to join?", "type": "textarea", "required": False, "builtin": True},
    {"key": "experience_level", "label": "Experience / skill level", "type": "text", "required": False, "builtin": True},
]


class Community(db.Model):
    __tablename__ = "communities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    community_token = db.Column(db.String(64), unique=True, nullable=False, index=True, default=generate_token)
    description = db.Column(db.Text, default="")
    approval_required = db.Column(db.Boolean, default=False)
    members_visible = db.Column(db.Boolean, default=True)
    community_type = db.Column(db.String(20), default="free")  # free, paid
    price_cents = db.Column(db.Integer, default=0)
    currency = db.Column(db.String(10), default="USD")
    billing_interval = db.Column(db.String(20), default="one_time")  # one_time, month, year
    registration_fields_json = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    memberships = db.relationship(
        "CommunityMembership", backref="community", cascade="all, delete-orphan", lazy="dynamic"
    )
    posts = db.relationship(
        "CommunityPost", backref="community", cascade="all, delete-orphan", lazy="dynamic"
    )
    products = db.relationship(
        "CommunityProduct", backref="community", cascade="all, delete-orphan", lazy="dynamic"
    )

    def registration_fields(self):
        import json

        if self.registration_fields_json:
            try:
                return json.loads(self.registration_fields_json)
            except json.JSONDecodeError:
                pass
        return list(DEFAULT_COMMUNITY_REGISTRATION_FIELDS)

    def to_dict(self, include_link=False):
        from utils import community_link_for_token

        data = {
            "id": self.id,
            "name": self.name,
            "community_token": self.community_token,
            "description": self.description or "",
            "approval_required": bool(self.approval_required),
            "members_visible": bool(self.members_visible),
            "community_type": self.community_type or "free",
            "price_cents": self.price_cents or 0,
            "currency": self.currency or "USD",
            "billing_interval": self.billing_interval or "one_time",
            "registration_fields": self.registration_fields(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_link:
            data["community_link"] = community_link_for_token(self.community_token)
        return data


class CommunityMemberUser(db.Model):
    __tablename__ = "community_member_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    memberships = db.relationship("CommunityMembership", backref="member_user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self, private=False):
        data = {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name or "",
        }
        if private:
            data["email"] = self.email
        return data


class CommunityMembership(db.Model):
    __tablename__ = "community_memberships"
    __table_args__ = (
        db.UniqueConstraint("community_id", "member_user_id", name="uq_community_member"),
    )

    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id"), nullable=False, index=True)
    member_user_id = db.Column(db.Integer, db.ForeignKey("community_member_users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), default="active", index=True)  # pending_payment, pending, active, suspended, removed
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=True, index=True)
    background = db.Column(db.Text, default="")
    why_join = db.Column(db.Text, default="")
    experience_level = db.Column(db.String(120), default="")
    custom_fields_json = db.Column(db.Text, default="{}")
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    suspended_at = db.Column(db.DateTime, nullable=True)
    last_active_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self, include_private=False):
        import json

        user = self.member_user
        data = {
            "id": self.id,
            "community_id": self.community_id,
            "member_user_id": self.member_user_id,
            "status": self.status,
            "payment_id": self.payment_id,
            "username": user.username if user else "",
            "full_name": user.full_name if user else "",
            "background": self.background or "",
            "why_join": self.why_join or "",
            "experience_level": self.experience_level or "",
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
        }
        try:
            data["custom_fields"] = json.loads(self.custom_fields_json or "{}")
        except json.JSONDecodeError:
            data["custom_fields"] = {}
        if include_private and user:
            data["email"] = user.email
        return data


class CommunityPost(db.Model):
    __tablename__ = "community_posts"

    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id"), nullable=False, index=True)
    member_user_id = db.Column(db.Integer, db.ForeignKey("community_member_users.id"), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=True)
    content = db.Column(db.Text, default="")
    image_url = db.Column(db.String(500), nullable=True)
    is_announcement = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    member_user = db.relationship("CommunityMemberUser")
    admin = db.relationship("Admin")
    comments = db.relationship("CommunityComment", backref="post", cascade="all, delete-orphan", lazy="dynamic")
    likes = db.relationship("CommunityPostLike", backref="post", cascade="all, delete-orphan", lazy="dynamic")

    def author_label(self):
        if self.admin_id:
            return "Admin", "Administrator"
        if self.member_user:
            return self.member_user.full_name or self.member_user.username, "Member"
        return "Member", "Member"

    def to_dict(self, viewer_member_id=None):
        likes = self.likes.count()
        comments = CommunityComment.query.filter_by(post_id=self.id, deleted_at=None).count()
        name, role = self.author_label()
        data = {
            "id": self.id,
            "community_id": self.community_id,
            "content": self.content or "",
            "image_url": self.image_url or "",
            "is_announcement": bool(self.is_announcement),
            "is_admin": self.admin_id is not None,
            "author_name": name,
            "author_role": role,
            "likes": likes,
            "comment_count": comments,
            "liked_by_me": False,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if viewer_member_id:
            data["liked_by_me"] = CommunityPostLike.query.filter_by(
                post_id=self.id, member_user_id=viewer_member_id
            ).first() is not None
        return data


class CommunityComment(db.Model):
    __tablename__ = "community_comments"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("community_posts.id"), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("community_comments.id"), nullable=True)
    member_user_id = db.Column(db.Integer, db.ForeignKey("community_member_users.id"), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    member_user = db.relationship("CommunityMemberUser")
    admin = db.relationship("Admin")
    parent = db.relationship("CommunityComment", remote_side=[id], backref="replies")

    def author_label(self):
        if self.admin_id:
            return "Admin", "Administrator"
        if self.member_user:
            return self.member_user.full_name or self.member_user.username, "Member"
        return "Member", "Member"

    def to_dict(self):
        name, role = self.author_label()
        return {
            "id": self.id,
            "post_id": self.post_id,
            "parent_id": self.parent_id,
            "content": self.content,
            "is_admin": self.admin_id is not None,
            "author_name": name,
            "author_role": role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CommunityPostLike(db.Model):
    __tablename__ = "community_post_likes"
    __table_args__ = (db.UniqueConstraint("post_id", "member_user_id", name="uq_community_post_like"),)

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("community_posts.id"), nullable=False)
    member_user_id = db.Column(db.Integer, db.ForeignKey("community_member_users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CommunityProduct(db.Model):
    __tablename__ = "community_products"

    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default="")
    image_url = db.Column(db.String(500), default="")
    product_type = db.Column(db.String(20), default="physical")  # physical, digital
    price = db.Column(db.String(64), default="")
    currency = db.Column(db.String(10), default="USD")
    purchase_url = db.Column(db.String(500), default="")
    price_cents = db.Column(db.Integer, default=0)
    quantity_available = db.Column(db.Integer, default=0)
    quantity_reserved = db.Column(db.Integer, default=0)
    digital_delivery_url = db.Column(db.String(500), default="")
    digital_delivery_text = db.Column(db.Text, default="")
    fee_percent = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="available")  # available, unavailable, out_of_stock
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def effective_status(self):
        if self.status == "unavailable":
            return "unavailable"
        avail = (self.quantity_available or 0) - (self.quantity_reserved or 0)
        if avail <= 0 and (self.quantity_available or 0) > 0:
            return "out_of_stock"
        return self.status or "available"

    def to_dict(self):
        avail = max(0, (self.quantity_available or 0) - (self.quantity_reserved or 0))
        eff = self.effective_status()
        return {
            "id": self.id,
            "community_id": self.community_id,
            "name": self.name,
            "description": self.description or "",
            "image_url": self.image_url or "",
            "product_type": self.product_type or "physical",
            "price": self.price or "",
            "price_cents": self.price_cents or 0,
            "currency": self.currency or "USD",
            "purchase_url": self.purchase_url or "",
            "quantity_available": self.quantity_available or 0,
            "quantity_reserved": self.quantity_reserved or 0,
            "quantity_sellable": avail,
            "digital_delivery_url": self.digital_delivery_url or "",
            "digital_delivery_text": self.digital_delivery_text or "",
            "fee_percent": self.fee_percent or 0,
            "status": eff,
            "view_count": self.view_count or 0,
            "in_app_checkout": True,
        }


class CommunityScheduledMessage(db.Model):
    __tablename__ = "community_scheduled_messages"

    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id"), nullable=False, index=True)
    title = db.Column(db.String(255), default="")
    message = db.Column(db.Text, nullable=False)
    schedule_kind = db.Column(db.String(20), default="once")  # once, daily, weekly
    schedule_time = db.Column(db.String(5), default="09:00")
    schedule_weekday = db.Column(db.Integer, nullable=True)  # 0=Monday for weekly
    scheduled_at = db.Column(db.DateTime, nullable=True)  # for once
    is_active = db.Column(db.Boolean, default=True)
    is_announcement = db.Column(db.Boolean, default=True)
    last_sent_at = db.Column(db.DateTime, nullable=True)
    next_run_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    community = db.relationship("Community", backref="scheduled_messages")

    def to_dict(self):
        return {
            "id": self.id,
            "community_id": self.community_id,
            "title": self.title or "",
            "message": self.message,
            "schedule_kind": self.schedule_kind,
            "schedule_time": self.schedule_time,
            "schedule_weekday": self.schedule_weekday,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "is_active": bool(self.is_active),
            "is_announcement": bool(self.is_announcement),
            "last_sent_at": self.last_sent_at.isoformat() if self.last_sent_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
        }


class CommunityNotification(db.Model):
    __tablename__ = "community_notifications"

    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id"), nullable=False, index=True)
    member_user_id = db.Column(db.Integer, db.ForeignKey("community_member_users.id"), nullable=True, index=True)
    kind = db.Column(db.String(40), default="info")
    message = db.Column(db.Text, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    payment_reference = db.Column(db.String(64), unique=True, nullable=False, index=True)
    payment_kind = db.Column(db.String(32), nullable=False, index=True)  # product_order, community_membership
    membership_id = db.Column(db.Integer, db.ForeignKey("community_memberships.id"), nullable=True, index=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id"), nullable=True, index=True)
    community_product_id = db.Column(db.Integer, db.ForeignKey("community_products.id"), nullable=True)
    member_user_id = db.Column(db.Integer, db.ForeignKey("community_member_users.id"), nullable=True, index=True)
    subtotal_cents = db.Column(db.Integer, default=0)
    discount_cents = db.Column(db.Integer, default=0)
    fee_cents = db.Column(db.Integer, default=0)
    total_cents = db.Column(db.Integer, default=0)
    currency = db.Column(db.String(10), default="USD")
    provider = db.Column(db.String(20), default="manual")  # modem, paypal, manual, coupon
    provider_payment_id = db.Column(db.String(255), default="", index=True)
    provider_intent_secret = db.Column(db.String(255), default="")
    payment_link = db.Column(db.String(500), default="")
    status = db.Column(db.String(30), default="pending", index=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey("coupons.id"), nullable=True)
    customer_name = db.Column(db.String(255), default="")
    customer_email = db.Column(db.String(255), default="")
    customer_phone = db.Column(db.String(64), default="")
    receipt_url = db.Column(db.String(500), default="")
    manual_review_note = db.Column(db.Text, default="")
    reviewed_at = db.Column(db.DateTime, nullable=True)
    metadata_json = db.Column(db.Text, default="{}")
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = db.relationship("Order", backref="payment_record", uselist=False, foreign_keys="Order.payment_id")
    coupon = db.relationship("Coupon", backref="payments")

    def to_dict(self, include_private=False):
        import json

        data = {
            "id": self.id,
            "payment_reference": self.payment_reference,
            "payment_kind": self.payment_kind,
            "membership_id": self.membership_id,
            "community_id": self.community_id,
            "community_product_id": self.community_product_id,
            "member_user_id": self.member_user_id,
            "subtotal_cents": self.subtotal_cents or 0,
            "discount_cents": self.discount_cents or 0,
            "fee_cents": self.fee_cents or 0,
            "total_cents": self.total_cents or 0,
            "currency": self.currency or "USD",
            "provider": self.provider or "",
            "provider_payment_id": self.provider_payment_id or "",
            "payment_link": self.payment_link or "",
            "status": self.status or "pending",
            "coupon_id": self.coupon_id,
            "customer_name": self.customer_name or "",
            "customer_email": self.customer_email or "",
            "receipt_url": self.receipt_url or "",
            "manual_review_note": self.manual_review_note or "",
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        try:
            data["metadata"] = json.loads(self.metadata_json or "{}")
        except json.JSONDecodeError:
            data["metadata"] = {}
        if include_private:
            data["customer_phone"] = self.customer_phone or ""
        return data


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(64), unique=True, nullable=False, index=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id"), nullable=False, index=True)
    community_product_id = db.Column(db.Integer, db.ForeignKey("community_products.id"), nullable=False, index=True)
    member_user_id = db.Column(db.Integer, db.ForeignKey("community_member_users.id"), nullable=False, index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=True, index=True)
    quantity = db.Column(db.Integer, default=1)
    unit_price_cents = db.Column(db.Integer, default=0)
    subtotal_cents = db.Column(db.Integer, default=0)
    discount_cents = db.Column(db.Integer, default=0)
    total_cents = db.Column(db.Integer, default=0)
    currency = db.Column(db.String(10), default="USD")
    payment_status = db.Column(db.String(30), default="pending")
    order_status = db.Column(db.String(30), default="pending_payment", index=True)
    product_type = db.Column(db.String(20), default="physical")
    delivery_json = db.Column(db.Text, default="{}")
    digital_delivery_url = db.Column(db.String(500), default="")
    digital_delivery_text = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = db.relationship("CommunityProduct", backref="orders")
    member_user = db.relationship("CommunityMemberUser", backref="orders")

    def to_dict(self, include_private=False):
        import json

        user = self.member_user
        product = self.product
        try:
            delivery = json.loads(self.delivery_json or "{}")
        except json.JSONDecodeError:
            delivery = {}
        data = {
            "id": self.id,
            "order_number": self.order_number,
            "community_id": self.community_id,
            "community_product_id": self.community_product_id,
            "member_user_id": self.member_user_id,
            "payment_id": self.payment_id,
            "quantity": self.quantity or 1,
            "unit_price_cents": self.unit_price_cents or 0,
            "subtotal_cents": self.subtotal_cents or 0,
            "discount_cents": self.discount_cents or 0,
            "total_cents": self.total_cents or 0,
            "currency": self.currency or "USD",
            "payment_status": self.payment_status or "",
            "order_status": self.order_status or "",
            "product_type": self.product_type or "physical",
            "product_name": product.name if product else "",
            "product_image": product.image_url if product else "",
            "customer_name": user.full_name if user else "",
            "customer_username": user.username if user else "",
            "digital_delivery_url": self.digital_delivery_url or "",
            "digital_delivery_text": self.digital_delivery_text or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_private:
            data["delivery"] = delivery
            if user:
                data["customer_email"] = user.email
        return data


class Coupon(db.Model):
    __tablename__ = "coupons"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    discount_type = db.Column(db.String(20), default="percent")  # percent, fixed
    discount_value = db.Column(db.Integer, default=0)  # percent 0-100 or fixed cents
    max_uses = db.Column(db.Integer, nullable=True)
    used_count = db.Column(db.Integer, default=0)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    applies_to = db.Column(db.String(20), default="all")  # all, product, community
    community_product_id = db.Column(db.Integer, db.ForeignKey("community_products.id"), nullable=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "discount_type": self.discount_type,
            "discount_value": self.discount_value or 0,
            "max_uses": self.max_uses,
            "used_count": self.used_count or 0,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": bool(self.is_active),
            "applies_to": self.applies_to or "all",
            "community_product_id": self.community_product_id,
            "community_id": self.community_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PaymentWebhookEvent(db.Model):
    __tablename__ = "payment_webhook_events"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(20), nullable=False, index=True)
    event_key = db.Column(db.String(255), nullable=False, index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=True)
    payload_json = db.Column(db.Text, default="{}")
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("provider", "event_key", name="uq_payment_webhook_event"),
    )
