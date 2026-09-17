import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from memreport.tts import clean_text_for_tts, get_or_create_report_audio, cleanup_report_audio
from memreport.config import AUDIO_CACHE_DIR


def test_clean_text_for_tts():
    raw = """
# 📖 Tagebucheintrag: 2026-09-16

**16. September 2026**

Manchmal spürt man schon beim ersten Blinzeln am Morgen, dass der Körper über Nacht echte Reparaturarbeit geleistet hat. Heute war genau so ein Tag in **Bruckmühl**.

---

## 🗺️ GPS Route: 2026-09-16 24385637186 Bruckmühl Gehen

```leaflet
{
  "title": "Route Bruckmühl",
  "coordinates": [[47.87, 11.95]]
}
```

## 📊 Statistiken

- Puls: 65 bpm
- Schlaf: 8 Stunden
"""
    cleaned = clean_text_for_tts(raw)
    assert "Tagebucheintrag" not in cleaned
    assert "16. September 2026" not in cleaned
    assert "GPS Route" not in cleaned
    assert "Statistiken" not in cleaned
    assert "Puls: 65" not in cleaned
    assert "Manchmal spürt man schon beim ersten Blinzeln am Morgen" in cleaned
    assert "Heute war genau so ein Tag in Bruckmühl." in cleaned


@pytest.mark.asyncio
async def test_get_or_create_report_audio_caching(tmp_path):
    user_id = 999
    date_str = "2026-09-16"
    content = "Hallo Welt, dies ist ein Testbericht für Vorlesen."

    # Mock gTTS so we don't hit external Google API
    with patch("memreport.tts.gTTS") as mock_gtts_cls:
        mock_instance = MagicMock()
        mock_gtts_cls.return_value = mock_instance

        def fake_save(path):
            Path(path).write_bytes(b"FAKE_MP3_DATA")

        mock_instance.save.side_effect = fake_save

        # 1st call: should generate
        audio_path_1 = await get_or_create_report_audio(user_id, date_str, content)
        assert audio_path_1.exists()
        assert audio_path_1.read_bytes() == b"FAKE_MP3_DATA"
        assert mock_instance.save.call_count == 1

        # 2nd call: should hit cache without calling gTTS save again
        audio_path_2 = await get_or_create_report_audio(user_id, date_str, content)
        assert audio_path_2 == audio_path_1
        assert mock_instance.save.call_count == 1  # No extra generation!

        # Cleanup
        cleanup_report_audio(user_id, date_str)
        assert not audio_path_1.exists()


@pytest.mark.asyncio
async def test_api_report_audio_endpoint(async_client, auth_headers):
    date_str = "2026-09-17"
    # Create report first
    res = await async_client.put(
        f"/api/reports/{date_str}",
        json={"content": "Mein heutiger Bericht zum Vorlesen.", "content_type": "markdown"},
        headers=auth_headers
    )
    assert res.status_code == 200

    with patch("memreport.tts.gTTS") as mock_gtts_cls:
        mock_instance = MagicMock()
        mock_gtts_cls.return_value = mock_instance
        mock_instance.save.side_effect = lambda p: Path(p).write_bytes(b"MP3_BYTES")

        # Fetch audio
        audio_res = await async_client.get(f"/api/reports/{date_str}/audio", headers=auth_headers)
        assert audio_res.status_code == 200
        assert audio_res.headers["content-type"] == "audio/mpeg"
        assert audio_res.content == b"MP3_BYTES"

        # Cleanup audio cache
        user_res = await async_client.get("/api/auth/me", headers=auth_headers)
        user_id = user_res.json()["id"]
        cleanup_report_audio(user_id, date_str)
