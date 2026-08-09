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
    content = db.Column(db.Text, nullable=False)
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
            "content": self.content,
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
