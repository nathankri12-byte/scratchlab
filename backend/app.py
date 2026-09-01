from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
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

SESSION_COOKIE = "scratchlab_session"
PBKDF2_ITERATIONS = 210_000
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
SINGLE_LESSON_PRICE_EUR = 5
PREMIUM_MONTHLY_PRICE_EUR = 15

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_PREMIUM_PRICE_ID = os.environ.get("STRIPE_PREMIUM_PRICE_ID", "").strip()
STRIPE_LESSON_PRICE_ID = os.environ.get("STRIPE_LESSON_PRICE_ID", "").strip()


def load_local_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(
            key.strip().lstrip("\ufeff"),
            value.strip().strip('"').strip("'"),
        )


load_local_env()

# Re-read after local .env loading.
SUPABASE_URL = os.environ.get("SUPABASE_URL", SUPABASE_URL).strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get(
    "SUPABASE_SERVICE_ROLE_KEY", SUPABASE_SERVICE_ROLE_KEY
).strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY).strip()
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", STRIPE_SECRET_KEY).strip()
STRIPE_PREMIUM_PRICE_ID = os.environ.get(
    "STRIPE_PREMIUM_PRICE_ID", STRIPE_PREMIUM_PRICE_ID
).strip()
STRIPE_LESSON_PRICE_ID = os.environ.get(
    "STRIPE_LESSON_PRICE_ID", STRIPE_LESSON_PRICE_ID
).strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return (
        base64.b64encode(digest).decode("ascii"),
        base64.b64encode(salt).decode("ascii"),
    )


def verify_password(password: str, encoded_hash: str, encoded_salt: str) -> bool:
    expected, _ = hash_password(password, base64.b64decode(encoded_salt))
    return hmac.compare_digest(expected, encoded_hash)


def calculate_level(xp: int) -> int:
    return max(1, xp // 100 + 1)


def load_courses() -> list[dict[str, Any]]:
    courses: list[dict[str, Any]] = []
    for file in sorted(DATA.glob("*.json")):
        courses.append(json.loads(file.read_text(encoding="utf-8")))
    return sorted(courses, key=lambda item: item.get("order", 999))


def all_lessons() -> list[tuple[dict[str, Any], dict[str, Any]]]:
    result = []
    for course in load_courses():
        for lesson in course.get("lessons", []):
            result.append((course, lesson))
    return result


def find_lesson(lesson_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for course, lesson in all_lessons():
        if str(lesson.get("id")) == str(lesson_id):
            return course, lesson
    return None, None


def is_admin_user(user: dict[str, Any] | None) -> bool:
    if not user or not ADMIN_EMAIL:
        return False
    return str(user.get("email", "")).strip().lower() == ADMIN_EMAIL


def public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "username": row.get("username"),
        "email": row.get("email"),
        "xp": int(row.get("xp") or 0),
        "level": int(row.get("level") or 1),
        "premiumStatus": row.get("premium_status") or "free",
        "currentLessonId": row.get("current_lesson_id"),
        "lastLessonId": row.get("last_lesson_id"),
        "isAdmin": is_admin_user(row),
    }


class SupabaseError(RuntimeError):
    pass


def require_supabase() -> None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise SupabaseError(
            "Supabase ist auf dem Server noch nicht konfiguriert. "
            "Setze SUPABASE_URL und SUPABASE_SERVICE_ROLE_KEY in Render."
        )


def supabase_request(
    method: str,
    table: str,
    *,
    query: str = "",
    payload: Any = None,
    headers: dict[str, str] | None = None,
) -> Any:
    require_supabase()
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if query:
        url += f"?{query}"

    request_headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if headers:
        request_headers.update(headers)

    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            pass
        raise SupabaseError(
            f"Supabase {exc.code}: {detail or exc.reason}"
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise SupabaseError("Supabase ist gerade nicht erreichbar.") from exc
    except json.JSONDecodeError as exc:
        raise SupabaseError("Supabase hat eine ungültige Antwort gesendet.") from exc


def sb_select(
    table: str,
    *,
    select: str = "*",
    filters: list[tuple[str, str]] | None = None,
    limit: int | None = None,
    order: str | None = None,
) -> list[dict[str, Any]]:
    parts = [f"select={quote(select)}"]
    for key, value in filters or []:
        parts.append(f"{quote(key)}={quote(value)}")
    if order:
        parts.append(f"order={quote(order)}")
    if limit is not None:
        parts.append(f"limit={int(limit)}")
    data = supabase_request("GET", table, query="&".join(parts))
    return data or []


def sb_insert(
    table: str,
    payload: dict[str, Any],
    *,
    returning: bool = True,
) -> list[dict[str, Any]]:
    headers = {"Prefer": "return=representation" if returning else "return=minimal"}
    data = supabase_request("POST", table, payload=payload, headers=headers)
    return data or []


def sb_update(
    table: str,
    payload: dict[str, Any],
    *,
    filters: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    parts = []
    for key, value in filters:
        parts.append(f"{quote(key)}={quote(value)}")
    data = supabase_request(
        "PATCH",
        table,
        query="&".join(parts),
        payload=payload,
        headers={"Prefer": "return=representation"},
    )
    return data or []


def sb_delete(
    table: str,
    *,
    filters: list[tuple[str, str]],
) -> None:
    parts = []
    for key, value in filters:
        parts.append(f"{quote(key)}={quote(value)}")
    supabase_request("DELETE", table, query="&".join(parts), headers={"Prefer": "return=minimal"})


def find_user_by_email(email: str) -> dict[str, Any] | None:
    rows = sb_select(
        "users",
        filters=[("email", f"eq.{email}")],
        limit=1,
    )
    return rows[0] if rows else None


def find_user_by_id(user_id: str | int) -> dict[str, Any] | None:
    rows = sb_select(
        "users",
        filters=[("id", f"eq.{user_id}")],
        limit=1,
    )
    return rows[0] if rows else None


def create_session(user: dict[str, Any]) -> str:
    token = secrets.token_urlsafe(40)
    sb_insert(
        "sessions",
        {
            "token": token,
            "user_id": user["id"],
            "created_at": now_iso(),
        },
        returning=False,
    )
    return token


def current_user_from_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    rows = sb_select(
        "sessions",
        select="user_id",
        filters=[("token", f"eq.{token}")],
        limit=1,
    )
    if not rows:
        return None
    return find_user_by_id(rows[0]["user_id"])


def next_lesson_after(completed_ids: set[str]) -> dict[str, Any] | None:
    for course, lesson in all_lessons():
        if lesson["id"] not in completed_ids and not lesson.get("premium"):
            return {"courseId": course["id"], **lesson}
    for course, lesson in all_lessons():
        if lesson["id"] not in completed_ids:
            return {"courseId": course["id"], **lesson}
    return None


def course_progress(completed_ids: set[str]) -> list[dict[str, Any]]:
    output = []
    for course in load_courses():
        lessons = course.get("lessons", [])
        completed = sum(1 for lesson in lessons if lesson["id"] in completed_ids)
        total = len(lessons)
        output.append(
            {
                "id": course["id"],
                "title": course["title"],
                "description": course.get("description", ""),
                "difficulty": course.get("difficulty", "Anfänger"),
                "lessonCount": total,
                "completedCount": completed,
                "percent": round(completed / total * 100) if total else 0,
                "isComplete": total > 0 and completed == total,
            }
        )
    return output


def analyze_scratch_project(sb3_bytes: bytes) -> dict[str, Any]:
    if len(sb3_bytes) > 10 * 1024 * 1024:
        raise ValueError("Die .sb3-Datei darf maximal 10 MB groß sein.")

    try:
        with zipfile.ZipFile(io.BytesIO(sb3_bytes)) as archive:
            names = set(archive.namelist())
            if "project.json" not in names:
                raise ValueError("In der .sb3-Datei wurde keine project.json gefunden.")
            with archive.open("project.json") as project_file:
                project = json.loads(project_file.read().decode("utf-8"))
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Die .sb3-Datei konnte nicht gelesen werden.") from exc

    if not isinstance(project, dict) or not isinstance(project.get("targets"), list):
        raise ValueError("Die Scratch-Projektstruktur ist ungültig.")

    opcodes: set[str] = set()
    variables: set[str] = set()
    lists: set[str] = set()
    broadcasts: set[str] = set()
    target_count = 0

    for target in project["targets"]:
        if not isinstance(target, dict):
            continue
        target_count += 1

        for block in (target.get("blocks") or {}).values():
            if not isinstance(block, dict):
                continue
            opcode = block.get("opcode")
            if opcode:
                opcodes.add(str(opcode))

            for field in (block.get("fields") or {}).values():
                if isinstance(field, list) and field:
                    value = str(field[0])
                    lowered = value.lower()
                    if "broadcast" in lowered or "nachricht" in lowered:
                        broadcasts.add(value)

        for variable in (target.get("variables") or {}).values():
            if isinstance(variable, list) and variable:
                variables.add(str(variable[0]))

        for item in (target.get("lists") or {}).values():
            if isinstance(item, list) and item:
                lists.add(str(item[0]))

        for broadcast in (target.get("broadcasts") or {}).values():
            broadcasts.add(str(broadcast))

    return {
        "targetCount": target_count,
        "opcodes": sorted(opcodes),
        "variables": sorted(variables),
        "lists": sorted(lists),
        "broadcasts": sorted(broadcasts),
    }


def evaluate_project_for_lesson(
    analysis: dict[str, Any],
    lesson: dict[str, Any] | None,
) -> dict[str, Any]:
    task = (lesson or {}).get("task") or {}

    requirements: list[tuple[str, list[str], set[str], str]] = [
        (
            "Blöcke",
            task.get("required_opcodes") or [],
            set(analysis.get("opcodes") or []),
            "Block",
        ),
        (
            "Variablen",
            task.get("required_variables") or [],
            set(analysis.get("variables") or []),
            "Variable",
        ),
        (
            "Listen",
            task.get("required_lists") or [],
            set(analysis.get("lists") or []),
            "Liste",
        ),
        (
            "Nachrichten",
            task.get("required_broadcasts") or [],
            set(analysis.get("broadcasts") or []),
            "Nachricht",
        ),
    ]

    details = []
    for category, required, actual, label in requirements:
        for item in sorted(set(map(str, required))):
            passed = item in actual
            details.append(
                {
                    "requirement": f"{category}: {item}",
                    "passed": passed,
                    "message": (
                        f"{label} '{item}' gefunden."
                        if passed
                        else f"{label} '{item}' fehlt noch."
                    ),
                }
            )

    if not details:
        details.append(
            {
                "requirement": "Anforderungen",
                "passed": False,
                "message": (
                    "Für diese Lektion sind noch keine prüfbaren "
                    "Scratch-Anforderungen hinterlegt."
                ),
            }
        )

    score = sum(1 for item in details if item["passed"])
    total = len(details)
    passed = total > 0 and score == total

    if passed:
        feedback = (
            "Projekt geprüft: Die geforderten Scratch-Bausteine sind vorhanden. "
            "Du kannst die Lektion jetzt abschließen."
        )
    elif score:
        feedback = (
            f"Schon {score} von {total} Anforderungen gefunden. "
            "Achte noch einmal auf die fehlenden Bausteine."
        )
    else:
        feedback = (
            "Die Datei wurde gelesen. Achte noch einmal auf die Anforderungen "
            "der Lektion und prüfe dein Projekt erneut."
        )

    return {
        "score": score,
        "total": total,
        "passed": passed,
        "feedback": feedback,
        "details": details,
    }


def build_assistant_prompt(
    message: str,
    lesson_id: str | None,
    learner_context: str,
) -> str:
    _, lesson = find_lesson(lesson_id) if lesson_id else (None, None)
    lesson_text = ""
    if lesson:
        task = lesson.get("task") or {}
        lesson_text = (
            f"Aktuelle Lektion: {lesson.get('title', '')}\n"
            f"Lernziel: {lesson.get('learning_goal', lesson.get('summary', ''))}\n"
            f"Erklärung: {lesson.get('explanation', '')}\n"
            f"Aufgabe: {task.get('prompt', '')}\n"
            f"Schritte: {' | '.join(map(str, task.get('steps') or []))}\n"
        )

    return (
        "Du bist der ScratchLab KI-Lernassistent. Antworte auf Deutsch, "
        "freundlich, kurz und altersgerecht. Du bist Lernbegleiter, "
        "kein Lösungsgenerator. Gib keine komplette Lösung und keinen "
        "fertigen Block-für-Block-Bauplan. Nutze Formulierungen wie "
        "'Achte noch einmal auf ...', 'Prüfe einmal ...' oder "
        "'Überlege, welcher Block ...'. "
        "Die automatische .sb3-Prüfung entscheidet über das Bestehen. "
        "Wenn ein Screenshot vorhanden ist, beschreibe auffällige Stellen, "
        "ohne die Aufgabe komplett zu lösen.\n\n"
        f"Lernstand: {learner_context}\n"
        f"{lesson_text}\n"
        f"Frage: {message}"
    )


_GEMINI_MODEL_CACHE = None


def discover_gemini_model(api_key: str) -> str:
    global _GEMINI_MODEL_CACHE
    now = datetime.now(timezone.utc).timestamp()
    if _GEMINI_MODEL_CACHE and now - _GEMINI_MODEL_CACHE[0] < 600:
        return _GEMINI_MODEL_CACHE[1]

    req = Request(
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
        headers={"x-goog-api-key": api_key, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = ""
        raise RuntimeError(f"Gemini-Modellliste Fehler ({exc.code}). {detail[:500]}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Gemini-Modellliste ist momentan nicht erreichbar.") from exc

    available = []
    for item in data.get("models", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name.startswith("models/"):
            name = name[7:]
        methods = item.get("supportedGenerationMethods") or []
        if name and "generateContent" in methods:
            available.append(name)

    if not available:
        raise RuntimeError("Dein Gemini-API-Key bietet kein Modell fÃ¼r generateContent an.")

    preferred = [
        os.environ.get("GEMINI_MODEL", "").strip(),
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-flash-latest",
    ]
    for wanted in preferred:
        if wanted and wanted in available:
            _GEMINI_MODEL_CACHE = (now, wanted)
            print("ScratchLab Gemini-Modell:", wanted)
            return wanted

    flash = [x for x in available if "flash" in x.lower() and "image" not in x.lower() and "tts" not in x.lower() and "live" not in x.lower()]
    chosen = sorted(flash or available)[-1]
    _GEMINI_MODEL_CACHE = (now, chosen)
    print("ScratchLab Gemini-Modell automatisch gewÃ¤hlt:", chosen)
    return chosen


def call_gemini(
    message: str,
    lesson_id: str | None,
    history: list[dict[str, Any]],
    learner_context: str,
    image_base64: str | None = None,
    image_mime_type: str | None = None,
) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY ist auf Render nicht gesetzt.")

    model = discover_gemini_model(api_key)
    contents = []

    for item in history[-6:]:
        old_message = str(item.get("message", "")).strip()
        old_response = str(item.get("response", "")).strip()
        if old_message:
            contents.append({"role": "user", "parts": [{"text": old_message}]})
        if old_response:
            contents.append({"role": "model", "parts": [{"text": old_response}]})

    parts = [{"text": build_assistant_prompt(message, lesson_id, learner_context)}]
    if image_base64:
        parts.append({"inline_data": {"mime_type": image_mime_type or "image/jpeg", "data": image_base64}})

    contents.append({"role": "user", "parts": parts})
    body = {"contents": contents, "generationConfig": {"maxOutputTokens": 700}}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model)}:generateContent"
    req = Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key, "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = ""
        raise RuntimeError(f"Gemini API Fehler ({exc.code}) mit Modell {model}. {detail[:500]}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Gemini ist momentan nicht erreichbar.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini hat keine gÃ¼ltige Antwort geliefert.") from exc

    if isinstance(payload.get("error"), dict):
        raise RuntimeError(payload["error"].get("message") or "Gemini hat einen Fehler gemeldet.")

    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini hat keine Antwort erzeugt.")
    response_parts = candidates[0].get("content", {}).get("parts", [])
    answer = "\n".join(str(p.get("text", "")).strip() for p in response_parts if isinstance(p, dict) and p.get("text")).strip()
    if not answer:
        raise RuntimeError("Gemini hat keine Textantwort erzeugt.")
    return answer[:1800]
class ScratchLabServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class Handler(SimpleHTTPRequestHandler):
    server_version = "ScratchLab/0.2"

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
        self.send_header(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
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

            elif (
                method == "POST"
                and path.startswith("/api/lessons/")
                and path.endswith("/complete")
            ):
                self.complete_lesson(path.split("/")[3])

            elif method == "GET" and path == "/api/projects":
                self.projects()

            elif method == "POST" and path == "/api/projects/check":
                self.check_project()

            elif method == "POST" and path == "/api/projects/check-link":
                self.check_project_link()

            elif method == "POST" and path == "/api/projects":
                self.create_project()

            elif method == "DELETE" and path.startswith("/api/projects/"):
                self.delete_project(int(path.rsplit("/", 1)[1]))

            elif method == "POST" and path == "/api/assistant":
                self.assistant()

            elif method == "POST" and path == "/api/feedback":
                self.feedback()

            elif method == "GET" and path == "/api/admin/feedback":
                self.admin_feedback()

            elif method == "POST" and path == "/api/checkout/premium":
                self.checkout_premium()

            elif method == "POST" and path == "/api/checkout/lesson":
                self.checkout_lesson()

            else:
                self.json_response({"error": "Not found"}, HTTPStatus.NOT_FOUND)

        except ValueError as exc:
            self.json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except PermissionError as exc:
            self.json_response({"error": str(exc)}, HTTPStatus.UNAUTHORIZED)
        except SupabaseError as exc:
            self.json_response({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)
        except RuntimeError as exc:
            self.json_response({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)
        except Exception as exc:
            print("ScratchLab server error:", repr(exc))
            self.json_response(
                {"error": "Serverfehler. Bitte versuche es erneut."},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def read_json(self, max_bytes: int = 16_000_000) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > max_bytes:
            raise ValueError("Die Anfrage ist zu groß.")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Ungültige JSON-Anfrage.") from exc
        if not isinstance(data, dict):
            raise ValueError("Ungültige Anfrage.")
        return data

    def session_token(self) -> str | None:
        cookie = SimpleCookie(self.headers.get("Cookie"))
        value = cookie.get(SESSION_COOKIE)
        return value.value if value else None

    def current_user(self) -> dict[str, Any] | None:
        return current_user_from_token(self.session_token())

    def require_user(self) -> dict[str, Any]:
        user = self.current_user()
        if not user:
            raise PermissionError("Bitte melde dich an.")
        return user

    def require_user_response(self) -> None:
        user = self.current_user()
        if user:
            self.json_response({"user": public_user(user)})
        else:
            self.json_response({"user": None})

    def set_session_cookie(self, token: str) -> None:
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE}={token}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=2592000",
        )

    def register(self) -> None:
        payload = self.read_json()
        username = str(payload.get("username", "")).strip()[:28]
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))

        if len(username) < 3:
            raise ValueError("Der Benutzername braucht mindestens 3 Zeichen.")
        if not validate_email(email):
            raise ValueError("Bitte gib eine gültige E-Mail-Adresse ein.")
        if len(password) < 8:
            raise ValueError("Das Passwort braucht mindestens 8 Zeichen.")

        password_hash, salt = hash_password(password)

        try:
            rows = sb_insert(
                "users",
                {
                    "username": username,
                    "email": email,
                    "password_hash": password_hash,
                    "salt": salt,
                    "xp": 0,
                    "level": 1,
                    "premium_status": "free",
                    "created_at": now_iso(),
                },
            )
        except SupabaseError:
            raise ValueError("Benutzername oder E-Mail ist bereits vergeben.")

        if not rows:
            raise SupabaseError("Der Account konnte nicht erstellt werden.")

        user = rows[0]
        token = create_session(user)

        body = json.dumps({"user": public_user(user)}, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.set_session_cookie(token)
        self.end_headers()
        self.wfile.write(body)

    def login(self) -> None:
        payload = self.read_json()
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))

        user = find_user_by_email(email)
        if not user or not verify_password(
            password,
            user.get("password_hash", ""),
            user.get("salt", ""),
        ):
            self.json_response(
                {"error": "E-Mail oder Passwort ist falsch."},
                HTTPStatus.UNAUTHORIZED,
            )
            return

        token = create_session(user)
        body = json.dumps({"user": public_user(user)}, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.set_session_cookie(token)
        self.end_headers()
        self.wfile.write(body)

    def logout(self) -> None:
        token = self.session_token()
        if token:
            try:
                sb_delete("sessions", filters=[("token", f"eq.{token}")])
            except Exception:
                pass

        body = b'{"ok":true}'
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE}=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0",
        )
        self.end_headers()
        self.wfile.write(body)

    def progress(self) -> None:
        user = self.require_user()
        rows = sb_select(
            "progress",
            filters=[("user_id", f"eq.{user['id']}")],
            order="completed_at.desc",
        )
        completed_ids = {str(row["lesson_id"]) for row in rows}

        badges = []
        user_badges = sb_select(
            "user_badges",
            select="badge_id,awarded_at",
            filters=[("user_id", f"eq.{user['id']}")],
            order="awarded_at.desc",
        )
        for item in user_badges:
            badge_rows = sb_select(
                "badges",
                filters=[("id", f"eq.{item['badge_id']}")],
                limit=1,
            )
            if badge_rows:
                badges.append(badge_rows[0])

        projects = sb_select(
            "projects",
            select="id,title,updated_at,is_public",
            filters=[("user_id", f"eq.{user['id']}")],
            order="updated_at.desc",
            limit=5,
        )

        self.json_response(
            {
                "completed": rows,
                "badges": badges,
                "user": public_user(user),
                "courseProgress": course_progress(completed_ids),
                "nextLesson": next_lesson_after(completed_ids),
                "recentActivity": rows[:5],
                "projects": projects,
            }
        )

    def has_lesson_access(self, user_id: int, lesson_id: str) -> bool:
        _, lesson = find_lesson(lesson_id)
        if not lesson or not lesson.get("premium"):
            return True

        user = find_user_by_id(user_id)
        if user and user.get("premium_status") == "premium":
            return True

        purchases = sb_select(
            "lesson_purchases",
            filters=[
                ("user_id", f"eq.{user_id}"),
                ("lesson_id", f"eq.{lesson_id}"),
                ("status", "eq.paid"),
            ],
            limit=1,
        )
        return bool(purchases)

    def award_badges(self, user_id: int) -> None:
        rows = sb_select(
            "progress",
            select="lesson_id",
            filters=[("user_id", f"eq.{user_id}")],
        )
        lesson_ids = {str(row["lesson_id"]) for row in rows}
        count = len(lesson_ids)

        badge_rules = []
        if count >= 1:
            badge_rules.append("first-step")
        if "move-sprite" in lesson_ids:
            badge_rules.append("motion-maker")
        if count >= 3:
            badge_rules.append("mini-maker")
        if count >= 5:
            badge_rules.append("block-builder")
        if count >= 50:
            badge_rules.append("scratch-master")
        if {"repeat-loop", "forever-loop", "repeat-until"} & lesson_ids:
            badge_rules.append("loop-pro")
        if {"score-counter", "timer", "lives"} & lesson_ids:
            badge_rules.append("variable-keeper")
        if {"catch-game", "maze-game", "dodge-game"} & lesson_ids:
            badge_rules.append("game-maker")

        checks = sb_select(
            "project_checks",
            select="id",
            filters=[("user_id", f"eq.{user_id}")],
            limit=1,
        )
        if checks:
            badge_rules.append("debugger")

        for badge_id in sorted(set(badge_rules)):
            existing = sb_select(
                "user_badges",
                filters=[
                    ("user_id", f"eq.{user_id}"),
                    ("badge_id", f"eq.{badge_id}"),
                ],
                limit=1,
            )
            if not existing:
                sb_insert(
                    "user_badges",
                    {
                        "user_id": user_id,
                        "badge_id": badge_id,
                        "awarded_at": now_iso(),
                    },
                    returning=False,
                )

    def complete_lesson(self, lesson_id: str) -> None:
        user = self.require_user()
        payload = self.read_json()
        verification_token = (
            str(payload.get("verificationToken", "")).strip()
        )

        course, lesson = find_lesson(lesson_id)

        if not lesson or not course:
            self.json_response(
                {"error": "Lektion nicht gefunden."},
                HTTPStatus.NOT_FOUND,
            )
            return

        if not self.has_lesson_access(user["id"], lesson_id):
            self.json_response(
                {
                    "error": "Diese Lektion ist Premium und muss freigeschaltet werden.",
                    "requiresPayment": True,
                },
                HTTPStatus.PAYMENT_REQUIRED,
            )
            return

        already_done = sb_select(
            "progress",
            filters=[
                ("user_id", f"eq.{user['id']}"),
                ("lesson_id", f"eq.{lesson_id}"),
            ],
            limit=1,
        )

        if not already_done:
            if not verification_token:
                self.json_response(
                    {
                        "error": (
                            "Prüfe zuerst dein Scratch-Projekt erfolgreich. "
                            "Erst danach kannst du die Lektion abschließen."
                        ),
                        "requiresProjectCheck": True,
                    },
                    HTTPStatus.CONFLICT,
                )
                return

            checks = sb_select(
                "project_checks",
                select="id,score,total,verification_token,used_at",
                filters=[
                    ("user_id", f"eq.{user['id']}"),
                    ("lesson_id", f"eq.{lesson_id}"),
                    (
                        "verification_token",
                        f"eq.{verification_token}",
                    ),
                ],
                limit=1,
            )

            if not checks:
                self.json_response(
                    {
                        "error": (
                            "Die Projektprüfung ist nicht gültig. "
                            "Bitte prüfe deine Scratch-Datei erneut."
                        ),
                        "requiresProjectCheck": True,
                    },
                    HTTPStatus.CONFLICT,
                )
                return

            check = checks[0]
            score = int(check.get("score") or 0)
            total = int(check.get("total") or 0)

            if (
                check.get("used_at")
                or total <= 0
                or score != total
            ):
                self.json_response(
                    {
                        "error": (
                            "Diese Projektprüfung wurde bereits verwendet. "
                            "Bitte führe eine neue Prüfung durch."
                        ),
                        "requiresProjectCheck": True,
                    },
                    HTTPStatus.CONFLICT,
                )
                return

        awarded = 0 if already_done else int(lesson.get("xp") or 0)

        if not already_done:
            sb_insert(
                "progress",
                {
                    "user_id": user["id"],
                    "course_id": course["id"],
                    "lesson_id": lesson_id,
                    "xp_awarded": awarded,
                    "completed_at": now_iso(),
                },
                returning=False,
            )

            sb_update(
                "project_checks",
                {"used_at": now_iso()},
                filters=[
                    ("user_id", f"eq.{user['id']}"),
                    ("lesson_id", f"eq.{lesson_id}"),
                    (
                        "verification_token",
                        f"eq.{verification_token}",
                    ),
                ],
            )

            new_xp = int(user.get("xp") or 0) + awarded
            completed_rows = sb_select(
                "progress",
                select="lesson_id",
                filters=[("user_id", f"eq.{user['id']}")],
            )
            completed_ids = {
                str(row["lesson_id"])
                for row in completed_rows
            }
            next_lesson = next_lesson_after(completed_ids)

            updated_rows = sb_update(
                "users",
                {
                    "xp": new_xp,
                    "level": calculate_level(new_xp),
                    "last_lesson_id": lesson_id,
                    "current_lesson_id": (
                        next_lesson["id"]
                        if next_lesson
                        else None
                    ),
                },
                filters=[("id", f"eq.{user['id']}")],
            )

            if updated_rows:
                user = updated_rows[0]

            self.award_badges(user["id"])

        fresh = find_user_by_id(user["id"]) or user

        self.json_response(
            {
                "awardedXp": awarded,
                "user": public_user(fresh),
                "message": lesson.get(
                    "success_message",
                    "Lektion erfolgreich abgeschlossen!",
                ),
            }
        )

    def projects(self) -> None:
        user = self.require_user()
        own = sb_select(
            "projects",
            filters=[("user_id", f"eq.{user['id']}")],
            order="updated_at.desc",
        )
        public = sb_select(
            "projects",
            filters=[("is_public", "eq.true")],
            order="updated_at.desc",
            limit=20,
        )
        self.json_response({"own": own, "public": public})

    def create_project(self) -> None:
        user = self.require_user()
        payload = self.read_json()
        title = str(payload.get("title", "")).strip()[:80]
        description = str(payload.get("description", "")).strip()[:600]
        scratch_url = str(payload.get("scratchUrl", "")).strip()[:300]
        is_public = bool(payload.get("isPublic"))

        if len(title) < 3:
            raise ValueError("Der Projekttitel braucht mindestens 3 Zeichen.")

        rows = sb_insert(
            "projects",
            {
                "user_id": user["id"],
                "title": title,
                "description": description,
                "scratch_url": scratch_url,
                "is_public": is_public,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            },
        )
        self.json_response({"project": rows[0] if rows else {}})

    def delete_project(self, project_id: int) -> None:
        user = self.require_user()
        sb_delete(
            "projects",
            filters=[
                ("id", f"eq.{project_id}"),
                ("user_id", f"eq.{user['id']}"),
            ],
        )
        self.json_response({"ok": True})

    def read_sb3_from_payload(self, encoded: str) -> bytes:
        encoded = encoded.strip()
        if encoded.startswith("data:") and "," in encoded:
            encoded = encoded.split(",", 1)[1]

        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("Die .sb3-Datei konnte nicht gelesen werden.") from exc

        if not data:
            raise ValueError("Die .sb3-Datei ist leer.")

        if len(data) > 10 * 1024 * 1024:
            raise ValueError("Die .sb3-Datei darf maximal 10 MB groß sein.")

        return data

    def check_project(self) -> None:
        user = self.require_user()
        payload = self.read_json()

        lesson_id = str(payload.get("lessonId", "")).strip() or None
        project_id = payload.get("projectId")
        encoded = str(payload.get("dataBase64", "")).strip()

        if not encoded:
            raise ValueError("Bitte wähle zuerst eine Scratch-Datei aus.")

        sb3_bytes = self.read_sb3_from_payload(encoded)
        analysis = analyze_scratch_project(sb3_bytes)

        _, lesson = find_lesson(lesson_id) if lesson_id else (None, None)
        result = evaluate_project_for_lesson(analysis, lesson)

        verification_token = (
            secrets.token_urlsafe(32)
            if result.get("passed")
            else None
        )

        sb_insert(
            "project_checks",
            {
                "user_id": user["id"],
                "project_id": int(project_id) if project_id else None,
                "lesson_id": lesson_id,
                "score": result["score"],
                "total": result["total"],
                "feedback": result["feedback"],
                "details": json.dumps(
                    result["details"],
                    ensure_ascii=False,
                ),
                "created_at": now_iso(),
                "verification_token": verification_token,
                "used_at": None,
            },
            returning=False,
        )

        self.json_response({
            "analysis": analysis,
            "result": result,
            "verificationToken": verification_token,
        })

    def check_project_link(self) -> None:
        user = self.require_user()
        payload = self.read_json()

        lesson_id = str(payload.get("lessonId", "")).strip() or None
        scratch_url = str(payload.get("scratchUrl", "")).strip()
        if not scratch_url:
            raise ValueError("Bitte füge einen Scratch-Projekt-Link ein.")

        project_id = scratch_project_id_from_url(scratch_url)
        project = fetch_scratch_project_json(project_id)
        analysis = analyze_scratch_project_json(project)

        _, lesson = find_lesson(lesson_id) if lesson_id else (None, None)
        result = evaluate_project_for_lesson(analysis, lesson)

        verification_token = (
            secrets.token_urlsafe(32) if result.get("passed") else None
        )

        sb_insert(
            "project_checks",
            {
                "user_id": user["id"],
                "project_id": None,
                "lesson_id": lesson_id,
                "score": result["score"],
                "total": result["total"],
                "feedback": result["feedback"],
                "details": json.dumps(result["details"], ensure_ascii=False),
                "created_at": now_iso(),
                "verification_token": verification_token,
                "used_at": None,
            },
            returning=False,
        )

        self.json_response({
            "projectId": project_id,
            "analysis": analysis,
            "result": result,
            "verificationToken": verification_token,
        })

    def assistant(self) -> None:
        user = self.current_user()
        payload = self.read_json()

        message = str(payload.get("message", "")).strip()[:1200]
        lesson_id = str(payload.get("lessonId", "")).strip() or None
        raw_image_base64 = payload.get("imageBase64")
        raw_image_mime_type = payload.get("imageMimeType")

        image_base64 = (
            str(raw_image_base64).strip()
            if raw_image_base64
            else None
        )
        image_mime_type = (
            str(raw_image_mime_type).strip()
            if raw_image_mime_type
            else None
        )

        if len(message) < 2 and not image_base64:
            raise ValueError(
                "Schreib kurz, wobei du Hilfe brauchst, "
                "oder lade einen Screenshot hoch."
            )

        if image_base64:
            if image_mime_type not in {
                "image/png",
                "image/jpeg",
                "image/webp",
            }:
                raise ValueError(
                    "Bitte nutze PNG, JPG/JPEG oder WebP."
                )

            if len(image_base64) > 7_000_000:
                raise ValueError(
                    "Der Screenshot darf maximal 5 MB groß sein."
                )

        if user:
            history = sb_select(
                "ai_interactions",
                select="message,response",
                filters=[
                    ("user_id", f"eq.{user['id']}"),
                    (
                        "lesson_id",
                        f"eq.{lesson_id}"
                        if lesson_id
                        else "is.null",
                    ),
                ],
                order="created_at.desc",
                limit=6,
            )

            completed = sb_select(
                "progress",
                select="lesson_id",
                filters=[("user_id", f"eq.{user['id']}")],
            )

            learner_context = (
                f"Level {user.get('level', 1)}, "
                f"{user.get('xp', 0)} XP, "
                f"{len(completed)} abgeschlossene Lektionen."
            )
        else:
            history = []
            learner_context = "Nicht eingeloggter Nutzer."

        history = list(reversed(history))

        # Important: Never silently replace Gemini with pre-written answers.
        response = call_gemini(
            message,
            lesson_id,
            history,
            learner_context,
            image_base64,
            image_mime_type,
        )

        sb_insert(
            "ai_interactions",
            {
                "user_id": user["id"] if user else None,
                "lesson_id": lesson_id,
                "message": message,
                "response": response,
                "safety_label": "gemini_hint",
                "created_at": now_iso(),
            },
            returning=False,
        )

        self.json_response(
            {
                "response": response,
                "safetyLabel": "gemini_hint",
            }
        )

    def feedback(self) -> None:
        user = self.current_user()
        payload = self.read_json()

        feedback_type = str(payload.get("type", "")).strip()[:40]
        message = str(payload.get("message", "")).strip()[:2000]
        rating = payload.get("rating")
        email = str(payload.get("email", "")).strip()[:200]

        if feedback_type not in {
            "Lob",
            "Verbesserung",
            "Fehler",
            "Hilfe",
        }:
            feedback_type = "Feedback"

        if len(message) < 5:
            raise ValueError("Bitte schreib ein bisschen mehr zu deinem Feedback.")

        rating_value = None
        if rating not in (None, ""):
            try:
                rating_value = max(1, min(5, int(rating)))
            except (TypeError, ValueError):
                raise ValueError("Die Bewertung muss zwischen 1 und 5 liegen.")

        sb_insert(
            "feedback",
            {
                "type": feedback_type,
                "message": message,
                "email": email or (user.get("email") if user else None),
                "rating": rating_value,
                "user_id": user["id"] if user else None,
                "created_at": now_iso(),
            },
            returning=False,
        )

        self.json_response({"ok": True})

    def require_admin(self) -> dict[str, Any]:
        user = self.require_user()
        if not is_admin_user(user):
            raise PermissionError("Kein Betreiberzugriff.")
        return user

    def admin_feedback(self) -> None:
        self.require_admin()

        rows = sb_select(
            "feedback",
            select="id,type,message,email,rating,user_id,created_at",
            order="created_at.desc",
            limit=500,
        )

        # Do not expose internal user data beyond what the feedback table
        # already stores. The admin endpoint itself is protected by ADMIN_EMAIL.
        self.json_response({"feedback": rows})

    def pricing(self) -> None:
        self.json_response(
            {
                "singleLessonPriceEur": SINGLE_LESSON_PRICE_EUR,
                "premiumMonthlyPriceEur": PREMIUM_MONTHLY_PRICE_EUR,
                "checkoutReady": bool(
                    STRIPE_SECRET_KEY
                    and STRIPE_PREMIUM_PRICE_ID
                    and STRIPE_LESSON_PRICE_ID
                ),
            }
        )

    def checkout_premium(self) -> None:
        self.require_user()
        if not STRIPE_SECRET_KEY or not STRIPE_PREMIUM_PRICE_ID:
            self.json_response(
                {
                    "error": "Stripe ist noch nicht konfiguriert.",
                    "checkoutReady": False,
                },
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        self.json_response(
            {
                "error": (
                    "Stripe ist noch nicht vollständig angebunden. "
                    "Zahlungen werden erst nach Einrichtung von Checkout und Webhooks aktiviert."
                ),
                "checkoutReady": False,
            },
            HTTPStatus.SERVICE_UNAVAILABLE,
        )

    def checkout_lesson(self) -> None:
        self.require_user()
        if not STRIPE_SECRET_KEY or not STRIPE_LESSON_PRICE_ID:
            self.json_response(
                {
                    "error": "Stripe ist noch nicht konfiguriert.",
                    "checkoutReady": False,
                },
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        self.json_response(
            {
                "error": (
                    "Stripe ist noch nicht vollständig angebunden. "
                    "Zahlungen werden erst nach Einrichtung von Checkout und Webhooks aktiviert."
                ),
                "checkoutReady": False,
            },
            HTTPStatus.SERVICE_UNAVAILABLE,
        )

    def json_response(
        self,
        payload: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = ScratchLabServer(("0.0.0.0", port), Handler)
    print(f"ScratchLab läuft auf http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
aders()
        self.wfile.write(body)


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = ScratchLabServer(("0.0.0.0", port), Handler)
    print(f"ScratchLab läuft auf http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
