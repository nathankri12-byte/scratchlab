# Architektur

## Zielbild

ScratchLab wird als modularer Produktkern gebaut: Lerninhalte, Fortschritt, Gamification, Projekte, Premium und KI-Hilfe sind getrennte Domänen. Scratch ist die erste Sprache, aber Kurse und Aufgaben tragen ein `language`-Feld, damit spaeter Python, JavaScript oder weitere Sprachen ohne grundlegenden Umbau ergaenzt werden koennen.

## MVP-Stack

- Frontend: Vanilla HTML, CSS und JavaScript als schlanke responsive SPA
- Backend: Python-HTTP-Server mit klaren JSON-APIs
- Datenbank: SQLite fuer lokale Entwicklung und niedrige Kosten im MVP
- Auth: E-Mail/Login mit PBKDF2-Passwort-Hash, HttpOnly-Session-Cookie
- Inhalte: JSON-Dateien in `data/courses`
- Tests: Python `unittest`

## Spaeteres Produktionsziel

Fuer einen echten oeffentlichen Launch sollte die gleiche Domaenenstruktur auf einen Cloud-Stack migriert werden, zum Beispiel:

- Next.js oder Remix fuer UI und Server-Routing
- PostgreSQL fuer relationale Daten
- Object Storage fuer Projektdateien und Medien
- Stripe oder Paddle fuer Abos
- Moderationsqueue fuer veroeffentlichte Projekte
- Separater KI-Service mit Limits, Logging und Safety-Policies

## Domänen

- `Auth`: Nutzer, Sessions, Passwortsicherheit
- `Learning`: Kurse, Lektionen, Aufgaben
- `Progress`: abgeschlossene Lektionen, aktueller Kurs, XP, Level
- `Rewards`: Badges, freigeschaltete Kosmetik
- `Projects`: eigene und veroeffentlichte Scratch-Projekte
- `Premium`: Subscription-Status und Zugriffskontrolle
- `Assistant`: Lernhilfe mit Hinweisen statt Komplettloesungen

## Sicherheit

Das MVP setzt bereits Grundprinzipien um: serverseitige Validierung, parametrische SQL-Queries, sichere Passwort-Hashes, HttpOnly-Cookies, einfache Rate-Limit-Struktur, keine Secrets im Frontend und zurueckhaltende Datenerfassung. Vor Launch muessen Datenschutz, Minderjaehrigenschutz, Moderation und rechtliche Texte professionell geprueft werden.
