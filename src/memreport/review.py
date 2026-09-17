"""AI Review module – uses Gemini to refine diary text based on user feedback."""

import asyncio
import re

from google import genai

from memreport.config import settings


def _extract_diary_prose(content: str) -> str:
    """
    Extract only the introductory diary prose from a full report.
    Same logic as TTS: everything before the first section divider or level-2+ heading.
    """
    if not content:
        return ""

    text = content.strip()

    # Cut at first horizontal divider or level-2+ heading
    split_match = re.search(r"(\n\s*[-*_]{3,}\s*\n|\n\s*##+\s+)", text)
    if split_match:
        text = text[:split_match.start()]

    return text.strip()


def _replace_diary_prose(full_content: str, new_prose: str) -> str:
    """
    Replace only the introductory diary prose in a full report, keeping
    all subsequent sections (stats, GPS routes, sleep data, etc.) intact.
    """
    content = full_content.strip()

    split_match = re.search(r"(\n\s*[-*_]{3,}\s*\n|\n\s*##+\s+)", content)
    if split_match:
        suffix = content[split_match.start():]
        return new_prose.strip() + suffix
    else:
        # No sections found – entire content is the prose
        return new_prose.strip()


async def review_report_with_gemini(
    original_content: str,
    user_feedback: str,
    model_name: str = "gemini-2.0-flash",
) -> str:
    """
    Send the diary prose + user correction instructions to Gemini and
    return the full updated report content (prose replaced, sections preserved).

    Raises ValueError if Gemini API key is not configured.
    Raises RuntimeError on Gemini API errors.
    """
    api_key = settings.gemini_api_key
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY ist nicht konfiguriert. "
            "Bitte setze die Umgebungsvariable GEMINI_API_KEY."
        )

    diary_prose = _extract_diary_prose(original_content)
    if not diary_prose:
        raise ValueError("Kein Tagebuchtext im Bericht gefunden.")

    # Build the prompt
    system_instruction = (
        "Du bist ein hilfreicher Assistent, der Tagebucheinträge korrigiert und verbessert. "
        "Du erhältst den Originaltext eines Tagebucheintrags und eine Korrekturanweisung des Benutzers. "
        "Schreibe den Text entsprechend um. Behalte den Stil und die Sprache des Originals bei. "
        "Gib NUR den korrigierten Tagebuchtext zurück, ohne Erklärungen, ohne Markdown-Codeblöcke, "
        "ohne zusätzliche Kommentare. Der Text soll direkt als Markdown-Tagebucheintrag nutzbar sein."
    )

    prompt = (
        f"## Originaltext des Tagebucheintrags:\n\n"
        f"{diary_prose}\n\n"
        f"## Korrekturanweisung des Benutzers:\n\n"
        f"{user_feedback}\n\n"
        f"## Aufgabe:\n\n"
        f"Schreibe den Tagebuchtext gemäß der Korrekturanweisung um. "
        f"Gib NUR den korrigierten Text zurück."
    )

    try:
        client = genai.Client(api_key=api_key)

        # Run the blocking API call in a thread pool
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_name,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction,
            ),
        )

        corrected_prose = response.text.strip()

        # Remove any wrapping ```markdown ... ``` if Gemini adds them
        if corrected_prose.startswith("```"):
            lines = corrected_prose.split("\n")
            # Remove first line (```markdown) and last line (```)
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            elif lines[0].strip().startswith("```"):
                lines = lines[1:]
            corrected_prose = "\n".join(lines).strip()

        # Replace only the prose section, keep stats/routes/etc.
        updated_content = _replace_diary_prose(original_content, corrected_prose)
        return updated_content

    except Exception as e:
        error_msg = str(e)
        if "API_KEY" in error_msg.upper() or "authentication" in error_msg.lower():
            raise ValueError(f"Gemini API-Schlüssel ungültig: {error_msg}")
        raise RuntimeError(f"Gemini-Fehler: {error_msg}")
