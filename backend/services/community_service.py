"""Community business logic."""

import json
import re
from datetime import datetime, timedelta

from models import (
    db,
    Community,
    CommunityComment,
    CommunityMembership,
    CommunityMemberUser,
    CommunityNotification,
    CommunityPost,
    CommunityPostLike,
    CommunityProduct,
    CommunityScheduledMessage,
    DEFAULT_COMMUNITY_REGISTRATION_FIELDS,
    generate_token,
)
from utils import community_link_for_token

URL_PATTERN = re.compile(r"https?://[^\s<]+", re.I)


def _community_or_error(community_id):
    c = Community.query.filter_by(id=community_id, deleted_at=None).first()
    if not c:
        raise ValueError("Community not found.")
    return c


def _community_by_token(token):
    c = Community.query.filter_by(community_token=token, deleted_at=None).first()
    if not c:
        raise ValueError("Community link is invalid.")
    return c


def list_communities():
    return Community.query.filter_by(deleted_at=None).order_by(Community.name.asc()).all()


def create_community(name):
    name = (name or "").strip()
    if not name:
        raise ValueError("Community name is required.")
    c = Community(
        name=name[:255],
        registration_fields_json=json.dumps(DEFAULT_COMMUNITY_REGISTRATION_FIELDS),
    )
    db.session.add(c)
    db.session.commit()
    return c


def update_community(community_id, data):
    c = _community_or_error(community_id)
    if data.get("name"):
        c.name = data["name"].strip()[:255]
    if data.get("description") is not None:
        c.description = (data.get("description") or "").strip()
    if data.get("approval_required") is not None:
        c.approval_required = bool(data["approval_required"])
    if data.get("members_visible") is not None:
        c.members_visible = bool(data["members_visible"])
    if data.get("registration_fields") is not None:
        c.registration_fields_json = json.dumps(data["registration_fields"])
    db.session.commit()
    return c


def delete_community(community_id):
    c = _community_or_error(community_id)
    c.deleted_at = datetime.utcnow()
    db.session.commit()


def community_dashboard(community_id):
    c = _community_or_error(community_id)
    memberships = CommunityMembership.query.filter_by(community_id=c.id)
    total = memberships.filter(CommunityMembership.status != "removed").count()
    active = memberships.filter_by(status="active").count()
    pending = memberships.filter_by(status="pending").count()
    posts = CommunityPost.query.filter_by(community_id=c.id, deleted_at=None).count()
    products = CommunityProduct.query.filter_by(community_id=c.id).count()
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_members = memberships.filter(
        CommunityMembership.joined_at >= week_ago,
        CommunityMembership.status != "removed",
    ).count()
    comments = CommunityComment.query.join(CommunityPost).filter(
        CommunityPost.community_id == c.id,
        CommunityComment.deleted_at.is_(None),
    ).count()
    return {
        "community": c.to_dict(include_link=True),
        "stats": {
            "total_members": total,
            "active_members": active,
            "pending_members": pending,
            "posts": posts,
            "products": products,
            "new_members_week": new_members,
            "comments": comments,
        },
        "community_link": community_link_for_token(c.community_token),
    }


def list_members(community_id, search=None, status=None):
    c = _community_or_error(community_id)
    q = CommunityMembership.query.filter_by(community_id=c.id)
    if status:
        q = q.filter_by(status=status)
    else:
        q = q.filter(CommunityMembership.status != "removed")
    rows = q.order_by(CommunityMembership.joined_at.desc()).all()
    if search:
        s = search.lower()
        rows = [
            m for m in rows
            if s in (m.member_user.username or "").lower()
            or s in (m.member_user.full_name or "").lower()
            or s in (m.member_user.email or "").lower()
        ]
    return [m.to_dict(include_private=True) for m in rows]


def get_membership(community_id, membership_id):
    m = CommunityMembership.query.filter_by(id=membership_id, community_id=community_id).first()
    if not m:
        raise ValueError("Member not found.")
    return m


def update_membership(community_id, membership_id, data):
    m = get_membership(community_id, membership_id)
    if data.get("status"):
        status = data["status"]
        if status not in ("pending", "active", "suspended", "removed"):
            raise ValueError("Invalid status.")
        m.status = status
        if status == "active":
            m.approved_at = datetime.utcnow()
            m.suspended_at = None
        if status == "suspended":
            m.suspended_at = datetime.utcnow()
    if data.get("background") is not None:
        m.background = (data.get("background") or "").strip()
    if data.get("why_join") is not None:
        m.why_join = (data.get("why_join") or "").strip()
    if data.get("experience_level") is not None:
        m.experience_level = (data.get("experience_level") or "").strip()[:120]
    if data.get("full_name") and m.member_user:
        m.member_user.full_name = data["full_name"].strip()[:255]
    db.session.commit()
    return m


def approve_member(community_id, membership_id):
    return update_membership(community_id, membership_id, {"status": "active"})


def suspend_member(community_id, membership_id):
    return update_membership(community_id, membership_id, {"status": "suspended"})


def restore_member(community_id, membership_id):
    return update_membership(community_id, membership_id, {"status": "active"})


def remove_member(community_id, membership_id):
    return update_membership(community_id, membership_id, {"status": "removed"})


def list_posts(community_id, after_id=None, viewer_member_id=None):
    _community_or_error(community_id)
    q = CommunityPost.query.filter_by(community_id=community_id, deleted_at=None)
    if after_id:
        q = q.filter(CommunityPost.id > after_id)
    posts = q.order_by(CommunityPost.created_at.asc()).all()
    return [p.to_dict(viewer_member_id=viewer_member_id) for p in posts]


def create_post(community_id, content, admin_id=None, member_user_id=None, image_url=None, is_announcement=False):
    c = _community_or_error(community_id)
    content = (content or "").strip()
    if not content and not image_url:
        raise ValueError("Post cannot be empty.")
    if member_user_id and image_url:
        raise ValueError("Only the admin can post images.")
    if member_user_id:
        m = CommunityMembership.query.filter_by(
            community_id=c.id, member_user_id=member_user_id, status="active"
        ).first()
        if not m:
            raise ValueError("You are not an active member of this community.")
        m.last_active_at = datetime.utcnow()
    post = CommunityPost(
        community_id=c.id,
        content=content,
        admin_id=admin_id,
        member_user_id=member_user_id,
        image_url=image_url or None,
        is_announcement=bool(is_announcement),
    )
    db.session.add(post)
    db.session.commit()
    return post


def delete_post(community_id, post_id):
    post = CommunityPost.query.filter_by(id=post_id, community_id=community_id, deleted_at=None).first()
    if not post:
        raise ValueError("Post not found.")
    post.deleted_at = datetime.utcnow()
    db.session.commit()


def toggle_like(post_id, member_user_id):
    post = CommunityPost.query.filter_by(id=post_id, deleted_at=None).first()
    if not post:
        raise ValueError("Post not found.")
    existing = CommunityPostLike.query.filter_by(post_id=post_id, member_user_id=member_user_id).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(CommunityPostLike(post_id=post_id, member_user_id=member_user_id))
        liked = True
    db.session.commit()
    return {"liked": liked, "likes": CommunityPostLike.query.filter_by(post_id=post_id).count()}


def list_comments(post_id):
    rows = (
        CommunityComment.query.filter_by(post_id=post_id, deleted_at=None, parent_id=None)
        .order_by(CommunityComment.created_at.asc())
        .all()
    )
    result = []
    for row in rows:
        d = row.to_dict()
        replies = (
            CommunityComment.query.filter_by(parent_id=row.id, deleted_at=None)
            .order_by(CommunityComment.created_at.asc())
            .all()
        )
        d["replies"] = [r.to_dict() for r in replies]
        result.append(d)
    return result


def create_comment(post_id, content, admin_id=None, member_user_id=None, parent_id=None):
    content = (content or "").strip()
    if not content:
        raise ValueError("Comment cannot be empty.")
    post = CommunityPost.query.filter_by(id=post_id, deleted_at=None).first()
    if not post:
        raise ValueError("Post not found.")
    if member_user_id:
        m = CommunityMembership.query.filter_by(
            community_id=post.community_id, member_user_id=member_user_id, status="active"
        ).first()
        if not m:
            raise ValueError("You are not an active member.")
    comment = CommunityComment(
        post_id=post_id,
        parent_id=parent_id,
        content=content,
        admin_id=admin_id,
        member_user_id=member_user_id,
    )
    db.session.add(comment)
    if member_user_id and post.member_user_id and post.member_user_id != member_user_id:
        db.session.add(
            CommunityNotification(
                community_id=post.community_id,
                member_user_id=post.member_user_id,
                kind="reply",
                message=f"Someone commented on your post.",
            )
        )
    db.session.commit()
    return comment


def delete_comment(comment_id):
    c = CommunityComment.query.get(comment_id)
    if not c or c.deleted_at:
        raise ValueError("Comment not found.")
    c.deleted_at = datetime.utcnow()
    db.session.commit()


def list_products(community_id):
    _community_or_error(community_id)
    rows = CommunityProduct.query.filter_by(community_id=community_id).order_by(CommunityProduct.created_at.desc()).all()
    return [p.to_dict() for p in rows]


def create_product(community_id, data):
    _community_or_error(community_id)
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Product name is required.")
    p = CommunityProduct(
        community_id=community_id,
        name=name[:255],
        description=(data.get("description") or "").strip(),
        image_url=(data.get("image_url") or "").strip()[:500],
        product_type=(data.get("product_type") or "physical").lower()[:20],
        price=(data.get("price") or "").strip()[:64],
        currency=(data.get("currency") or "USD").strip()[:10],
        purchase_url=(data.get("purchase_url") or "").strip()[:500],
        status=(data.get("status") or "available").lower()[:20],
    )
    db.session.add(p)
    db.session.commit()
    return p


def update_product(community_id, product_id, data):
    p = CommunityProduct.query.filter_by(id=product_id, community_id=community_id).first()
    if not p:
        raise ValueError("Product not found.")
    for field in ("name", "description", "image_url", "product_type", "price", "currency", "purchase_url", "status"):
        if data.get(field) is not None:
            setattr(p, field, (data.get(field) or "").strip())
    db.session.commit()
    return p


def delete_product(community_id, product_id):
    p = CommunityProduct.query.filter_by(id=product_id, community_id=community_id).first()
    if not p:
        raise ValueError("Product not found.")
    db.session.delete(p)
    db.session.commit()


def record_product_view(product_id):
    p = CommunityProduct.query.get(product_id)
    if p:
        p.view_count = (p.view_count or 0) + 1
        db.session.commit()


def register_member(token, data):
    c = _community_by_token(token)
    username = (data.get("username") or "").strip().lower()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip()
    if not username or not email or not password:
        raise ValueError("Username, email, and password are required.")
    if CommunityMemberUser.query.filter_by(username=username).first():
        raise ValueError("Username is already taken.")
    if CommunityMemberUser.query.filter_by(email=email).first():
        raise ValueError("Email is already registered.")
    user = CommunityMemberUser(username=username[:80], email=email[:255], full_name=full_name[:255])
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    status = "pending" if c.approval_required else "active"
    membership = CommunityMembership(
        community_id=c.id,
        member_user_id=user.id,
        status=status,
        background=(data.get("background") or "").strip(),
        why_join=(data.get("why_join") or "").strip(),
        experience_level=(data.get("experience_level") or "").strip()[:120],
        custom_fields_json=json.dumps(data.get("custom_fields") or {}),
        approved_at=datetime.utcnow() if status == "active" else None,
    )
    db.session.add(membership)
    db.session.commit()
    return user, membership


def login_member(username_or_email, password):
    key = (username_or_email or "").strip().lower()
    user = CommunityMemberUser.query.filter(
        (CommunityMemberUser.username == key) | (CommunityMemberUser.email == key)
    ).first()
    if not user or not user.check_password(password):
        raise ValueError("Invalid username/email or password.")
    return user


def get_member_memberships(member_user_id):
    rows = CommunityMembership.query.filter_by(member_user_id=member_user_id).filter(
        CommunityMembership.status.in_(["active", "pending", "suspended"])
    ).all()
    return rows


def membership_for_token(member_user_id, token):
    c = _community_by_token(token)
    return CommunityMembership.query.filter_by(community_id=c.id, member_user_id=member_user_id).first()


def list_scheduled_messages(community_id):
    _community_or_error(community_id)
    rows = CommunityScheduledMessage.query.filter_by(community_id=community_id).order_by(
        CommunityScheduledMessage.created_at.desc()
    ).all()
    return rows


def create_scheduled_message(community_id, data):
    _community_or_error(community_id)
    message = (data.get("message") or "").strip()
    if not message:
        raise ValueError("Message is required.")
    row = CommunityScheduledMessage(
        community_id=community_id,
        title=(data.get("title") or "").strip()[:255],
        message=message,
        schedule_kind=(data.get("schedule_kind") or "once").lower()[:20],
        schedule_time=(data.get("schedule_time") or "09:00")[:5],
        schedule_weekday=data.get("schedule_weekday"),
        is_announcement=bool(data.get("is_announcement", True)),
        is_active=bool(data.get("is_active", True)),
    )
    if data.get("scheduled_at"):
        try:
            row.scheduled_at = datetime.fromisoformat(data["scheduled_at"].replace("Z", ""))
        except ValueError:
            pass
    db.session.add(row)
    db.session.commit()
    from services.community_scheduler import compute_next_run

    row.next_run_at = compute_next_run(row)
    db.session.commit()
    return row


def update_scheduled_message(community_id, msg_id, data):
    row = CommunityScheduledMessage.query.filter_by(id=msg_id, community_id=community_id).first()
    if not row:
        raise ValueError("Scheduled message not found.")
    for field in ("title", "message", "schedule_kind", "schedule_time"):
        if data.get(field) is not None:
            setattr(row, field, (data.get(field) or "").strip())
    if data.get("schedule_weekday") is not None:
        row.schedule_weekday = data.get("schedule_weekday")
    if data.get("is_active") is not None:
        row.is_active = bool(data["is_active"])
    if data.get("is_announcement") is not None:
        row.is_announcement = bool(data["is_announcement"])
    if data.get("scheduled_at"):
        try:
            row.scheduled_at = datetime.fromisoformat(data["scheduled_at"].replace("Z", ""))
        except ValueError:
            pass
    from services.community_scheduler import compute_next_run

    row.next_run_at = compute_next_run(row)
    db.session.commit()
    return row


def delete_scheduled_message(community_id, msg_id):
    row = CommunityScheduledMessage.query.filter_by(id=msg_id, community_id=community_id).first()
    if not row:
        raise ValueError("Scheduled message not found.")
    db.session.delete(row)
    db.session.commit()


def send_community_announcement(community_id, message, admin_id=None, title=""):
    return create_post(
        community_id,
        message,
        admin_id=admin_id,
        is_announcement=True,
    )


def community_ai_summary():
    """Compact summary for AI / Mentor."""
    lines = ["COMMUNITIES:"]
    for c in list_communities():
        memberships = CommunityMembership.query.filter_by(community_id=c.id)
        active = memberships.filter_by(status="active").count()
        pending = memberships.filter_by(status="pending").count()
        posts = CommunityPost.query.filter_by(community_id=c.id, deleted_at=None).count()
        lines.append(
            f"- {c.name} (id={c.id}): {active} active members, {pending} pending, {posts} posts"
        )
    return "\n".join(lines)
