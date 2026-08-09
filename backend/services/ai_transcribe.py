"""Transcribe audio with Groq Whisper using the active API key."""

from services.groq_key_service import get_active_groq_config, mark_key_used


def transcribe_audio(file_storage):
    """
    Transcribe uploaded audio (webm, wav, mp3, etc.).
    Returns transcript text.
    """
    config = get_active_groq_config()
    if not config:
        raise RuntimeError("No Groq API key configured.")

    raw = file_storage.read()
    if not raw:
        raise ValueError("Empty audio file.")

    if len(raw) > 25 * 1024 * 1024:
        raise ValueError("Audio file is too large (max 25 MB).")

    filename = (file_storage.filename or "recording.webm").strip()
    if not filename:
        filename = "recording.webm"

    from groq import Groq

    client = Groq(api_key=config["api_key"])
    result = client.audio.transcriptions.create(
        file=(filename, raw),
        model="whisper-large-v3-turbo",
        language="en",
        response_format="text",
        temperature=0,
    )

    mark_key_used(config.get("key_id"))

    text = (result if isinstance(result, str) else getattr(result, "text", "") or "").strip()
    if not text:
        raise ValueError("No speech detected in the recording.")
    return text
