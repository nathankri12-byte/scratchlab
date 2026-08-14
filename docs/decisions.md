# Technische Entscheidungen

## ADR-001: Datengetriebene Lerninhalte

Kurse und Lektionen werden als JSON abgelegt. Dadurch kann ScratchLab neue Inhalte erhalten, ohne UI- oder Backend-Code anzupassen.

## ADR-002: SQLite im MVP

SQLite senkt Komplexitaet und laufende Kosten in der lokalen Entwicklungsphase. Die SQL-Struktur bleibt relational und kann spaeter nach PostgreSQL migriert werden.

## ADR-003: Lernassistent gibt Hinweise, keine Komplettloesungen

Die KI-Hilfe nutzt optional Gemini ueber `GEMINI_API_KEY`. Ohne Key faellt sie auf lokale Hinweise zurueck. In beiden Faellen bleibt die Produktregel gleich: kurze Lernhinweise statt kompletter Copy-Paste-Loesungen.

## ADR-004: Premium vorbereitet, aber nicht verkaufsdominant

Die ersten Scratch-Grundlagen bleiben kostenlos. Danach werden Premium-Lektionen sichtbar, aber gesperrt: 5 EUR pro einzelne Lektion oder 15 EUR/Monat fuer alle Lektionen. Der echte Checkout wird spaeter angebunden.

## ADR-005: Kein Schulplattform-Look

Die UI ist dunkel, klar und spielerisch. Fortschritt, Aufgabe und naechster Schritt sind jederzeit sichtbar.
