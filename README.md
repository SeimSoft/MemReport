# MemReport 🚀

**MemReport** ist eine vollwertige Python-Webanwendung auf Basis von **FastAPI** und **Uvicorn**, die eine REST-API bereitstellt und ein dynamisches Web-Dashboard hostet.

---

## Highlights

- **Multi-Format Reports**: Berichte können Markdown und HTML beliebig mischen.
- **LaTeX Math Support**: KaTeX-Integration für Inline- (`$E=mc^2$`) und Blockformeln (`$$\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}$$`).
- **Syntax Highlighting**: Automatische Code-Hervorhebung mit Highlight.js für Python, Bash, JSON uvm.
- **Base64-Grafiken**: Vollständig eingebettete Bilder (`data:image/png;base64,...`) in Markdown und HTML.
- **Interaktiver Kalender**: Übersichtliche Monatsansicht in der Sidebar mit Indikatoren für Tage mit Berichten und GPS-Punkten.
- **Append & Overwrite**: Mehrere Uploads für einen Tag werden standardmäßig angehängt (`overwrite=false`) oder überschrieben (`overwrite=true`).
- **In-Viewer Texteditor**: Berichte können direkt im Web-Viewer bearbeitet und gespeichert werden.
- **GPS-Standorte & Kartenansicht**:
  - Jeder Tag kann einer GPS-Position zugeordnet werden (`PUT /api/reports/{date}/location`).
  - Interaktive Leaflet-Karte mit Report-Bubbles, Schnellvorschau und Direktsprung zum Tagesbericht.
- **Öffentliche Share-Links**: Token-basierte Freigabelinks für einen oder mehrere Tage – ohne Login abrufbar!

---

## Installation & Schnellstart

### 1. Repository klonen & Virtual Environment mit `uv` anlegen
```bash
# Virtuelle Umgebung mit uv erstellen
uv venv

# Abhängigkeiten und Paket im Editable-Mode installieren
uv pip install -e ".[test]"
```

### 2. Server starten mit Uvicorn
```bash
uv run uvicorn memreport.main:app --host 0.0.0.0 --port 8000 --reload
```
Oder direkt über das installierte CLI-Kommando:
```bash
uv run memreport
```

Öffne anschließend [http://localhost:8000](http://localhost:8000) im Browser.

### Standard-Zugangsdaten:
- **Benutzername:** `admin`
- **Passwort:** `admin123`
*(Neue Benutzer können direkt auf der Login-Seite registriert werden).*

---

## REST API Referenz

### Authentifizierung (`/api/auth`)
- `POST /api/auth/login`: Anmelden (JSON oder Formular), gibt JWT-Token zurück und setzt Session-Cookie.
- `POST /api/auth/register`: Neuen Benutzer anlegen.
- `GET /api/auth/me`: Daten des angemeldeten Benutzers abrufen.
- `POST /api/auth/logout`: Abmelden (Session-Cookie löschen).

### Berichte (`/api/reports`)
- `GET /api/reports`: Liste aller Berichtstage mit Metadaten (Größe, GPS-Status, Zeitstempel).
- `GET /api/reports/{YYYY-MM-DD}`: Vollständigen Bericht eines Tages abrufen.
- `POST /api/reports/{YYYY-MM-DD}?overwrite=false`:
  - Neuen Bericht für das Datum erstellen oder an existierenden Bericht **anhängen**.
  - Mit `?overwrite=true` wird der bestehende Bericht ersetzt.
- `PUT /api/reports/{YYYY-MM-DD}`: Inhalt des Tagesberichts aktualisieren (z.B. durch Texteditor).
- `DELETE /api/reports/{YYYY-MM-DD}`: Bericht dieses Tages löschen.

### GPS-Standorte (`/api/reports/{date}/location`)
- `PUT /api/reports/{YYYY-MM-DD}/location`:
  ```json
  {
    "latitude": 52.5200,
    "longitude": 13.4050,
    "name": "Berlin Campus"
  }
  ```
- `DELETE /api/reports/{YYYY-MM-DD}/location`: GPS-Koordinaten entfernen.
- `GET /api/locations`: Alle Standorte des Nutzers für die Kartenansicht abrufen.

### Freigaben (`/api/shares`)
- `POST /api/shares`: Freigabelink für 1..n Tage erstellen:
  ```json
  {
    "dates": ["2026-09-15", "2026-09-16"],
    "title": "Wochenbericht KW 38",
    "expires_in_days": 7
  }
  ```
- `GET /api/shares`: Aktive Freigaben des Nutzers auflisten.
- `DELETE /api/shares/{id}`: Freigabelink widerrufen.
- `GET /api/public/shares/{token}`: **Öffentliche** Abfrage der Berichte über den Freigabe-Token (ohne Login!).

---

## Automatisierte Tests ausführen
```bash
uv run pytest
```