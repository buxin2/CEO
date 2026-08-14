"""Upload group chat images to Cloudinary (admin-only uploads)."""

import os

import cloudinary
import cloudinary.uploader
from flask import current_app

ALLOWED_IMAGE_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/heic",
    "image/heif",
})
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def _configure_cloudinary():
    url = (current_app.config.get("CLOUDINARY_URL") or "").strip()
    if url:
        cloudinary.config(cloudinary_url=url, secure=True)
        return True
    cloud_name = (current_app.config.get("CLOUDINARY_CLOUD_NAME") or "").strip()
    api_key = (current_app.config.get("CLOUDINARY_API_KEY") or "").strip()
    api_secret = (current_app.config.get("CLOUDINARY_API_SECRET") or "").strip()
    if cloud_name and api_key and api_secret:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )
        return True
    return False


def is_cloudinary_configured():
    try:
        return _configure_cloudinary()
    except RuntimeError:
        return bool(
            os.environ.get("CLOUDINARY_URL")
            or (
                os.environ.get("CLOUDINARY_CLOUD_NAME")
                and os.environ.get("CLOUDINARY_API_KEY")
                and os.environ.get("CLOUDINARY_API_SECRET")
            )
        )


def upload_group_chat_image(file_storage, company_id):
    """Upload image file; returns secure_url and public_id."""
    if not _configure_cloudinary():
        raise RuntimeError(
            "Image upload is not configured. Set CLOUDINARY_URL on the server."
        )

    if not file_storage or not file_storage.filename:
        raise ValueError("No image file provided.")

    content_type = (file_storage.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("Only image files are allowed (JPEG, PNG, GIF, WebP).")

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_IMAGE_BYTES:
        raise ValueError("Image is too large. Maximum size is 10 MB.")

    folder = f"group-chat/company-{company_id}"
    result = cloudinary.uploader.upload(
        file_storage,
        folder=folder,
        resource_type="image",
    )
    url = result.get("secure_url") or result.get("url")
    if not url:
        raise RuntimeError("Cloudinary upload failed.")
    return {
        "url": url,
        "public_id": result.get("public_id") or "",
        "width": result.get("width"),
        "height": result.get("height"),
    }
