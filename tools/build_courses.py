from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COURSE_DIR = ROOT / "data" / "courses"


COURSES = [
    (
        "01-scratch-grundlagen",
        "Scratch Grundlagen",
        "Lerne die Buehne, Figuren und erste sichtbare Aktionen kennen.",
        "Anfaenger",
        [
            ("hello-sprite", "Deine Figur spricht", "Die Figur reagiert auf die gruene Flagge.", "event_whenflagclicked", "looks_sayforsecs", "Sage einen eigenen Begruessungssatz.", "Aendere Text und Dauer.", 40),
            ("move-sprite", "Bewegung mit Energie", "Eine Figur bewegt sich sichtbar auf der Buehne.", "event_whenflagclicked", "motion_movesteps", "Lass deine Figur laufen und danach sprechen.", "Teste drei verschiedene Schrittzahlen.", 55),
            ("first-animation", "Deine erste Animation", "Bewegung und Kostuemwechsel erzeugen Animation.", "control_repeat", "looks_nextcostume", "Baue eine kurze Laufanimation.", "Fuege eine Wartezeit ein.", 70),
            ("stage-background", "Buehne wechseln", "Hintergruende machen Szenen lebendig.", "event_whenflagclicked", "looks_switchbackdropto", "Wechsle beim Start den Hintergrund.", "Lass die Figur passend dazu sprechen.", 65),
            ("sound-start", "Sound beim Start", "Klang gibt Projekten direkt Feedback.", "event_whenflagclicked", "sound_play", "Spiele beim Start einen Sound ab.", "Kombiniere Sound mit Bewegung.", 65),
        ],
    ),
    (
        "02-bewegung-steuerung",
        "Bewegung und Steuerung",
        "Steuere Figuren mit Tastatur, Maus und Koordinaten.",
        "Anfaenger",
        [
            ("arrow-control", "Mit Pfeiltasten steuern", "Events koennen auf Tastendruck reagieren.", "event_whenkeypressed", "motion_changexby", "Bewege die Figur mit einer Pfeiltaste.", "Fuege eine zweite Richtung hinzu.", 75),
            ("coordinates", "X und Y verstehen", "Koordinaten bestimmen die Position auf der Buehne.", "motion_gotoxy", "motion_changeyby", "Setze die Figur an eine feste Position.", "Lass sie danach nach oben wandern.", 80),
            ("follow-mouse", "Der Maus folgen", "Figuren koennen sich an anderen Punkten orientieren.", "motion_pointtowards", "motion_movesteps", "Lass die Figur zur Maus laufen.", "Begrenze die Geschwindigkeit.", 85),
            ("edge-bounce", "Am Rand abprallen", "Rand-Erkennung verhindert, dass Figuren verschwinden.", "motion_ifonedgebounce", "motion_movesteps", "Lass die Figur abprallen.", "Aendere den Drehstil.", 85),
            ("smooth-glide", "Sanft gleiten", "Gleiten erzeugt ruhige Bewegungen.", "motion_glidesecstoxy", "event_whenflagclicked", "Lass die Figur sanft zu einem Punkt gleiten.", "Baue zwei Gleitpunkte nacheinander.", 90),
        ],
    ),
    (
        "03-bedingungen-logik",
        "Bedingungen und Logik",
        "Baue Entscheidungen: Wenn etwas passiert, reagiert dein Projekt.",
        "Fortgeschritten",
        [
            ("if-touching", "Wenn beruehrt", "Bedingungen pruefen, ob etwas wahr ist.", "control_if", "sensing_touchingobject", "Wenn zwei Figuren sich beruehren, soll eine sprechen.", "Fuege danach einen Sound hinzu.", 95),
            ("color-detect", "Farbe erkennen", "Scratch kann Farben auf der Buehne erkennen.", "sensing_touchingcolor", "control_if", "Reagiere, wenn deine Figur eine Farbe beruehrt.", "Mache daraus eine Ziellinie.", 100),
            ("if-else-choice", "Wenn oder sonst", "If-Else entscheidet zwischen zwei Wegen.", "control_if_else", "operator_gt", "Lass Scratch je nach Punktzahl anders reagieren.", "Aendere die Grenze.", 105),
            ("logic-and", "Und/Oder nutzen", "Logik verbindet mehrere Bedingungen.", "operator_and", "control_if", "Pruefe zwei Bedingungen gleichzeitig.", "Baue eine Oder-Regel.", 110),
            ("game-over-condition", "Game Over erkennen", "Spiele brauchen klare Endbedingungen.", "control_if", "control_stop", "Stoppe ein Spiel, wenn eine Bedingung erfuellt ist.", "Zeige vorher eine Game-Over-Nachricht.", 115),
        ],
    ),
    (
        "04-schleifen",
        "Schleifen",
        "Wiederhole Aktionen automatisch und baue lebendige Ablaufe.",
        "Fortgeschritten",
        [
            ("repeat-loop", "Wiederhole mal", "Eine feste Schleife wiederholt eine Aktion begrenzt.", "control_repeat", "motion_movesteps", "Lass eine Figur zehn Schritte mehrfach laufen.", "Aendere die Wiederholungszahl.", 90),
            ("forever-loop", "Endlos-Schleife", "Endlos-Schleifen halten Spiele am Laufen.", "control_forever", "motion_movesteps", "Lass die Figur dauerhaft laufen.", "Fuege Rand-Abprallen hinzu.", 100),
            ("wait-loop", "Tempo mit Wartezeit", "Warten macht Animationen kontrollierbar.", "control_wait", "control_repeat", "Baue eine langsame Blinkanimation.", "Mache sie schneller und langsamer.", 95),
            ("repeat-until", "Wiederholen bis", "Diese Schleife stoppt bei einer Bedingung.", "control_repeat_until", "sensing_touchingobject", "Lass eine Figur laufen, bis sie ein Ziel beruehrt.", "Fuege einen Erfolgssatz hinzu.", 115),
            ("loop-pattern", "Muster bauen", "Schleifen koennen Formen und Muster erzeugen.", "control_repeat", "motion_turnright", "Baue eine einfache Kreis- oder Quadratbewegung.", "Experimentiere mit Winkeln.", 120),
        ],
    ),
    (
        "05-variablen",
        "Variablen",
        "Speichere Punkte, Leben, Zeit und Spielwerte.",
        "Fortgeschritten",
        [
            ("score-counter", "Punkte zaehlen", "Eine Variable speichert den aktuellen Punktestand.", "data_changevariableby", "event_whenthisspriteclicked", "Erhoehe Punkte beim Klick auf eine Figur.", "Setze Punkte beim Start auf 0.", 85),
            ("timer", "Timer bauen", "Zeitdruck macht Spiele spannender.", "data_changevariableby", "control_wait", "Zaehle eine Zeitvariable herunter.", "Stoppe bei 0.", 115),
            ("lives", "Leben verwenden", "Leben zeigen, wie viele Versuche bleiben.", "data_setvariableto", "data_changevariableby", "Ziehe ein Leben ab, wenn etwas beruehrt wird.", "Baue Game Over bei 0 Leben.", 120),
            ("high-score-idea", "Highscore-Idee", "Ein hoher Wert kann als Rekord gespeichert werden.", "operator_gt", "data_setvariableto", "Aktualisiere Rekord, wenn Punkte groesser sind.", "Lass die Figur den Rekord sagen.", 125),
            ("variable-debug", "Variablen debuggen", "Sichtbare Variablen helfen beim Fehlersuchen.", "data_showvariable", "looks_sayforsecs", "Zeige eine Variable und pruefe ihren Wert.", "Verstecke sie erst am Ende.", 95),
        ],
    ),
    (
        "06-nachrichten-events",
        "Nachrichten und Events",
        "Lass Figuren miteinander kommunizieren.",
        "Fortgeschritten",
        [
            ("broadcast-start", "Nachricht senden", "Broadcasts starten Aktionen bei anderen Figuren.", "event_broadcast", "event_whenbroadcastreceived", "Sende eine Nachricht und lasse eine zweite Figur reagieren.", "Fuege einen Sound zur Reaktion hinzu.", 120),
            ("scene-change", "Szenenwechsel", "Nachrichten koennen neue Szenen starten.", "event_broadcast", "looks_switchbackdropto", "Wechsle per Nachricht den Hintergrund.", "Lass alle Figuren neu positionieren.", 125),
            ("dialogue", "Dialog zwischen Figuren", "Mit Nachrichten entsteht ein Gespraech.", "event_whenbroadcastreceived", "looks_sayforsecs", "Baue einen kurzen Dialog mit zwei Figuren.", "Fuege eine dritte Antwort hinzu.", 130),
            ("level-start", "Level starten", "Events ordnen groessere Spiele.", "event_broadcast", "data_setvariableto", "Starte ein Level per Nachricht.", "Setze Punkte und Zeit beim Levelstart.", 135),
            ("custom-event-chain", "Ereigniskette", "Mehrere Nachrichten koennen eine Kette bilden.", "event_broadcastandwait", "event_whenbroadcastreceived", "Baue drei Aktionen nacheinander.", "Nutze broadcast and wait.", 140),
        ],
    ),
    (
        "07-klone",
        "Klone",
        "Erzeuge viele gleiche Objekte, ohne alles mehrfach zu bauen.",
        "Profi",
        [
            ("clone-basics", "Erster Klon", "Klone kopieren eine Figur zur Laufzeit.", "control_create_clone_of", "control_start_as_clone", "Erzeuge beim Start einen Klon.", "Lass Original und Klon anders aussehen.", 140),
            ("falling-clones", "Fallende Objekte", "Klone eignen sich fuer Sammelobjekte.", "motion_gotoxy", "control_create_clone_of", "Lass mehrere Objekte von oben fallen.", "Nutze zufaellige X-Positionen.", 150),
            ("delete-clones", "Klone loeschen", "Geloeschte Klone halten das Projekt schnell.", "control_delete_this_clone", "sensing_touchingobject", "Loesche einen Klon, wenn er den Rand erreicht.", "Loesche ihn auch beim Einsammeln.", 145),
            ("clone-randomness", "Zufall mit Klonen", "Zufall macht Spiele weniger vorhersehbar.", "operator_random", "motion_gotoxy", "Erzeuge Klone an zufaelligen Orten.", "Aendere Groesse oder Kostuem zufaellig.", 155),
            ("enemy-wave", "Gegnerwelle", "Viele Klone koennen eine Herausforderung bilden.", "control_forever", "control_create_clone_of", "Baue eine einfache Gegnerwelle.", "Erhoehe mit Zeit die Geschwindigkeit.", 165),
        ],
    ),
    (
        "08-listen",
        "Listen",
        "Speichere mehrere Werte und baue Inventar- oder Quizideen.",
        "Profi",
        [
            ("list-basics", "Erste Liste", "Listen speichern mehrere Eintraege.", "data_addtolist", "data_showlist", "Fuege drei Woerter zu einer Liste hinzu.", "Lass die Figur ein zufaelliges Wort sagen.", 145),
            ("quiz-list", "Quizfragen sammeln", "Listen koennen Fragen und Antworten organisieren.", "data_itemoflist", "sensing_askandwait", "Stelle eine Frage aus einer Liste.", "Pruefe die Antwort mit einer Bedingung.", 160),
            ("inventory", "Inventar bauen", "Ein Inventar merkt sich gesammelte Dinge.", "data_addtolist", "sensing_touchingobject", "Fuege ein Item hinzu, wenn es eingesammelt wird.", "Verhindere doppelte Eintraege.", 165),
            ("remove-item", "Eintrag entfernen", "Listen lassen sich veraendern.", "data_deleteoflist", "data_itemnumoflist", "Entferne ein Item, wenn es benutzt wird.", "Zeige vorher eine Meldung.", 170),
            ("list-debug", "Listen pruefen", "Listen sichtbar zu machen hilft beim Testen.", "data_showlist", "looks_sayforsecs", "Zeige eine Liste waehrend des Tests.", "Verstecke sie im fertigen Spiel.", 150),
        ],
    ),
    (
        "09-spiele-programmieren",
        "Spiele programmieren",
        "Kombiniere alles zu echten Mini-Spielen.",
        "Profi",
        [
            ("catch-game", "Fangspiel", "Ein Ziel, Punkte und Bewegung ergeben ein Spiel.", "sensing_touchingobject", "data_changevariableby", "Baue ein Spiel, in dem man Objekte faengt.", "Fuege Zeitlimit hinzu.", 180),
            ("maze-game", "Labyrinth", "Farb- und Randregeln erzeugen Level.", "sensing_touchingcolor", "motion_gotoxy", "Baue ein kleines Labyrinth.", "Setze die Figur bei Wandkontakt zurueck.", 185),
            ("clicker-game", "Clicker-Spiel", "Klicks, Punkte und Upgrades motivieren.", "event_whenthisspriteclicked", "data_changevariableby", "Baue ein Klickspiel mit Punkten.", "Fuege ein Upgrade mit Bedingung hinzu.", 175),
            ("dodge-game", "Ausweichspiel", "Bewegung und Klone erzeugen Spannung.", "control_create_clone_of", "sensing_touchingobject", "Baue ein Spiel, in dem man Hindernissen ausweicht.", "Mache es jede Runde schneller.", 195),
            ("platform-idea", "Platformer-Idee", "Sprung, Schwerkraft und Kollision bilden Plattformspiele.", "motion_changeyby", "operator_lt", "Baue eine einfache Sprungbewegung.", "Stoppe die Figur auf einer Plattform.", 210),
        ],
    ),
    (
        "10-eigene-projekte",
        "Eigene Projekte",
        "Plane, baue, teste und verbessere dein eigenes Scratch-Projekt.",
        "Profi",
        [
            ("project-plan", "Projekt planen", "Eine klare Idee macht das Bauen leichter.", "looks_sayforsecs", "event_whenflagclicked", "Schreibe Ziel, Figuren und Regeln deines Projekts auf.", "Baue eine Startszene.", 120),
            ("prototype", "Prototyp bauen", "Ein Prototyp testet nur die wichtigste Idee.", "event_whenflagclicked", "control_forever", "Baue die Kernmechanik deines Projekts.", "Lass Optik erstmal einfach.", 180),
            ("playtest", "Playtest machen", "Testen zeigt, was noch unklar ist.", "looks_sayforsecs", "data_showvariable", "Teste dein Projekt und notiere drei Verbesserungen.", "Frage eine andere Person nach Feedback.", 150),
            ("polish", "Projekt polieren", "Kleine Details machen Projekte hochwertig.", "sound_play", "looks_nextcostume", "Fuege Sound, Animation oder bessere Texte hinzu.", "Entferne sichtbare Debug-Variablen.", 170),
            ("publish-project", "Projekt vorstellen", "Eine gute Beschreibung hilft anderen.", "event_whenflagclicked", "looks_sayforsecs", "Gib deinem Projekt einen Titel und eine Beschreibung.", "Speichere es in ScratchLab als eigenes Projekt.", 160),
        ],
    ),
]


def lesson(course_id: str, index: int, item: tuple[str, str, str, str, str, str, str, int], premium: bool) -> dict:
    lesson_id, title, goal, required_one, required_two, task, challenge, xp = item
    return {
        "id": lesson_id,
        "title": title,
        "summary": goal,
        "learning_goal": goal,
        "explanation": f"In dieser Lektion lernst du: {goal} Du baust sofort etwas Sichtbares in Scratch und testest danach, ob es funktioniert.",
        "example": f"Beispiel: Kombiniere einen passenden Startblock mit {required_two}, teste dein Projekt und veraendere danach eine Zahl oder einen Text.",
        "demo": f"Nutze {required_one} zusammen mit {required_two}.",
        "xp": xp,
        "premium": premium,
        "price_eur": 5 if premium else 0,
        "task": {
            "kind": "scratch-build",
            "prompt": task,
            "steps": [
                "Oeffne dein Scratch-Projekt.",
                f"Fuege einen Block vom Typ {required_one} hinzu.",
                f"Kombiniere ihn mit {required_two}.",
                "Starte das Projekt und beobachte, was sichtbar passiert.",
            ],
            "checks": [
                "Das Ergebnis ist auf der Buehne sichtbar.",
                "Du kannst erklaeren, welcher Block den Effekt ausloest.",
            ],
            "required_opcodes": [required_one, required_two],
        },
        "challenge": challenge,
        "hints": [
            "Teste immer nur eine kleine Aenderung auf einmal.",
            "Wenn nichts passiert, pruefe zuerst den Startblock.",
            "Nutze sichtbare Variablen oder Sprechblasen, um Fehler zu finden.",
        ],
        "success_condition": "Die geforderten Bloecke sind vorhanden und das Projekt zeigt den beschriebenen Effekt.",
        "success_message": f"Lektion abgeschlossen: {title}. Genau so waechst dein Scratch-Werkzeugkasten.",
    }


def main() -> None:
    COURSE_DIR.mkdir(parents=True, exist_ok=True)
    for old_file in COURSE_DIR.glob("*.json"):
        old_file.unlink()
    for course_index, (course_id, title, description, difficulty, lessons) in enumerate(COURSES, start=1):
        course = {
            "id": course_id,
            "language": "scratch",
            "title": title,
            "description": description,
            "difficulty": difficulty,
            "free": course_index <= 1,
            "order": course_index,
            "lessons": [
                lesson(course_id, i, item, premium=(course_index > 1 or i > 3))
                for i, item in enumerate(lessons, start=1)
            ],
        }
        (COURSE_DIR / f"{course_id}.json").write_text(
            json.dumps(course, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
