# ScratchLab

ScratchLab ist eine moderne, dunkle und spielerische Lernplattform fuer Programmier-Einsteiger. Das MVP fokussiert Scratch, ist aber daten- und architekturseitig auf weitere Sprachen vorbereitet.

## MVP-Inhalt

- Landingpage mit schnellem Einstieg
- Registrierung, Login, Logout mit sicheren Passwort-Hashes
- Dashboard mit Fortschritt, XP, Level und Badges
- Datengetriebene Kurse und Lektionen
- Praktische Scratch-Aufgaben mit Erfolgserlebnis
- Fortschrittsspeicherung in SQLite
- Eigene Projekte anlegen und veroeffentlichen
- KI-Lernassistent mit optionaler Gemini-Anbindung und lernorientiertem Fallback
- Premium-Status, 5-EUR-Einzellektionen und 15-EUR-Monatspremium technisch vorbereitet
- Responsive Dark-Mode-UI
- Tests fuer Auth, Progression, Projekte und KI-Grenzen

## Starten

```powershell
& "C:\Users\MKRIP\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" backend/app.py
```

Mit echter Gemini-KI:

```powershell
$env:GEMINI_API_KEY="DEIN_KEY_HIER"
& "C:\Users\MKRIP\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" backend/app.py
```

Alternativ kann lokal eine `.env` angelegt werden:

```text
GEMINI_API_KEY=DEIN_KEY_HIER
GEMINI_MODEL=gemini-3.5-flash
```

Ohne Key nutzt ScratchLab automatisch den lokalen Hinweis-Fallback.

Danach im Browser oeffnen:

```text
http://localhost:8080
```

## Tests

```powershell
& "C:\Users\MKRIP\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests
```

## Dokumentation

- [Architektur](docs/architecture.md)
- [Datenmodell](docs/data-model.md)
- [Entwicklungsplan](docs/development-plan.md)
- [Technische Entscheidungen](docs/decisions.md)
