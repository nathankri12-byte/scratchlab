from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import zipfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from http.server import SimpleHTTPRequestHandler, HTTPServer


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DATA = ROOT / "data" / "courses"
DB_PATH = ROOT / "scratchlab.sqlite3"
ENV_PATH = ROOT / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip().lstrip("\ufeff"), value.strip().strip('"').strip("'"))
SESSION_COOKIE = "scratchlab_session"
PBKDF2_ITERATIONS = 210_000
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
SINGLE_LESSON_PRICE_EUR = 5
PREMIUM_MONTHLY_PRICE_EUR = 15
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_PREMIUM_PRICE_ID = os.environ.get("STRIPE_PREMIUM_PRICE_ID", "").strip()
STRIPE_LESSON_PRICE_ID = os.environ.get("STRIPE_LESSON_PRICE_ID", "").strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        result = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return result


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return base64.b64encode(digest).decode("ascii"), base64.b64encode(salt).decode("ascii")


def verify_password(password: str, encoded_hash: str, encoded_salt: str) -> bool:
    expected, _ = hash_password(password, base64.b64decode(encoded_salt))
    return hmac.compare_digest(expected, encoded_hash)


def calculate_level(xp: int) -> int:
    return max(1, xp // 100 + 1)


def load_courses() -> list[dict[str, Any]]:
    courses: list[dict[str, Any]] = []
    for file in sorted(DATA.glob("*.json")):
        courses.append(json.loads(file.read_text(encoding="utf-8")))
    return courses


def find_lesson(lesson_id: str) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
    for course in load_courses():
        for lesson in course.get("lessons", []):
            if lesson["id"] == lesson_id:
                return course, lesson
    return None, None


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                xp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1,
                premium_status TEXT NOT NULL DEFAULT 'free',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS progress (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                course_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL,
                xp_awarded INTEGER NOT NULL,
                completed_at TEXT NOT NULL,
                PRIMARY KEY (user_id, lesson_id)
            );

            CREATE TABLE IF NOT EXISTS badges (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                icon TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_badges (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                badge_id TEXT NOT NULL REFERENCES badges(id) ON DELETE CASCADE,
                awarded_at TEXT NOT NULL,
                PRIMARY KEY (user_id, badge_id)
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                scratch_url TEXT NOT NULL DEFAULT '',
                is_public INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ai_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                lesson_id TEXT,
                message TEXT NOT NULL,
                response TEXT NOT NULL,
                safety_label TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lesson_purchases (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                lesson_id TEXT NOT NULL,
                price_eur INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, lesson_id)
            );

            CREATE TABLE IF NOT EXISTS project_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                lesson_id TEXT,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                feedback TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                provider_reference TEXT NOT NULL,
                status TEXT NOT NULL,
                current_period_end TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        ensure_column(db, "users", "current_lesson_id", "TEXT")
        ensure_column(db, "users", "last_lesson_id", "TEXT")
        ensure_column(db, "projects", "sb3_summary", "TEXT NOT NULL DEFAULT ''")
        db.executemany(
            "INSERT OR IGNORE INTO badges (id, name, description, icon) VALUES (?, ?, ?, ?)",
            [
                ("first-step", "Erster Start", "Du hast deine erste Lektion geschafft.", "*"),
                ("motion-maker", "Bewegungs-Profi", "Du hast Bewegung in dein Projekt gebracht.", ">"),
                ("mini-maker", "Mini-Maker", "Du hast drei Lektionen abgeschlossen.", "#"),
                ("block-builder", "Block Builder", "Du hast fuenf Lektionen abgeschlossen.", "BB"),
                ("loop-pro", "Schleifen-Profi", "Du hast Schleifen gemeistert.", "LO"),
                ("variable-keeper", "Variablen-Kenner", "Du arbeitest sicher mit Variablen.", "VA"),
                ("debugger", "Debugger", "Du hast ein Projekt automatisch pruefen lassen.", "DG"),
                ("game-maker", "Game Maker", "Du hast ein Spiele-Thema abgeschlossen.", "GM"),
                ("scratch-master", "Scratch Master", "Du hast 50 Lektionen geschafft.", "SM"),
            ],
        )


def public_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "xp": row["xp"],
        "level": row["level"],
        "premiumStatus": row["premium_status"],
        "currentLessonId": row["current_lesson_id"] if "current_lesson_id" in row.keys() else None,
        "lastLessonId": row["last_lesson_id"] if "last_lesson_id" in row.keys() else None,
    }


def all_lessons() -> list[tuple[dict[str, Any], dict[str, Any]]]:
    ordered: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for course in sorted(load_courses(), key=lambda item: item.get("order", 999)):
        for lesson in course.get("lessons", []):
            ordered.append((course, lesson))
    return ordered


def next_lesson_after(completed_lesson_ids: set[str]) -> dict[str, Any] | None:
    for course, lesson in all_lessons():
        if lesson["id"] not in completed_lesson_ids and not lesson.get("premium"):
            return {"courseId": course["id"], **lesson}
    for course, lesson in all_lessons():
        if lesson["id"] not in completed_lesson_ids:
            return {"courseId": course["id"], **lesson}
    return None


def course_progress(completed_lesson_ids: set[str]) -> list[dict[str, Any]]:
    result = []
    for course in sorted(load_courses(), key=lambda item: item.get("order", 999)):
        lessons = course.get("lessons", [])
        completed = sum(1 for lesson in lessons if lesson["id"] in completed_lesson_ids)
        total = len(lessons)
        result.append(
            {
                "id": course["id"],
                "title": course["title"],
                "description": course["description"],
                "difficulty": course.get("difficulty", "Anfaenger"),
                "lessonCount": total,
                "completedCount": completed,
                "percent": round((completed / total) * 100) if total else 0,
                "isComplete": completed == total and total > 0,
            }
        )
    return result


def lesson_context(lesson_id: str | None) -> dict[str, Any] | None:
    if not lesson_id:
        return None
    _, lesson = find_lesson(lesson_id)
    return lesson


def build_assistant_prompt(message: str, lesson_id: str | None, learner_context: str = "") -> str:
    lesson = lesson_context(lesson_id)
    lesson_text = ""
    if lesson:
        lesson_text = (
            f"Aktuelle Lektion: {lesson['title']}\n"
            f"Erklaerung: {lesson['explanation']}\n"
            f"Demo: {lesson['demo']}\n"
            f"Aufgabe: {lesson['task']['prompt']}\n"
            f"Schritte: {' | '.join(lesson['task']['steps'])}\n"
        )
    return (
        "Du bist der ScratchLab KI-Lerncoach fuer absolute Scratch-Anfaenger. "
        "Antworte auf Deutsch, kurz, freundlich und konkret. "
        "Gib keine komplette fertige Loesung und keine langen Textwaende. "
        "Fuehre den Nutzer mit 1 bis 3 Hinweisen zum eigenen Denken. "
        "Wenn der Nutzer nach kompletter Loesung fragt, erklaere knapp, warum du nur Hinweise gibst. "
        "Nutze einfache Sprache, passend fuer Kinder, Jugendliche und Erwachsene.\n\n"
        f"Lernstand: {learner_context or 'Noch kein Lernstand uebergeben.'}\n"
        f"{lesson_text}\n"
        f"Frage des Nutzers: {message}"
    )


def call_gemini(message: str, lesson_id: str | None, history: list[sqlite3.Row], learner_context: str = "") -> tuple[str, str] | None:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    contents: list[dict[str, Any]] = []
    for item in history[-6:]:
        contents.append({"role": "user", "parts": [{"text": item["message"]}]})
        contents.append({"role": "model", "parts": [{"text": item["response"]}]})
    contents.append({"role": "user", "parts": [{"text": build_assistant_prompt(message, lesson_id, learner_context)}]})
    body = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 800,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(GEMINI_MODEL)}:generateContent"
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=35) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError):
        return None
    if not text:
        return None
    return text[:1400], "gemini_hint"


def assistant_reply(message: str, lesson_id: str | None, previous_count: int = 0) -> tuple[str, str]:
    lower = message.lower()
    label = "hint"
    prefix = ""
    if previous_count:
        prefix = "Naechster Hinweis: "
    if any(word in lower for word in ["loesung", "lösung", "fertig", "code geben", "komplett"]):
        return (
            prefix + "Ich gebe dir lieber keinen fertigen Komplettbau. Schau zuerst auf den Startblock: Wird dein Skript wirklich durch die gruene Flagge oder ein Ereignis gestartet?",
            "blocked_solution",
        )
    if "variable" in lower:
        hints = [
            "Bei Variablen hilft ein kurzer Check: Wird die Variable am Anfang gesetzt, danach veraendert und an der richtigen Stelle angezeigt?",
            "Schau auf den Block, der den Wert setzt. Wenn er nie ausgefuehrt wird, bleibt die Variable so, als haette Scratch sie nie geaendert.",
            "Teste mit einem Sprechblock: Lass die Figur kurz den aktuellen Variablenwert sagen. Dann siehst du, ob der Wert stimmt."
        ]
        return (prefix + hints[previous_count % len(hints)], label)
    if "beweg" in lower or "move" in lower:
        hints = [
            "Teste die Bewegung in kleinen Schritten: Starte mit 10 Schritten, beobachte die Richtung und veraendere dann nur eine Zahl.",
            "Wenn nichts passiert, pruefe zuerst: Ist der Bewegungsblock wirklich mit dem Startblock verbunden?",
            "Wenn die Figur in die falsche Richtung geht, schaue auf Richtung, Drehstil und die Zahl im Bewegungsblock."
        ]
        return (prefix + hints[previous_count % len(hints)], label)
    if "warum" in lower or "fehler" in lower:
        hints = [
            "Beschreibe den Moment, an dem es anders laeuft als erwartet. Danach pruefe den Block direkt davor, denn dort steckt oft der erste Hinweis.",
            "Vergleiche Erwartung und Ergebnis: Was sollte sichtbar passieren, und welcher Block ist direkt dafuer verantwortlich?",
            "Lass testweise einen Sprechblock zwischen zwei Bloecken auftauchen. So findest du, bis wohin dein Skript wirklich kommt."
        ]
        return (prefix + hints[previous_count % len(hints)], label)
    lesson_hint = " bei dieser Lektion" if lesson_id else ""
    general = [
        f"Guter Punkt. Versuch die Aufgabe{lesson_hint} in einen einzigen naechsten Mini-Schritt zu teilen: Welcher Block soll als erstes sichtbar etwas ausloesen?",
        "Mach einen Mini-Test statt alles auf einmal zu bauen: ein Startblock, ein sichtbarer Effekt, dann erst der naechste Block.",
        "Wenn du unsicher bist, lies die Aufgabe als kleine Szene: Wer soll wann was tun? Daraus ergeben sich meistens die passenden Bloecke."
    ]
    return (prefix + general[previous_count % len(general)], label)


def analyze_scratch_project(sb3_bytes: bytes) -> dict[str, Any]:
    if len(sb3_bytes) > 10 * 1024 * 1024:
        raise ValueError("Die Datei ist zu gross. Bitte lade eine kleinere .sb3-Datei hoch.")
    try:
        with zipfile.ZipFile(io.BytesIO(sb3_bytes)) as archive:
            with archive.open("project.json") as project_file:
                project = json.loads(project_file.read().decode("utf-8"))
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Die .sb3-Datei konnte nicht gelesen werden.")

    opcodes: set[str] = set()
    variables: set[str] = set()
    lists: set[str] = set()
    broadcasts: set[str] = set()
    target_count = 0

    for target in project.get("targets", []):
        target_count += 1
        for block in target.get("blocks", {}).values():
            if isinstance(block, dict) and block.get("opcode"):
                opcodes.add(block["opcode"])
                for field in block.get("fields", {}).values():
                    if isinstance(field, list) and field:
                        value = str(field[0])
                        if "message" in value.lower() or "broadcast" in value.lower():
                            broadcasts.add(value)
        for variable in target.get("variables", {}).values():
            if isinstance(variable, list) and variable:
                variables.add(str(variable[0]))
        for item in target.get("lists", {}).values():
            if isinstance(item, list) and item:
                lists.add(str(item[0]))
        for broadcast in target.get("broadcasts", {}).values():
            broadcasts.add(str(broadcast))

    return {
        "targetCount": target_count,
        "opcodes": sorted(opcodes),
        "variables": sorted(variables),
        "lists": sorted(lists),
        "broadcasts": sorted(broadcasts),
    }


def evaluate_project_for_lesson(analysis: dict[str, Any], lesson: dict[str, Any]) -> dict[str, Any]:
    task = lesson.get("task", {})
    required_opcodes = task.get("required_opcodes", [])
    details = []
    score = 0
    total = len(required_opcodes)
    opcodes = set(analysis.get("opcodes", []))
    for opcode in required_opcodes:
        if opcode in opcodes:
            score += 1
            details.append({"requirement": opcode, "passed": True, "message": f"{opcode} gefunden."})
        else:
            details.append({"requirement": opcode, "passed": False, "message": f"{opcode} fehlt noch."})

    feedback = f"{score} von {total} Anforderungen erfuellt."
    if total and score == total:
        feedback += " Stark, die wichtigsten Scratch-Bausteine sind vorhanden."
    elif score:
        feedback += " Du bist nah dran. Pruefe die fehlenden Bloecke."
    else:
        feedback += " Starte mit dem ersten geforderten Block aus der Aufgabe."
    return {"score": score, "total": total, "feedback": feedback, "details": details}


class ScratchLabServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class Handler(SimpleHTTPRequestHandler):
    server_version = "ScratchLab/0.1"

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        clean = parsed.path.lstrip("/") or "index.html"
        target = (FRONTEND / clean).resolve()
        if not str(target).startswith(str(FRONTEND.resolve())):
            return str(FRONTEND / "index.html")
        if target.is_dir():
            target = target / "index.html"
        return str(target)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        super().end_headers()

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self.route_api("GET")
            return
        super().do_GET()

    def do_POST(self) -> None:
        self.route_api("POST")

    def do_DELETE(self) -> None:
        self.route_api("DELETE")

    def route_api(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if method == "GET" and path == "/api/courses":
                self.json_response({"courses": load_courses()})
            elif method == "GET" and path == "/api/pricing":
                self.pricing()
            elif method == "GET" and path == "/api/me":
                self.require_user_response()
            elif method == "POST" and path == "/api/auth/register":
                self.register()
            elif method == "POST" and path == "/api/auth/login":
                self.login()
            elif method == "POST" and path == "/api/auth/logout":
                self.logout()
            elif method == "GET" and path == "/api/progress":
                self.progress()
            elif method == "POST" and path.startswith("/api/lessons/") and path.endswith("/complete"):
                lesson_id = path.split("/")[3]
                self.complete_lesson(lesson_id)
            elif method == "GET" and path == "/api/projects":
                self.projects()
            elif method == "POST" and path == "/api/projects":
                self.create_project()
            elif method == "POST" and path == "/api/projects/check":
                self.check_project()
            elif method == "DELETE" and path.startswith("/api/projects/"):
                self.delete_project(int(path.rsplit("/", 1)[1]))
            elif method == "POST" and path == "/api/assistant":
                self.assistant()
            elif method == "POST" and path == "/api/checkout/premium":
                self.checkout_premium()
            elif method == "POST" and path == "/api/checkout/lesson":
                self.checkout_lesson()
            else:
                self.json_response({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception:
            self.json_response({"error": "Server error"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 14_000_000:
            raise ValueError("Request too large")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def current_user(self) -> sqlite3.Row | None:
        cookie = SimpleCookie(self.headers.get("Cookie"))
        token = cookie.get(SESSION_COOKIE)
        if not token:
            return None
        with connect() as db:
            return db.execute(
                """
                SELECT users.* FROM users
                JOIN sessions ON sessions.user_id = users.id
                WHERE sessions.token = ?
                """,
                (token.value,),
            ).fetchone()

    def require_user(self) -> sqlite3.Row:
        user = self.current_user()
        if not user:
            raise PermissionError("Login required")
        return user

    def require_user_response(self) -> None:
        user = self.current_user()
        if not user:
            self.json_response({"user": None})
            return
        self.json_response({"user": public_user(user)})

    def register(self) -> None:
        payload = self.read_json()
        username = str(payload.get("username", "")).strip()[:28]
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        if len(username) < 3:
            raise ValueError("Der Benutzername braucht mindestens 3 Zeichen.")
        if not validate_email(email):
            raise ValueError("Bitte gib eine gueltige E-Mail-Adresse ein.")
        if len(password) < 8:
            raise ValueError("Das Passwort braucht mindestens 8 Zeichen.")
        password_hash, salt = hash_password(password)
        with connect() as db:
            try:
                cur = db.execute(
                    "INSERT INTO users (username, email, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?)",
                    (username, email, password_hash, salt, now_iso()),
                )
            except sqlite3.IntegrityError:
                raise ValueError("Benutzername oder E-Mail ist bereits vergeben.")
            user = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
        self.create_session(user)

    def login(self) -> None:
        payload = self.read_json()
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        with connect() as db:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not verify_password(password, user["password_hash"], user["salt"]):
            self.json_response({"error": "Login fehlgeschlagen."}, HTTPStatus.UNAUTHORIZED)
            return
        self.create_session(user)

    def create_session(self, user: sqlite3.Row) -> None:
        token = secrets.token_urlsafe(32)
        with connect() as db:
            db.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user["id"], now_iso()))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Set-Cookie", f"{SESSION_COOKIE}={token}; HttpOnly; SameSite=Lax; Path=/")
        self.end_headers()
        self.wfile.write(json.dumps({"user": public_user(user)}).encode("utf-8"))

    def logout(self) -> None:
        cookie = SimpleCookie(self.headers.get("Cookie"))
        token = cookie.get(SESSION_COOKIE)
        if token:
            with connect() as db:
                db.execute("DELETE FROM sessions WHERE token = ?", (token.value,))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; Max-Age=0; HttpOnly; SameSite=Lax; Path=/")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def progress(self) -> None:
        user = self.require_user_or_401()
        if not user:
            return
        with connect() as db:
            completed = [dict(row) for row in db.execute("SELECT * FROM progress WHERE user_id = ? ORDER BY completed_at DESC", (user["id"],))]
            badges = [dict(row) for row in db.execute(
                "SELECT badges.* FROM badges JOIN user_badges ON user_badges.badge_id = badges.id WHERE user_badges.user_id = ?",
                (user["id"],),
            )]
            projects = [dict(row) for row in db.execute("SELECT id, title, updated_at, is_public FROM projects WHERE user_id = ? ORDER BY updated_at DESC LIMIT 5", (user["id"],))]
        completed_ids = {item["lesson_id"] for item in completed}
        recommended = next_lesson_after(completed_ids)
        self.json_response(
            {
                "completed": completed,
                "badges": badges,
                "user": public_user(user),
                "courseProgress": course_progress(completed_ids),
                "nextLesson": recommended,
                "recentActivity": completed[:5],
                "projects": projects,
            }
        )

    def complete_lesson(self, lesson_id: str) -> None:
        user = self.require_user_or_401()
        if not user:
            return
        course, lesson = find_lesson(lesson_id)
        if not lesson:
            self.json_response({"error": "Lektion nicht gefunden."}, HTTPStatus.NOT_FOUND)
            return
        if lesson.get("premium") and not self.has_lesson_access(user["id"], lesson_id):
            self.json_response(
                {
                    "error": "Diese Lektion ist Premium. Du kannst sie einzeln fuer 5 EUR freischalten oder Premium fuer 15 EUR/Monat nutzen.",
                    "requiresPayment": True,
                },
                HTTPStatus.PAYMENT_REQUIRED,
            )
            return
        with connect() as db:
            exists = db.execute("SELECT 1 FROM progress WHERE user_id = ? AND lesson_id = ?", (user["id"], lesson_id)).fetchone()
            awarded = 0 if exists else int(lesson["xp"])
            if not exists:
                db.execute(
                    "INSERT INTO progress (user_id, course_id, lesson_id, xp_awarded, completed_at) VALUES (?, ?, ?, ?, ?)",
                    (user["id"], course["id"], lesson_id, awarded, now_iso()),
                )
                new_xp = user["xp"] + awarded
                completed_ids = {
                    row["lesson_id"]
                    for row in db.execute("SELECT lesson_id FROM progress WHERE user_id = ?", (user["id"],)).fetchall()
                }
                next_lesson = next_lesson_after(completed_ids)
                db.execute(
                    "UPDATE users SET xp = ?, level = ?, last_lesson_id = ?, current_lesson_id = ? WHERE id = ?",
                    (new_xp, calculate_level(new_xp), lesson_id, next_lesson["id"] if next_lesson else None, user["id"]),
                )
                self.award_badges(db, user["id"])
            updated = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        self.json_response({"awardedXp": awarded, "user": public_user(updated), "message": lesson["success_message"]})

    def has_lesson_access(self, user_id: int, lesson_id: str) -> bool:
        _, lesson = find_lesson(lesson_id)
        if not lesson or not lesson.get("premium"):
            return True
        with connect() as db:
            user = db.execute("SELECT premium_status FROM users WHERE id = ?", (user_id,)).fetchone()
            if user and user["premium_status"] == "premium":
                return True
            purchase = db.execute(
                "SELECT 1 FROM lesson_purchases WHERE user_id = ? AND lesson_id = ? AND status = 'paid'",
                (user_id, lesson_id),
            ).fetchone()
        return bool(purchase)

    def award_badges(self, db: sqlite3.Connection, user_id: int) -> None:
        count = db.execute("SELECT COUNT(*) AS c FROM progress WHERE user_id = ?", (user_id,)).fetchone()["c"]
        rules = []
        if count >= 1:
            rules.append("first-step")
        if db.execute("SELECT 1 FROM progress WHERE user_id = ? AND lesson_id = 'move-sprite'", (user_id,)).fetchone():
            rules.append("motion-maker")
        if count >= 3:
            rules.append("mini-maker")
        if count >= 5:
            rules.append("block-builder")
        if count >= 50:
            rules.append("scratch-master")
        if db.execute("SELECT 1 FROM progress WHERE user_id = ? AND lesson_id IN ('repeat-loop', 'forever-loop', 'repeat-until')", (user_id,)).fetchone():
            rules.append("loop-pro")
        if db.execute("SELECT 1 FROM progress WHERE user_id = ? AND lesson_id IN ('score-counter', 'timer', 'lives')", (user_id,)).fetchone():
            rules.append("variable-keeper")
        if db.execute("SELECT 1 FROM progress WHERE user_id = ? AND lesson_id IN ('catch-game', 'maze-game', 'dodge-game')", (user_id,)).fetchone():
            rules.append("game-maker")
        for badge_id in rules:
            db.execute(
                "INSERT OR IGNORE INTO user_badges (user_id, badge_id, awarded_at) VALUES (?, ?, ?)",
                (user_id, badge_id, now_iso()),
            )

    def projects(self) -> None:
        user = self.require_user_or_401()
        if not user:
            return
        with connect() as db:
            own = [dict(row) for row in db.execute("SELECT * FROM projects WHERE user_id = ? ORDER BY updated_at DESC", (user["id"],))]
            public = [dict(row) for row in db.execute(
                "SELECT projects.*, users.username FROM projects JOIN users ON users.id = projects.user_id WHERE is_public = 1 ORDER BY updated_at DESC LIMIT 20"
            )]
        self.json_response({"own": own, "public": public})

    def create_project(self) -> None:
        user = self.require_user_or_401()
        if not user:
            return
        payload = self.read_json()
        title = str(payload.get("title", "")).strip()[:80]
        if len(title) < 3:
            raise ValueError("Der Projekttitel braucht mindestens 3 Zeichen.")
        description = str(payload.get("description", "")).strip()[:600]
        scratch_url = str(payload.get("scratchUrl", "")).strip()[:300]
        is_public = 1 if payload.get("isPublic") else 0
        ts = now_iso()
        with connect() as db:
            cur = db.execute(
                """
                INSERT INTO projects (user_id, title, description, scratch_url, is_public, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user["id"], title, description, scratch_url, is_public, ts, ts),
            )
            project = dict(db.execute("SELECT * FROM projects WHERE id = ?", (cur.lastrowid,)).fetchone())
        self.json_response({"project": project})

    def delete_project(self, project_id: int) -> None:
        user = self.require_user_or_401()
        if not user:
            return
        with connect() as db:
            db.execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, user["id"]))
        self.json_response({"ok": True})

    def check_project(self) -> None:
        user = self.require_user_or_401()
        if not user:
            return
        payload = self.read_json()
        lesson_id = str(payload.get("lessonId", "")).strip() or None
        project_id = payload.get("projectId")
        encoded = str(payload.get("dataBase64", "")).strip()
        if not encoded:
            raise ValueError("Bitte lade eine .sb3-Datei hoch.")
        try:
            sb3_bytes = base64.b64decode(encoded, validate=True)
        except ValueError:
            raise ValueError("Die Datei konnte nicht gelesen werden.")
        analysis = analyze_scratch_project(sb3_bytes)
        _, lesson = find_lesson(lesson_id) if lesson_id else (None, None)
        result = evaluate_project_for_lesson(analysis, lesson) if lesson else {
            "score": 0,
            "total": 0,
            "feedback": "Projekt analysiert. Waehle eine Lektion aus, um konkrete Anforderungen zu pruefen.",
            "details": [],
        }
        with connect() as db:
            db.execute(
                """
                INSERT INTO project_checks (user_id, project_id, lesson_id, score, total, feedback, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    int(project_id) if project_id else None,
                    lesson_id,
                    result["score"],
                    result["total"],
                    result["feedback"],
                    json.dumps(result["details"], ensure_ascii=False),
                    now_iso(),
                ),
            )
            db.execute(
                "INSERT OR IGNORE INTO user_badges (user_id, badge_id, awarded_at) VALUES (?, 'debugger', ?)",
                (user["id"], now_iso()),
            )
        self.json_response({"analysis": analysis, "result": result})

    def checkout_premium(self) -> None:
        user = self.require_user_or_401()
        if not user:
            return
        if not STRIPE_SECRET_KEY or not STRIPE_PREMIUM_PRICE_ID:
            self.json_response(
                {
                    "error": "Stripe Checkout ist noch nicht vollstaendig konfiguriert.",
                    "checkoutReady": False,
                },
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        self.json_response(
            {
                "error": "Stripe Checkout ist vorbereitet, aber die echte Session-Erstellung wird erst nach vollstaendiger Stripe-Konfiguration aktiviert.",
                "checkoutReady": False,
            },
            HTTPStatus.SERVICE_UNAVAILABLE,
        )

    def checkout_lesson(self) -> None:
        user = self.require_user_or_401()
        if not user:
            return
        payload = self.read_json()
        lesson_id = str(payload.get("lessonId", "")).strip()
        _, lesson = find_lesson(lesson_id)
        if not lesson:
            self.json_response({"error": "Lektion nicht gefunden."}, HTTPStatus.NOT_FOUND)
            return
        if not lesson.get("premium"):
            self.json_response({"error": "Diese Lektion ist kostenlos."}, HTTPStatus.BAD_REQUEST)
            return
        if not STRIPE_SECRET_KEY or not STRIPE_LESSON_PRICE_ID:
            self.json_response(
                {
                    "error": "Stripe Checkout ist noch nicht vollstaendig konfiguriert.",
                    "checkoutReady": False,
                },
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        self.json_response(
            {
                "error": "Stripe Checkout ist vorbereitet, aber die echte Session-Erstellung wird erst nach vollstaendiger Stripe-Konfiguration aktiviert.",
                "checkoutReady": False,
            },
            HTTPStatus.SERVICE_UNAVAILABLE,
        )

    def assistant(self) -> None:
        user = self.current_user()
        payload = self.read_json()
        message = str(payload.get("message", "")).strip()[:1000]
        lesson_id = str(payload.get("lessonId", "")).strip() or None
        if len(message) < 2:
            raise ValueError("Schreib kurz, wobei du Hilfe brauchst.")
        with connect() as db:
            if user:
                history = db.execute(
                    "SELECT message, response FROM ai_interactions WHERE user_id = ? AND lesson_id = ? ORDER BY id DESC LIMIT 6",
                    (user["id"], lesson_id),
                ).fetchall()
                previous_count = len(history)
                completed_count = db.execute("SELECT COUNT(*) AS c FROM progress WHERE user_id = ?", (user["id"],)).fetchone()["c"]
                learner_context = f"Level {user['level']}, {user['xp']} XP, {completed_count} abgeschlossene Lektionen."
            else:
                history = db.execute(
                    "SELECT message, response FROM ai_interactions WHERE user_id IS NULL AND lesson_id = ? ORDER BY id DESC LIMIT 6",
                    (lesson_id,),
                ).fetchall()
                previous_count = len(history)
                learner_context = "Nicht eingeloggter Nutzer ohne gespeicherten Fortschritt."
            response, label = call_gemini(message, lesson_id, list(reversed(history)), learner_context) or assistant_reply(message, lesson_id, previous_count)
            db.execute(
                """
                INSERT INTO ai_interactions (user_id, lesson_id, message, response, safety_label, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user["id"] if user else None, lesson_id, message, response, label, now_iso()),
            )
        self.json_response({"response": response, "safetyLabel": label})

    def pricing(self) -> None:
        self.json_response(
            {
                "singleLessonPriceEur": SINGLE_LESSON_PRICE_EUR,
                "premiumMonthlyPriceEur": PREMIUM_MONTHLY_PRICE_EUR,
                "premiumIncludes": [
                    "Alle Scratch-Lektionen",
                    "Alle spaeteren Premium-Kurse",
                    "Mehr KI-Hilfe mit fairen Limits",
                    "Kosmetische Belohnungen",
                ],
                "checkoutReady": bool(STRIPE_SECRET_KEY and STRIPE_PREMIUM_PRICE_ID and STRIPE_LESSON_PRICE_ID),
                "stripeConfigured": bool(STRIPE_SECRET_KEY and STRIPE_PREMIUM_PRICE_ID and STRIPE_LESSON_PRICE_ID),
            }
        )

    def require_user_or_401(self) -> sqlite3.Row | None:
        try:
            return self.require_user()
        except PermissionError:
            self.json_response({"error": "Bitte melde dich an."}, HTTPStatus.UNAUTHORIZED)
            return None

    def json_response(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    init_db()
    port = int(os.environ.get("PORT", "8080"))
    server = ScratchLabServer(("0.0.0.0", port), Handler)
    print(f"ScratchLab laeuft auf http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
