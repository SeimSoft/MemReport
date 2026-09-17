"""Text-to-Speech (TTS) module using Google TTS (gTTS) with local disk caching."""

import asyncio
import hashlib
import re
from pathlib import Path
from typing import Optional
from gtts import gTTS

from memreport.config import AUDIO_CACHE_DIR


def clean_text_for_tts(content: str) -> str:
    """
    Extract and clean only the initial diary prose text for TTS.
    Excludes title headers, date labels, and all subsequent sections
    (GPS routes, stats, charts, tables, subheadings).
    """
    if not content:
        return ""

    text = content.strip()

    # 1. Take only the section before any horizontal divider or level-2+ heading
    # e.g. '---', '***', '___' or '\n## '
    split_match = re.search(r"(\n\s*[-*_]{3,}\s*\n|\n\s*##+\s+)", text)
    if split_match:
        text = text[:split_match.start()]

    # 2. Split lines and filter out title headings and standalone date strings
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        # Skip markdown h1 heading
        if stripped.startswith("# ") or stripped.startswith("#\t"):
            continue
        # Skip standalone date lines like "**16. September 2026**" or "16.09.2026"
        clean_date = re.sub(r"[\*_~]", "", stripped).strip()
        if re.match(r"^(\d{1,2}\.?\s+[A-Za-zäöüÄÖÜ]+\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4})$", clean_date):
            continue
        lines.append(line)

    text = "\n".join(lines)

    # 3. Remove code blocks ```...``` (if any in intro)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`[^`\n]+`", " ", text)

    # 4. Remove base64 data URLs & images
    text = re.sub(r"data:image\/[a-zA-Z0-9\+\/=;,]+", " ", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)

    # 5. Convert Markdown links [text](url) to just text
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)

    # 6. Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # 7. Remove any remaining markdown headings
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)

    # 8. Remove list bullets and tables
    text = re.sub(r"^[>\-\*\+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\|", " ", text)

    # 9. Remove formatting symbols (*text*, **text**, _text_)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
    text = re.sub(r"~~(.*?)~~", r"\1", text)

    # 10. Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = text.strip()

    # Fallback: if empty, take first paragraph from original content without code/headings
    if not text:
        fallback = re.sub(r"```[\s\S]*?```", " ", content)
        fallback = re.sub(r"^#+.*$", "", fallback, flags=re.MULTILINE)
        fallback = re.sub(r"<[^>]+>", " ", fallback)
        fallback = re.sub(r"[ \t]+", " ", fallback).strip()
        paragraphs = [p.strip() for p in fallback.split("\n\n") if p.strip()]
        if paragraphs:
            text = paragraphs[0]

    return text


def _generate_gtts_file(text: str, lang: str, output_path: Path) -> None:
    """Synchronously generate gTTS mp3 file (called inside threadpool)."""
    tts = gTTS(text=text, lang=lang)
    temp_path = output_path.with_suffix(".tmp.mp3")
    tts.save(str(temp_path))
    temp_path.replace(output_path)


async def get_or_create_report_audio(
    user_id: int,
    date_str: str,
    raw_content: str,
    lang: str = "de",
) -> Optional[Path]:
    """
    Retrieve cached audio file for a report, or generate it via Google TTS.
    Returns the Path to the cached .mp3 file, or None if no readable text is present.
    """
    clean_text = clean_text_for_tts(raw_content)
    if not clean_text:
        return None

    # Compute a deterministic hash of the cleaned text
    content_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()[:12]
    audio_filename = f"{user_id}_{date_str}_{content_hash}.mp3"
    audio_path = AUDIO_CACHE_DIR / audio_filename

    # If cached file exists and has size > 0, serve directly from cache
    if audio_path.exists() and audio_path.stat().st_size > 0:
        return audio_path

    # Otherwise generate audio via Google TTS in threadpool
    await asyncio.to_thread(_generate_gtts_file, clean_text, lang, audio_path)
    return audio_path


def cleanup_report_audio(user_id: int, date_str: str) -> None:
    """Remove any cached audio files for a specific report date when deleted or updated."""
    try:
        prefix = f"{user_id}_{date_str}_"
        for p in AUDIO_CACHE_DIR.glob(f"{prefix}*.mp3"):
            try:
                p.unlink()
            except OSError:
                pass
    except Exception:
        pass
