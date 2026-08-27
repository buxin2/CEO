"""Community API — admin management and member portal."""

from functools import wraps

from flask import Blueprint, jsonify, request, session

from routes.auth import login_required
from services.community_service import (
    approve_member,
    community_dashboard,
    create_comment,
    create_community,
    create_post,
    create_product,
    create_scheduled_message,
    delete_comment,
    delete_community,
    delete_post,
    delete_product,
    delete_scheduled_message,
    get_member_memberships,
    get_membership,
    join_community_for_store_customer,
    list_communities,
    list_communities_for_store_customer,
    list_comments,
    list_members,
    list_posts,
    list_products,
    list_scheduled_messages,
    login_member,
    membership_for_token,
    record_product_view,
    register_member,
    member_has_community_access,
    remove_member,
    restore_member,
    set_community_image,
    suspend_member,
    toggle_like,
    update_community,
    update_membership,
    update_product,
    update_scheduled_message,
)
from models import db, CommunityMemberUser, CommunityMembership, CommunityNotification

community_bp = Blueprint("community", __name__)


def _community_by_token_param(token):
    from services.community_service import _community_by_token

    return _community_by_token(token)


def resolve_community_member_id():
    uid = session.get("cm_user_id")
    if uid:
        return uid
    from services.store_customer_service import current_store_customer

    customer = current_store_customer()
    if not customer or not (customer.email or "").strip():
        return None
    user = CommunityMemberUser.query.filter_by(email=customer.email.strip().lower()).first()
    if not user:
        return None
    session["cm_user_id"] = user.id
    session.permanent = True
    return user.id


def community_member_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not resolve_community_member_id():
            return jsonify({"error": "Please log in to continue."}), 401
        return f(*args, **kwargs)

    return decorated


# ---------- Admin: communities ----------


@community_bp.route("/api/communities", methods=["GET"])
@login_required
def api_list_communities():
    rows = list_communities()
    return jsonify({"communities": [c.to_dict(include_link=True) for c in rows]})


@community_bp.route("/api/communities", methods=["POST"])
@login_required
def api_create_community():
    if request.files or request.form:
        data = {k: request.form.get(k) for k in request.form.keys()}
        try:
            c = create_community(data.get("name"), data)
            upload = request.files.get("image") or request.files.get("file")
            if upload and upload.filename:
                c = set_community_image(c.id, upload)
            return jsonify(c.to_dict(include_link=True)), 201
        except (ValueError, RuntimeError) as exc:
            return jsonify({"error": str(exc)}), 400
    data = request.get_json(silent=True) or {}
    try:
        c = create_community(data.get("name"), data)
        return jsonify(c.to_dict(include_link=True)), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/communities/<int:community_id>/image", methods=["POST"])
@login_required
def api_community_image(community_id):
    upload = request.files.get("image") or request.files.get("file")
    if not upload:
        return jsonify({"error": "Choose an image."}), 400
    try:
        c = set_community_image(community_id, upload)
        return jsonify(c.to_dict(include_link=True))
    except (ValueError, RuntimeError) as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/communities/<int:community_id>", methods=["GET"])
@login_required
def api_community_dashboard(community_id):
    try:
        return jsonify(community_dashboard(community_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@community_bp.route("/api/communities/<int:community_id>", methods=["PUT"])
@login_required
def api_update_community(community_id):
    data = request.get_json(silent=True) or {}
    try:
        c = update_community(community_id, data)
        return jsonify(c.to_dict(include_link=True))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/communities/<int:community_id>", methods=["DELETE"])
@login_required
def api_delete_community(community_id):
    try:
        delete_community(community_id)
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


# ---------- Admin: members ----------


@community_bp.route("/api/communities/<int:community_id>/members", methods=["GET"])
@login_required
def api_admin_members(community_id):
    search = request.args.get("search")
    status = request.args.get("status")
    try:
        return jsonify({"members": list_members(community_id, search=search, status=status)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@community_bp.route("/api/communities/<int:community_id>/members/<int:membership_id>", methods=["GET"])
@login_required
def api_admin_member_detail(community_id, membership_id):
    try:
        m = get_membership(community_id, membership_id)
        return jsonify(m.to_dict(include_private=True))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@community_bp.route("/api/communities/<int:community_id>/members/<int:membership_id>", methods=["PUT"])
@login_required
def api_admin_member_update(community_id, membership_id):
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    try:
        if action == "approve":
            m = approve_member(community_id, membership_id)
        elif action == "suspend":
            m = suspend_member(community_id, membership_id)
        elif action == "restore":
            m = restore_member(community_id, membership_id)
        elif action == "remove":
            m = remove_member(community_id, membership_id)
        else:
            m = update_membership(community_id, membership_id, data)
        return jsonify(m.to_dict(include_private=True))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


# ---------- Admin: posts ----------


@community_bp.route("/api/communities/<int:community_id>/posts", methods=["GET"])
@login_required
def api_admin_posts(community_id):
    after_id = request.args.get("after_id", type=int)
    try:
        return jsonify({"posts": list_posts(community_id, after_id=after_id)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@community_bp.route("/api/communities/<int:community_id>/posts", methods=["POST"])
@login_required
def api_admin_create_post(community_id):
    data = request.get_json(silent=True) or {}
    try:
        post = create_post(
            community_id,
            data.get("content"),
            admin_id=session.get("admin_id"),
            image_url=data.get("image_url"),
            is_announcement=bool(data.get("is_announcement")),
        )
        return jsonify(post.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/communities/<int:community_id>/posts/image", methods=["POST"])
@login_required
def api_admin_post_image(community_id):
    upload = request.files.get("image")
    if not upload:
        return jsonify({"error": "Image file is required."}), 400
    from services.cloudinary_service import upload_community_image

    try:
        uploaded = upload_community_image(upload, community_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    content = (request.form.get("content") or "").strip()
    is_ann = request.form.get("is_announcement") in ("1", "true", "yes")
    try:
        post = create_post(
            community_id,
            content,
            admin_id=session.get("admin_id"),
            image_url=uploaded["url"],
            is_announcement=is_ann,
        )
        return jsonify(post.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/communities/<int:community_id>/posts/<int:post_id>", methods=["DELETE"])
@login_required
def api_admin_delete_post(community_id, post_id):
    try:
        delete_post(community_id, post_id)
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@community_bp.route("/api/communities/<int:community_id>/posts/<int:post_id>/comments", methods=["GET"])
@login_required
def api_admin_comments(community_id, post_id):
    return jsonify({"comments": list_comments(post_id)})


@community_bp.route("/api/communities/<int:community_id>/posts/<int:post_id>/comments", methods=["POST"])
@login_required
def api_admin_comment(community_id, post_id):
    data = request.get_json(silent=True) or {}
    try:
        c = create_comment(
            post_id,
            data.get("content"),
            admin_id=session.get("admin_id"),
            parent_id=data.get("parent_id"),
        )
        return jsonify(c.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/communities/<int:community_id>/comments/<int:comment_id>", methods=["DELETE"])
@login_required
def api_admin_delete_comment(community_id, comment_id):
    try:
        delete_comment(comment_id)
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


# ---------- Admin: products ----------


@community_bp.route("/api/communities/<int:community_id>/products", methods=["GET"])
@login_required
def api_admin_products(community_id):
    try:
        return jsonify({"products": list_products(community_id)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@community_bp.route("/api/communities/<int:community_id>/products", methods=["POST"])
@login_required
def api_admin_create_product(community_id):
    data = request.get_json(silent=True) or {}
    try:
        p = create_product(community_id, data)
        return jsonify(p.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/communities/<int:community_id>/products/<int:product_id>", methods=["PUT"])
@login_required
def api_admin_update_product(community_id, product_id):
    data = request.get_json(silent=True) or {}
    try:
        p = update_product(community_id, product_id, data)
        return jsonify(p.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/communities/<int:community_id>/products/<int:product_id>", methods=["DELETE"])
@login_required
def api_admin_delete_product(community_id, product_id):
    try:
        delete_product(community_id, product_id)
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


# ---------- Admin: scheduled messages ----------


@community_bp.route("/api/communities/<int:community_id>/scheduled-messages", methods=["GET"])
@login_required
def api_scheduled_list(community_id):
    try:
        rows = list_scheduled_messages(community_id)
        return jsonify({"messages": [r.to_dict() for r in rows]})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@community_bp.route("/api/communities/<int:community_id>/scheduled-messages", methods=["POST"])
@login_required
def api_scheduled_create(community_id):
    data = request.get_json(silent=True) or {}
    try:
        row = create_scheduled_message(community_id, data)
        return jsonify(row.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/communities/<int:community_id>/scheduled-messages/<int:msg_id>", methods=["PUT"])
@login_required
def api_scheduled_update(community_id, msg_id):
    data = request.get_json(silent=True) or {}
    try:
        row = update_scheduled_message(community_id, msg_id, data)
        return jsonify(row.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/communities/<int:community_id>/scheduled-messages/<int:msg_id>", methods=["DELETE"])
@login_required
def api_scheduled_delete(community_id, msg_id):
    try:
        delete_scheduled_message(community_id, msg_id)
        return jsonify({"success": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


# ---------- Member auth ----------


@community_bp.route("/api/community-auth/register/<token>", methods=["POST"])
def api_member_register(token):
    data = request.get_json(silent=True) or {}
    try:
        user, membership = register_member(token, data)
        session["cm_user_id"] = user.id
        session.permanent = True
        checkout_url = None
        if membership.status == "pending_payment":
            checkout_url = f"checkout.html?membership_id={membership.id}&token={token}"
        return jsonify({
            "success": True,
            "status": membership.status,
            "membership_id": membership.id,
            "needs_payment": membership.status == "pending_payment",
            "checkout_url": checkout_url,
            "user": user.to_dict(private=True),
        }), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/public/community/<token>/join", methods=["POST"])
def api_public_community_join(token):
    from services.store_customer_service import current_store_customer

    customer = current_store_customer()
    if not customer:
        return jsonify({"error": "Sign in first."}), 401
    try:
        user, membership = join_community_for_store_customer(token, customer)
        session["cm_user_id"] = user.id
        session.permanent = True
        refresh = membership
        checkout_url = None
        if refresh.status == "pending_payment":
            checkout_url = f"checkout.html?membership_id={refresh.id}&token={token}"
        return jsonify({
            "success": True,
            "status": refresh.status,
            "membership_id": refresh.id,
            "needs_payment": refresh.status == "pending_payment",
            "checkout_url": checkout_url,
            "user": user.to_dict(private=True),
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/community-auth/login", methods=["POST"])
def api_member_login():
    data = request.get_json(silent=True) or {}
    try:
        user = login_member(data.get("username") or data.get("email"), data.get("password"))
        session.clear()
        session["cm_user_id"] = user.id
        session.permanent = True
        return jsonify({"success": True, "user": user.to_dict(private=True)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 401


@community_bp.route("/api/community-auth/logout", methods=["POST"])
def api_member_logout():
    session.clear()
    return jsonify({"success": True})


@community_bp.route("/api/community-auth/me", methods=["GET"])
def api_member_me():
    uid = resolve_community_member_id()
    if not uid:
        return jsonify({"authenticated": False}), 401
    user = CommunityMemberUser.query.get(uid)
    if not user:
        session.clear()
        return jsonify({"authenticated": False}), 401
    memberships = [
        {
            "community_id": m.community_id,
            "community_name": m.community.name if m.community else "",
            "status": m.status,
            **m.to_dict(),
        }
        for m in get_member_memberships(uid)
    ]
    return jsonify({"authenticated": True, "user": user.to_dict(private=True), "memberships": memberships})


@community_bp.route("/api/community-auth/profile", methods=["PUT"])
@community_member_required
def api_member_profile():
    uid = session.get("cm_user_id")
    user = CommunityMemberUser.query.get(uid)
    data = request.get_json(silent=True) or {}
    if data.get("full_name") is not None:
        user.full_name = (data.get("full_name") or "").strip()[:255]
    if data.get("password"):
        user.set_password(data["password"])
    db.session.commit()
    return jsonify(user.to_dict(private=True))


# ---------- Public community portal ----------


@community_bp.route("/api/public/community/<token>", methods=["GET"])
def api_public_community_info(token):
    try:
        c = _community_by_token_param(token)
        return jsonify({
            "name": c.name,
            "description": c.description or "",
            "image_url": c.image_url or "",
            "community_token": c.community_token,
            "approval_required": bool(c.approval_required),
            "members_visible": bool(c.members_visible),
            "community_type": c.community_type or "free",
            "price_cents": c.price_cents or 0,
            "currency": c.currency or "USD",
            "billing_interval": c.billing_interval or "one_time",
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@community_bp.route("/api/public/community/<token>/posts", methods=["GET"])
def api_public_posts(token):
    try:
        c = _community_by_token_param(token)
        viewer = resolve_community_member_id()
        if viewer and not member_has_community_access(viewer, c.id):
            membership = membership_for_token(viewer, token)
            if membership and membership.status == "pending_payment":
                return jsonify({"error": "Payment required.", "needs_payment": True, "membership_id": membership.id}), 403
            return jsonify({"error": "You do not have access to this community."}), 403
        after_id = request.args.get("after_id", type=int)
        return jsonify({"posts": list_posts(c.id, after_id=after_id, viewer_member_id=viewer)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@community_bp.route("/api/public/community/<token>/posts", methods=["POST"])
@community_member_required
def api_public_create_post(token):
    try:
        c = _community_by_token_param(token)
        data = request.get_json(silent=True) or {}
        post = create_post(c.id, data.get("content"), member_user_id=resolve_community_member_id())
        return jsonify(post.to_dict(viewer_member_id=resolve_community_member_id())), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/public/community/<token>/posts/<int:post_id>/like", methods=["POST"])
@community_member_required
def api_public_like(token, post_id):
    try:
        return jsonify(toggle_like(post_id, resolve_community_member_id()))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/public/community/<token>/posts/<int:post_id>/comments", methods=["GET"])
def api_public_comments(token, post_id):
    return jsonify({"comments": list_comments(post_id)})


@community_bp.route("/api/public/community/<token>/posts/<int:post_id>/comments", methods=["POST"])
@community_member_required
def api_public_comment(token, post_id):
    data = request.get_json(silent=True) or {}
    try:
        c = create_comment(
            post_id,
            data.get("content"),
            member_user_id=resolve_community_member_id(),
            parent_id=data.get("parent_id"),
        )
        return jsonify(c.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@community_bp.route("/api/public/community/<token>/products", methods=["GET"])
def api_public_products(token):
    try:
        c = _community_by_token_param(token)
        return jsonify({"products": list_products(c.id)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@community_bp.route("/api/public/community/<token>/products/<int:product_id>/view", methods=["POST"])
def api_public_product_view(token, product_id):
    record_product_view(product_id)
    return jsonify({"success": True})


@community_bp.route("/api/public/community/<token>/membership", methods=["GET"])
@community_member_required
def api_public_my_membership(token):
    try:
        m = membership_for_token(resolve_community_member_id(), token)
        if not m:
            return jsonify({"error": "You are not a member of this community."}), 404
        return jsonify(m.to_dict(include_private=True))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@community_bp.route("/api/public/community/<token>/notifications", methods=["GET"])
@community_member_required
def api_public_notifications(token):
    try:
        c = _community_by_token_param(token)
        uid = resolve_community_member_id()
        rows = (
            CommunityNotification.query.filter_by(community_id=c.id, member_user_id=uid)
            .order_by(CommunityNotification.created_at.desc())
            .limit(30)
            .all()
        )
        return jsonify({
            "notifications": [
                {
                    "id": n.id,
                    "kind": n.kind,
                    "message": n.message,
                    "read_at": n.read_at.isoformat() if n.read_at else None,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                }
                for n in rows
            ]
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
