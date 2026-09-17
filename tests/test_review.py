"""Tests for the AI review module – fully offline, no API calls."""

import pytest
from unittest.mock import patch, MagicMock
from memreport.review import _extract_diary_prose, _replace_diary_prose


# --- Unit tests for prose extraction & replacement (no API calls) ---


class TestExtractDiaryProse:
    """Test the diary prose extraction logic."""

    def test_extracts_prose_before_divider(self):
        content = """# 📖 Tagebucheintrag

**16. September 2026**

Manchmal spürt man schon beim ersten Blinzeln, dass der Tag etwas Besonderes werden könnte.

---

## 🗺️ GPS Route

Some route data here.
"""
        result = _extract_diary_prose(content)
        assert "Manchmal spürt man" in result
        assert "GPS Route" not in result
        assert "Some route data" not in result

    def test_extracts_prose_before_heading(self):
        content = """# Bericht

Ein schöner Tag voller Überraschungen.

## Schlaf

8 Stunden geschlafen.
"""
        result = _extract_diary_prose(content)
        assert "schöner Tag" in result
        assert "Schlaf" not in result
        assert "8 Stunden" not in result

    def test_empty_content(self):
        assert _extract_diary_prose("") == ""
        assert _extract_diary_prose(None) == ""

    def test_no_sections(self):
        content = "Heute war ein normaler Tag."
        result = _extract_diary_prose(content)
        assert result == "Heute war ein normaler Tag."


class TestReplaceDiaryProse:
    """Test replacing only the prose section while preserving the rest."""

    def test_replaces_prose_preserves_sections(self):
        original = """# Titel

Alter Text hier.

---

## Statistiken

| Metrik | Wert |
|--------|------|
| Schritte | 5000 |
"""
        new_prose = "# Titel\n\nNeuer korrigierter Text."
        result = _replace_diary_prose(original, new_prose)
        assert "Neuer korrigierter Text" in result
        assert "Alter Text" not in result
        assert "## Statistiken" in result
        assert "Schritte" in result

    def test_no_sections_replaces_all(self):
        original = "Nur ein einfacher Text."
        result = _replace_diary_prose(original, "Korrigierter Text.")
        assert result == "Korrigierter Text."

    def test_preserves_gps_section(self):
        original = """Intro text.

## 🗺️ GPS Route

```leaflet
coordinates: [[47.0, 11.0], [47.1, 11.1]]
```
"""
        result = _replace_diary_prose(original, "New intro text.")
        assert "New intro text." in result
        assert "GPS Route" in result
        assert "leaflet" in result


class TestReviewEndpointMocked:
    """Test the review API integration with mocked Gemini (zero API calls)."""

    @pytest.mark.asyncio
    async def test_review_replaces_prose_via_mock(self):
        """Verify the full flow with a mocked Gemini response."""
        from memreport.review import review_report_with_gemini

        original = """# 📖 Tagebucheintrag

**16. September 2026**

Heute war es bewölkt und kalt.

---

## Statistiken

Schritte: 5000
"""
        mock_response = MagicMock()
        mock_response.text = "# 📖 Tagebucheintrag\n\n**16. September 2026**\n\nHeute war es sonnig und warm."

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("memreport.review.genai.Client", return_value=mock_client), \
             patch("memreport.review.settings") as mock_settings:
            mock_settings.gemini_api_key = "fake-key-for-test"

            result = await review_report_with_gemini(
                original_content=original,
                user_feedback="Es war sonnig und warm, nicht bewölkt und kalt.",
            )

        # Prose replaced
        assert "sonnig und warm" in result
        # Stats preserved
        assert "## Statistiken" in result
        assert "Schritte: 5000" in result
        # Old prose gone
        assert "bewölkt und kalt" not in result

    @pytest.mark.asyncio
    async def test_review_raises_without_api_key(self):
        """Should raise ValueError when no API key is configured."""
        from memreport.review import review_report_with_gemini

        with patch("memreport.review.settings") as mock_settings:
            mock_settings.gemini_api_key = None

            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                await review_report_with_gemini(
                    original_content="Some text",
                    user_feedback="Fix it",
                )

    @pytest.mark.asyncio
    async def test_review_raises_on_empty_prose(self):
        """Should raise ValueError when no diary prose is found."""
        from memreport.review import review_report_with_gemini

        with patch("memreport.review.settings") as mock_settings:
            mock_settings.gemini_api_key = "fake-key"

            with pytest.raises(ValueError, match="Kein Tagebuchtext"):
                await review_report_with_gemini(
                    original_content="",
                    user_feedback="Fix it",
                )
