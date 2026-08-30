# ScratchLab

ScratchLab ist eine moderne, dunkle und spielerische Lernplattform fuer Programmier-Einsteiger. Das MVP fokussiert Scratch, ist aber daten- und architekturseitig auf weitere Sprachen vorbereitet.

## MVP-Inhalt

- Landingpage mit schnellem Einstieg
- Registrierung, Login, Logout mit sicheren Passwort-Hashes
- Dashboard mit Fortschritt, XP, Level und Badges
- 10 datengetriebene Kurse mit 50 Scratch-Lektionen
- Praktische Scratch-Aufgaben mit Erfolgserlebnis
- Fortschrittsspeicherung in SQLite
- Eigene Projekte anlegen und veroeffentlichen
- KI-Lernassistent mit optionaler Gemini-Anbindung und lernorientiertem Fallback
- `.sb3`-Projektpruefung ohne Scratch-Login
- Premium-Status, 5-EUR-Einzellektionen und 15-EUR-Monatspremium technisch vorbereitet
- Responsive Dark-Mode-UI
- Tests fuer Auth, Progression, Projekte und KI-Grenzen

## Projektstruktur

- `backend/`: Python-Backend, API, Auth, SQLite, Gemini, Projektpruefung
- `frontend/`: HTML/CSS/JavaScript fuer die responsive SPA
- `data/courses/`: JSON-Kurse und Lektionen
- `tools/build_courses.py`: Generator fuer die Kursdaten
- `tests/`: Unit-Tests fuer Kernlogik
- `docs/`: Architektur- und Produktentscheidungen

## Lokal starten

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

## Render Deployment

Render startet die App ueber das GitHub-Repo. Wichtig ist, dass Secrets nur in Render als Environment Variables gesetzt werden:

- `GEMINI_API_KEY`
- optional `GEMINI_MODEL`
- spaeter fuer Stripe: `STRIPE_SECRET_KEY`, `STRIPE_PREMIUM_PRICE_ID`, `STRIPE_LESSON_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`

Keine `.env`, keine echten API-Keys und keine Zahlungsdaten duerfen committed werden.

## Stripe Vorbereitung

ScratchLab speichert keine Karten-, Bank- oder PIN-Daten. Zahlungen sollen spaeter ausschliesslich ueber Stripe Checkout laufen. Solange Stripe nicht vollstaendig konfiguriert ist, geben die Checkout-Endpunkte eine sichere Meldung zurueck und aktivieren keine Zahlung.

## Scratch-Projektpruefung

ScratchLab speichert keine Scratch-Passwoerter. Die sichere Pruefung erfolgt ueber Upload einer `.sb3`-Datei. `.sb3` ist ein ZIP mit `project.json`; daraus werden Block-OpCodes, Variablen, Listen und Broadcasts gelesen und mit den Anforderungen der Lektion verglichen.

## Dokumentation

- [Architektur](docs/architecture.md)
- [Datenmodell](docs/data-model.md)
- [Entwicklungsplan](docs/development-plan.md)
- [Technische Entscheidungen](docs/decisions.md)
- [Scratch-Projektpruefung](docs/scratch-project-checking.md)
