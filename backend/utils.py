from flask import current_app


def frontend_url(path=""):
    """Build a URL on the deployed frontend (GitHub Pages)."""
    base = current_app.config["FRONTEND_URL"].rstrip("/")
    if not path:
        return base
    return f"{base}/{path.lstrip('/')}"


def task_link_for_token(token):
    """Employee task link served by the static frontend."""
    return frontend_url(f"task.html?token={token}")
