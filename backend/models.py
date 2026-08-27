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


class PaymentSettings(db.Model):
    """Singleton PayPal + Modem Pay keys and live/test mode (admin Payments page)."""

    __tablename__ = "payment_settings"

    id = db.Column(db.Integer, primary_key=True)
    mode = db.Column(db.String(10), default="live")  # live | test
    brand_name = db.Column(db.String(120), default="Store")
    enc_paypal_client_id = db.Column(db.Text, default="")
    enc_paypal_secret = db.Column(db.Text, default="")
    enc_paypal_sandbox_client_id = db.Column(db.Text, default="")
    enc_paypal_sandbox_secret = db.Column(db.Text, default="")
    enc_modem_public_key = db.Column(db.Text, default="")
    enc_modem_secret = db.Column(db.Text, default="")
    enc_modem_webhook_secret = db.Column(db.Text, default="")
    enc_modem_test_secret = db.Column(db.Text, default="")
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
    image_url = db.Column(db.String(500), default="")
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
            "image_url": self.image_url or "",
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
    paid_until = db.Column(db.DateTime, nullable=True)

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
            "paid_until": self.paid_until.isoformat() if self.paid_until else None,
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
    payment_kind = db.Column(db.String(32), nullable=False, index=True)  # product_order, community_membership, store_order
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
    applies_to = db.Column(db.String(20), default="all")  # all, product, community, store, store_product
    community_product_id = db.Column(db.Integer, db.ForeignKey("community_products.id"), nullable=True)
    store_product_id = db.Column(db.Integer, db.ForeignKey("store_products.id"), nullable=True)
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
            "store_product_id": self.store_product_id,
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


IDEA_STATUSES = (
    "new", "exploring", "developing", "planning", "in_progress",
    "on_hold", "completed", "rejected", "archived",
)
IDEA_PRIORITIES = ("low", "medium", "high", "critical")


class Idea(db.Model):
    __tablename__ = "ideas"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    preview = db.Column(db.String(500), default="")
    original_text = db.Column(db.Text, default="")
    status = db.Column(db.String(30), default="new", index=True)
    priority = db.Column(db.String(20), default="medium", index=True)
    tags_json = db.Column(db.Text, default="[]")
    structured_json = db.Column(db.Text, default="{}")
    narrative_summary = db.Column(db.Text, default="")
    archived = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    last_worked_at = db.Column(db.DateTime, default=datetime.utcnow)

    messages = db.relationship("IdeaMessage", backref="idea", lazy="dynamic", cascade="all, delete-orphan")
    events = db.relationship("IdeaEvent", backref="idea", lazy="dynamic", cascade="all, delete-orphan")
    links = db.relationship("IdeaLink", backref="idea", lazy="dynamic", cascade="all, delete-orphan")
    attachments = db.relationship("IdeaAttachment", backref="idea", lazy="dynamic", cascade="all, delete-orphan")

    def tags(self):
        import json

        try:
            return json.loads(self.tags_json or "[]")
        except json.JSONDecodeError:
            return []

    def structured(self):
        import json

        try:
            return json.loads(self.structured_json or "{}")
        except json.JSONDecodeError:
            return {}

    def to_dict(self, include_detail=False):
        data = {
            "id": self.id,
            "title": self.title,
            "preview": self.preview or "",
            "original_text": self.original_text or "",
            "status": self.status or "new",
            "priority": self.priority or "medium",
            "tags": self.tags(),
            "archived": bool(self.archived),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_worked_at": self.last_worked_at.isoformat() if self.last_worked_at else None,
        }
        if include_detail:
            data["structured"] = self.structured()
            data["narrative_summary"] = self.narrative_summary or ""
            data["events"] = [e.to_dict() for e in self.events.order_by(IdeaEvent.created_at.asc()).all()]
            data["links"] = [lnk.to_dict() for lnk in self.links.all()]
            data["attachments"] = [a.to_dict() for a in self.attachments.order_by(IdeaAttachment.created_at.desc()).all()]
        return data


class IdeaMessage(db.Model):
    __tablename__ = "idea_messages"

    id = db.Column(db.Integer, primary_key=True)
    idea_id = db.Column(db.Integer, db.ForeignKey("ideas.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "idea_id": self.idea_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class IdeaEvent(db.Model):
    __tablename__ = "idea_events"

    id = db.Column(db.Integer, primary_key=True)
    idea_id = db.Column(db.Integer, db.ForeignKey("ideas.id"), nullable=False, index=True)
    event_type = db.Column(db.String(40), default="note")
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "event_type": self.event_type or "note",
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class IdeaLink(db.Model):
    __tablename__ = "idea_links"

    id = db.Column(db.Integer, primary_key=True)
    idea_id = db.Column(db.Integer, db.ForeignKey("ideas.id"), nullable=False, index=True)
    link_type = db.Column(db.String(30), nullable=False)
    link_id = db.Column(db.Integer, nullable=False)
    label = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "link_type": self.link_type,
            "link_id": self.link_id,
            "label": self.label or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class IdeaAttachment(db.Model):
    __tablename__ = "idea_attachments"

    id = db.Column(db.Integer, primary_key=True)
    idea_id = db.Column(db.Integer, db.ForeignKey("ideas.id"), nullable=False, index=True)
    url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(255), default="")
    kind = db.Column(db.String(30), default="url")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title or "",
            "kind": self.kind or "url",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


STORE_PRODUCT_STATUSES = ("active", "draft", "out_of_stock", "hidden")
STORE_ORDER_STATUSES = (
    "pending_payment", "paid", "processing", "packed", "shipped",
    "delivered", "cancelled", "refunded",
)


class StoreSettings(db.Model):
    __tablename__ = "store_settings"

    id = db.Column(db.Integer, primary_key=True)
    store_name = db.Column(db.String(255), default="Store")
    tagline = db.Column(db.String(500), default="")
    logo_url = db.Column(db.String(500), default="")
    currency = db.Column(db.String(10), default="USD")
    free_shipping_min_cents = db.Column(db.Integer, nullable=True)
    origin_name = db.Column(db.String(120), default="Store")
    origin_street = db.Column(db.String(255), default="")
    origin_city = db.Column(db.String(120), default="Greater Noida")
    origin_state = db.Column(db.String(80), default="UP")
    origin_zip = db.Column(db.String(20), default="201310")
    origin_country = db.Column(db.String(8), default="IN")
    origin_phone = db.Column(db.String(32), default="")
    origin_email = db.Column(db.String(255), default="")
    default_weight_kg = db.Column(db.Float, default=0.6)
    default_length_cm = db.Column(db.Float, default=20.0)
    default_width_cm = db.Column(db.Float, default=15.0)
    default_height_cm = db.Column(db.Float, default=8.0)
    customs_signer = db.Column(db.String(120), default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "store_name": self.store_name or "Store",
            "tagline": self.tagline or "",
            "logo_url": self.logo_url or "",
            "currency": self.currency or "USD",
            "free_shipping_min_cents": self.free_shipping_min_cents,
            "origin_name": self.origin_name or "Store",
            "origin_street": self.origin_street or "",
            "origin_city": self.origin_city or "Greater Noida",
            "origin_state": self.origin_state or "UP",
            "origin_zip": self.origin_zip or "201310",
            "origin_country": self.origin_country or "IN",
            "origin_phone": self.origin_phone or "",
            "origin_email": self.origin_email or "",
            "default_weight_kg": self.default_weight_kg if self.default_weight_kg is not None else 0.6,
            "default_length_cm": self.default_length_cm if self.default_length_cm is not None else 20,
            "default_width_cm": self.default_width_cm if self.default_width_cm is not None else 15,
            "default_height_cm": self.default_height_cm if self.default_height_cm is not None else 8,
            "customs_signer": self.customs_signer or "",
        }


class StoreCategory(db.Model):
    __tablename__ = "store_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship("StoreProduct", backref="category", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "sort_order": self.sort_order or 0,
        }


class StoreProduct(db.Model):
    __tablename__ = "store_products"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    short_description = db.Column(db.String(500), default="")
    description = db.Column(db.Text, default="")
    specifications = db.Column(db.Text, default="")
    sku = db.Column(db.String(80), default="")
    category_id = db.Column(db.Integer, db.ForeignKey("store_categories.id"), nullable=True, index=True)
    product_type = db.Column(db.String(20), default="physical")  # physical, digital
    status = db.Column(db.String(20), default="draft", index=True)
    price_cents = db.Column(db.Integer, default=0)
    sale_price_cents = db.Column(db.Integer, nullable=True)
    currency = db.Column(db.String(10), default="USD")
    quantity_available = db.Column(db.Integer, nullable=True)
    quantity_reserved = db.Column(db.Integer, default=0)
    shipping_required = db.Column(db.Boolean, default=True)
    free_shipping = db.Column(db.Boolean, default=False)
    weight_kg = db.Column(db.Float, nullable=True)
    length_cm = db.Column(db.Float, nullable=True)
    width_cm = db.Column(db.Float, nullable=True)
    height_cm = db.Column(db.Float, nullable=True)
    digital_delivery_url = db.Column(db.String(500), default="")
    digital_delivery_text = db.Column(db.Text, default="")
    keywords = db.Column(db.String(500), default="")
    preview_token = db.Column(db.String(64), default="")
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images = db.relationship(
        "StoreProductImage", backref="product", cascade="all, delete-orphan",
        lazy="dynamic", order_by="StoreProductImage.sort_order",
    )
    videos = db.relationship(
        "StoreProductVideo", backref="product", cascade="all, delete-orphan",
        lazy="dynamic", order_by="StoreProductVideo.sort_order",
    )
    options = db.relationship(
        "StoreProductOption", backref="product", cascade="all, delete-orphan",
        lazy="dynamic", order_by="StoreProductOption.sort_order",
    )

    def unit_price_cents(self):
        if self.sale_price_cents is not None and self.sale_price_cents >= 0:
            return int(self.sale_price_cents)
        return int(self.price_cents or 0)

    def sellable_quantity(self):
        if self.quantity_available is None:
            return None
        return max(0, (self.quantity_available or 0) - (self.quantity_reserved or 0))

    def is_public(self):
        return (self.status or "draft") == "active"

    def availability_label(self):
        if self.status == "hidden":
            return "Unavailable"
        if self.status == "draft":
            return "Draft"
        sellable = self.sellable_quantity()
        if sellable is not None and sellable <= 0:
            return "Out of stock"
        if self.status == "out_of_stock":
            return "Out of stock"
        if sellable is None:
            return "Available"
        return f"Available: {sellable}"

    def to_public_dict(self, include_media=True, related=None):
        images = [i.to_dict() for i in self.images.all()] if include_media else []
        videos = [v.to_dict() for v in self.videos.all()] if include_media else []
        options = [o.to_dict() for o in self.options.all() if o.values.count()] if include_media else []
        cover = images[0]["url"] if images else ""
        sellable = self.sellable_quantity()
        data = {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "short_description": self.short_description or "",
            "description": self.description or "",
            "specifications": self.specifications or "",
            "sku": self.sku or "",
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else "",
            "product_type": self.product_type or "physical",
            "status": "out_of_stock" if (sellable is not None and sellable <= 0) else (self.status or "draft"),
            "price_cents": self.price_cents or 0,
            "sale_price_cents": self.sale_price_cents,
            "unit_price_cents": self.unit_price_cents(),
            "currency": self.currency or "USD",
            "quantity_sellable": sellable,
            "availability": self.availability_label(),
            "in_stock": sellable is None or sellable > 0,
            "shipping_required": bool(self.shipping_required if self.product_type != "digital" else False),
            "free_shipping": bool(self.free_shipping),
            "weight_kg": self.weight_kg,
            "length_cm": self.length_cm,
            "width_cm": self.width_cm,
            "height_cm": self.height_cm,
            "cover_image": cover,
            "images": images,
            "videos": videos,
            "options": options,
            "keywords": self.keywords or "",
        }
        if related is not None:
            data["related"] = related
        return data

    def to_admin_dict(self):
        data = self.to_public_dict(include_media=True)
        data["quantity_available"] = self.quantity_available
        data["quantity_reserved"] = self.quantity_reserved or 0
        data["status"] = self.status or "draft"
        data["digital_delivery_url"] = self.digital_delivery_url or ""
        data["digital_delivery_text"] = self.digital_delivery_text or ""
        data["preview_token"] = self.preview_token or ""
        data["view_count"] = self.view_count or 0
        data["related_ids"] = [r.related_product_id for r in StoreProductRelated.query.filter_by(product_id=self.id).all()]
        data["created_at"] = self.created_at.isoformat() if self.created_at else None
        data["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        return data


class StoreProductImage(db.Model):
    __tablename__ = "store_product_images"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("store_products.id"), nullable=False, index=True)
    url = db.Column(db.String(500), nullable=False)
    alt_text = db.Column(db.String(255), default="")
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {"id": self.id, "url": self.url, "alt_text": self.alt_text or "", "sort_order": self.sort_order or 0}


class StoreProductVideo(db.Model):
    __tablename__ = "store_product_videos"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("store_products.id"), nullable=False, index=True)
    video_type = db.Column(db.String(20), default="youtube")  # youtube, vimeo, url, upload
    url = db.Column(db.String(500), nullable=False)
    embed_url = db.Column(db.String(500), default="")
    title = db.Column(db.String(255), default="")
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "video_type": self.video_type or "url",
            "url": self.url,
            "embed_url": self.embed_url or "",
            "title": self.title or "",
            "sort_order": self.sort_order or 0,
        }


class StoreProductOption(db.Model):
    __tablename__ = "store_product_options"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("store_products.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    values = db.relationship(
        "StoreProductOptionValue", backref="option", cascade="all, delete-orphan",
        lazy="dynamic", order_by="StoreProductOptionValue.sort_order",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "sort_order": self.sort_order or 0,
            "values": [v.to_dict() for v in self.values.all()],
        }


class StoreProductOptionValue(db.Model):
    __tablename__ = "store_product_option_values"

    id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.Integer, db.ForeignKey("store_product_options.id"), nullable=False, index=True)
    label = db.Column(db.String(80), nullable=False)
    extra_cents = db.Column(db.Integer, default=0)
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "extra_cents": self.extra_cents or 0,
            "sort_order": self.sort_order or 0,
        }


class StoreProductRelated(db.Model):
    __tablename__ = "store_product_related"
    __table_args__ = (db.UniqueConstraint("product_id", "related_product_id", name="uq_store_related"),)

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("store_products.id"), nullable=False, index=True)
    related_product_id = db.Column(db.Integer, db.ForeignKey("store_products.id"), nullable=False)


class ShippingCountry(db.Model):
    __tablename__ = "shipping_countries"

    id = db.Column(db.Integer, primary_key=True)
    country_name = db.Column(db.String(120), nullable=False)
    country_code = db.Column(db.String(8), default="")
    rate_cents = db.Column(db.Integer, default=0)
    currency = db.Column(db.String(10), default="USD")
    is_enabled = db.Column(db.Boolean, default=True)
    free_shipping = db.Column(db.Boolean, default=False)
    free_shipping_min_cents = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    regions = db.relationship(
        "ShippingRegion", backref="country", cascade="all, delete-orphan", lazy="dynamic"
    )

    def to_dict(self, include_regions=True):
        data = {
            "id": self.id,
            "country_name": self.country_name,
            "country_code": self.country_code or "",
            "rate_cents": self.rate_cents or 0,
            "currency": self.currency or "USD",
            "is_enabled": bool(self.is_enabled),
            "free_shipping": bool(self.free_shipping),
            "free_shipping_min_cents": self.free_shipping_min_cents,
        }
        if include_regions:
            data["regions"] = [r.to_dict() for r in self.regions.order_by(ShippingRegion.region_name.asc()).all()]
        return data


class ShippingRegion(db.Model):
    __tablename__ = "shipping_regions"

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey("shipping_countries.id"), nullable=False, index=True)
    region_name = db.Column(db.String(160), nullable=False)
    rate_cents = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "country_id": self.country_id,
            "region_name": self.region_name,
            "rate_cents": self.rate_cents or 0,
        }


class StoreCustomer(db.Model):
    __tablename__ = "store_customers"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False, default="")
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(32), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    google_sub = db.Column(db.String(64), unique=True, nullable=True, index=True)
    has_password = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = db.relationship("StoreOrder", backref="customer", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_admin=False):
        data = {
            "id": self.id,
            "full_name": self.full_name or "",
            "email": self.email or "",
            "phone": self.phone or "",
            "google": bool(self.google_sub),
            "has_password": bool(self.has_password),
        }
        if include_admin:
            data["created_at"] = self.created_at.isoformat() if self.created_at else None
            data["order_count"] = self.orders.count()
        return data


class StoreAccountHelpRequest(db.Model):
    __tablename__ = "store_account_help_requests"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), default="")
    email = db.Column(db.String(255), default="")
    phone = db.Column(db.String(64), default="")
    message = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="pending", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name or "",
            "email": self.email or "",
            "phone": self.phone or "",
            "message": self.message or "",
            "status": self.status or "pending",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StoreCustomerNotice(db.Model):
    __tablename__ = "store_customer_notices"

    id = db.Column(db.Integer, primary_key=True)
    store_customer_id = db.Column(db.Integer, db.ForeignKey("store_customers.id"), nullable=False, index=True)
    title = db.Column(db.String(255), default="")
    body = db.Column(db.Text, default="")
    kind = db.Column(db.String(40), default="message")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime, nullable=True)

    customer = db.relationship("StoreCustomer", backref="notices")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title or "",
            "body": self.body or "",
            "kind": self.kind or "message",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "read": bool(self.read_at),
        }


class StoreOrder(db.Model):
    __tablename__ = "store_orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(64), unique=True, nullable=False, index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=True, index=True)
    store_customer_id = db.Column(db.Integer, db.ForeignKey("store_customers.id"), nullable=True, index=True)
    customer_name = db.Column(db.String(255), default="")
    customer_email = db.Column(db.String(255), default="")
    customer_phone = db.Column(db.String(64), default="")
    ship_country = db.Column(db.String(120), default="")
    ship_region = db.Column(db.String(160), default="")
    ship_city = db.Column(db.String(160), default="")
    ship_address = db.Column(db.Text, default="")
    ship_postal = db.Column(db.String(32), default="")
    subtotal_cents = db.Column(db.Integer, default=0)
    discount_cents = db.Column(db.Integer, default=0)
    shipping_cents = db.Column(db.Integer, default=0)
    total_cents = db.Column(db.Integer, default=0)
    currency = db.Column(db.String(10), default="USD")
    payment_method = db.Column(db.String(20), default="")
    payment_status = db.Column(db.String(30), default="pending")
    order_status = db.Column(db.String(30), default="pending_payment", index=True)
    shipping_unavailable = db.Column(db.Boolean, default=False)
    shipping_note = db.Column(db.String(255), default="")
    requires_shipping = db.Column(db.Boolean, default=True)
    courier = db.Column(db.String(120), default="")
    tracking_number = db.Column(db.String(120), default="")
    tracking_url = db.Column(db.String(500), default="")
    shipping_carrier = db.Column(db.String(120), default="")
    shipping_service = db.Column(db.String(160), default="")
    shipping_zone = db.Column(db.String(120), default="")
    shipping_currency = db.Column(db.String(10), default="")
    shipping_estimated_days = db.Column(db.Integer, nullable=True)
    shippo_rate_id = db.Column(db.String(80), default="")
    shippo_shipment_id = db.Column(db.String(80), default="")
    shipment_weight_kg = db.Column(db.Float, nullable=True)
    shipment_length_cm = db.Column(db.Float, nullable=True)
    shipment_width_cm = db.Column(db.Float, nullable=True)
    shipment_height_cm = db.Column(db.Float, nullable=True)
    digital_delivery_json = db.Column(db.Text, default="[]")
    access_token = db.Column(db.String(64), unique=True, nullable=False, index=True, default=generate_token)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship("StoreOrderItem", backref="order", cascade="all, delete-orphan", lazy="dynamic")
    payment = db.relationship("Payment", foreign_keys=[payment_id], uselist=False)

    def to_dict(self, include_private=False, include_items=True):
        import json

        try:
            digital = json.loads(self.digital_delivery_json or "[]")
        except json.JSONDecodeError:
            digital = []
        data = {
            "id": self.id,
            "order_number": self.order_number,
            "payment_id": self.payment_id,
            "store_customer_id": self.store_customer_id,
            "customer_name": self.customer_name or "",
            "customer_email": self.customer_email or "",
            "customer_phone": self.customer_phone or "",
            "ship_country": self.ship_country or "",
            "ship_region": self.ship_region or "",
            "ship_city": self.ship_city or "",
            "ship_address": self.ship_address or "",
            "ship_postal": self.ship_postal or "",
            "subtotal_cents": self.subtotal_cents or 0,
            "discount_cents": self.discount_cents or 0,
            "shipping_cents": self.shipping_cents or 0,
            "total_cents": self.total_cents or 0,
            "currency": self.currency or "USD",
            "payment_method": self.payment_method or "",
            "payment_status": self.payment_status or "",
            "order_status": self.order_status or "",
            "requires_shipping": bool(self.requires_shipping),
            "courier": self.courier or "",
            "tracking_number": self.tracking_number or "",
            "tracking_url": self.tracking_url or "",
            "shipping_carrier": self.shipping_carrier or "",
            "shipping_service": self.shipping_service or "",
            "shipping_zone": self.shipping_zone or "",
            "shipping_currency": self.shipping_currency or "",
            "shipping_estimated_days": self.shipping_estimated_days,
            "shippo_rate_id": self.shippo_rate_id or "",
            "shippo_shipment_id": self.shippo_shipment_id or "",
            "shipment_weight_kg": self.shipment_weight_kg,
            "shipment_length_cm": self.shipment_length_cm,
            "shipment_width_cm": self.shipment_width_cm,
            "shipment_height_cm": self.shipment_height_cm,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "product_summary": ", ".join(
                f"{i.product_title} × {i.quantity}" for i in self.items.all()
            ),
            "receipt_url": (self.payment.receipt_url if self.payment else "") or "",
        }
        if include_items:
            data["items"] = [i.to_dict() for i in self.items.all()]
        if include_private:
            data["digital_delivery"] = digital
            data["access_token"] = self.access_token
            if self.payment:
                data["payment_reference"] = self.payment.payment_reference
                data["provider_payment_id"] = self.payment.provider_payment_id or ""
                data["receipt_url"] = self.payment.receipt_url or ""
        else:
            data["digital_delivery"] = digital if self.payment_status in ("succeeded", "paid") else []
        return data


class StoreOrderItem(db.Model):
    __tablename__ = "store_order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("store_orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("store_products.id"), nullable=True, index=True)
    product_title = db.Column(db.String(255), default="")
    product_slug = db.Column(db.String(180), default="")
    sku = db.Column(db.String(80), default="")
    quantity = db.Column(db.Integer, default=1)
    unit_price_cents = db.Column(db.Integer, default=0)
    extra_cents = db.Column(db.Integer, default=0)
    line_total_cents = db.Column(db.Integer, default=0)
    options_json = db.Column(db.Text, default="{}")
    product_type = db.Column(db.String(20), default="physical")

    product = db.relationship("StoreProduct")

    def to_dict(self):
        import json

        try:
            options = json.loads(self.options_json or "{}")
        except json.JSONDecodeError:
            options = {}
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_title": self.product_title or "",
            "product_slug": self.product_slug or "",
            "sku": self.sku or "",
            "quantity": self.quantity or 1,
            "unit_price_cents": self.unit_price_cents or 0,
            "extra_cents": self.extra_cents or 0,
            "line_total_cents": self.line_total_cents or 0,
            "options": options,
            "product_type": self.product_type or "physical",
        }


class FedexZoneRate(db.Model):
    """Admin override for a zone's FedEx price. Country mapping stays in fedex_zones.py."""
    __tablename__ = "fedex_zone_rates"

    id = db.Column(db.Integer, primary_key=True)
    zone_slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    rate_cents = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


