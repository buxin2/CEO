"""Store media helpers: YouTube/Vimeo embeds and Cloudinary uploads."""

import os
import re

from services.cloudinary_service import (
    ALLOWED_IMAGE_TYPES,
    MAX_IMAGE_BYTES,
    _configure_cloudinary,
)

ALLOWED_VIDEO_TYPES = frozenset({
    "video/mp4",
    "video/webm",
    "video/quicktime",
})
MAX_VIDEO_BYTES = 80 * 1024 * 1024

_YT_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([A-Za-z0-9_-]{6,})"),
]
_VIMEO_RE = re.compile(r"vimeo\.com/(?:video/)?(\d+)")


def sanitize_html(text):
    raw = text or ""
    raw = re.sub(r"(?is)<script.*?>.*?</script>", "", raw)
    raw = re.sub(r"(?is)<iframe(?![^>]*youtube)(?![^>]*vimeo).*?>.*?</iframe>", "", raw)
    raw = re.sub(r"(?i)\son\w+\s*=", " ", raw)
    raw = re.sub(r"(?i)javascript:", "", raw)
    return raw


def parse_video_link(url):
    url = (url or "").strip()
    if not url:
        raise ValueError("Video URL is required.")
    for pat in _YT_PATTERNS:
        m = pat.search(url)
        if m:
            vid = m.group(1)
            return {
                "video_type": "youtube",
                "url": url,
                "embed_url": f"https://www.youtube.com/embed/{vid}",
            }
    m = _VIMEO_RE.search(url)
    if m:
        vid = m.group(1)
        return {
            "video_type": "vimeo",
            "url": url,
            "embed_url": f"https://player.vimeo.com/video/{vid}",
        }
    if url.lower().endswith((".mp4", ".webm", ".mov")) or url.startswith("http"):
        return {"video_type": "url", "url": url, "embed_url": url}
    raise ValueError("Unsupported video link. Use YouTube, Vimeo, or a direct video URL.")


def upload_store_image(file_storage, product_id):
    if not _configure_cloudinary():
        raise RuntimeError("Image upload is not configured. Open AI Assistant → Cloudinary settings.")
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
    import cloudinary.uploader

    result = cloudinary.uploader.upload(
        file_storage,
        folder=f"store/products/{product_id}",
        resource_type="image",
    )
    url = result.get("secure_url") or result.get("url")
    if not url:
        raise RuntimeError("Cloudinary upload failed.")
    return {"url": url, "public_id": result.get("public_id") or ""}


def upload_store_video(file_storage, product_id):
    if not _configure_cloudinary():
        raise RuntimeError("Video upload is not configured. Open AI Assistant → Cloudinary settings.")
    if not file_storage or not file_storage.filename:
        raise ValueError("No video file provided.")
    content_type = (file_storage.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in ALLOWED_VIDEO_TYPES:
        raise ValueError("Only MP4, WebM, or MOV videos are allowed.")
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_VIDEO_BYTES:
        raise ValueError("Video is too large. Maximum size is 80 MB.")
    import cloudinary.uploader

    result = cloudinary.uploader.upload(
        file_storage,
        folder=f"store/products/{product_id}/videos",
        resource_type="video",
    )
    url = result.get("secure_url") or result.get("url")
    if not url:
        raise RuntimeError("Cloudinary upload failed.")
    return {"url": url, "public_id": result.get("public_id") or "", "video_type": "upload", "embed_url": url}
