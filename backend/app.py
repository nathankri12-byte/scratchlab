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

from urllib.parse import quote, urlencode, urlparse

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
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()



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



def discover_gemini_models(api_key: str) -> list[str]:

    """Return usable text-generation Flash models for this API key."""

    global _GEMINI_MODEL_CACHE


    now = datetime.now(timezone.utc).timestamp()


    if _GEMINI_MODEL_CACHE and now - _GEMINI_MODEL_CACHE[0] < 600:

        return _GEMINI_MODEL_CACHE[1]


    request = Request(

        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",

        headers={

            "x-goog-api-key": api_key,

            "Accept": "application/json",

        },

        method="GET",

    )


    try:

        with urlopen(request, timeout=10) as response:

            payload = json.loads(response.read().decode("utf-8"))

    except HTTPError as exc:

        raise RuntimeError(

            f"Gemini-Modellliste Fehler ({exc.code})."

        ) from exc

    except (URLError, TimeoutError, json.JSONDecodeError) as exc:

        raise RuntimeError(

            "Gemini-Modellliste ist momentan nicht erreichbar."

        ) from exc


    available = []


    for item in payload.get("models", []):

        if not isinstance(item, dict):

            continue


        name = str(item.get("name", "")).strip()

        if name.startswith("models/"):

            name = name[7:]


        methods = item.get("supportedGenerationMethods") or []


        if name and "generateContent" in methods:

            available.append(name)


    if not available:

        raise RuntimeError(

            "Dein Gemini-API-Key bietet kein Modell für generateContent an."

        )


    # Prefer fast stable Flash models over the currently overloaded

    # 3.7 Flash endpoint. The API key still determines what is available.

    preferred = [

        "gemini-3.6-flash",

        "gemini-3.5-flash",

        "gemini-3.7-flash",

        "gemini-3.5-flash-lite",

        "gemini-3.1-flash-lite",

        "gemini-flash-latest",

    ]


    models = [

        name for name in preferred

        if name in available

    ]


    for name in sorted(available):

        lower = name.lower()

        if (

            "flash" in lower

            and "image" not in lower

            and "tts" not in lower

            and "live" not in lower

            and name not in models

        ):

            models.append(name)


    if not models:

        models = sorted(available)


    _GEMINI_MODEL_CACHE = (now, models)

    print("ScratchLab Gemini-Modelle:", ", ".join(models))

    return models



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

        raise RuntimeError(

            "GEMINI_API_KEY ist auf Render nicht gesetzt."

        )


    models = discover_gemini_models(api_key)


    contents = []


    for item in history[-4:]:

        old_message = str(item.get("message", "")).strip()

        old_response = str(item.get("response", "")).strip()


        if old_message:

            contents.append({

                "role": "user",

                "parts": [{"text": old_message}],

            })


        if old_response:

            contents.append({

                "role": "model",

                "parts": [{"text": old_response}],

            })


    parts = [{

        "text": build_assistant_prompt(

            message,

            lesson_id,

            learner_context,

        )

    }]


    if image_base64:

        parts.append({

            "inline_data": {

                "mime_type": image_mime_type or "image/jpeg",

                "data": image_base64,

            }

        })


    contents.append({

        "role": "user",

        "parts": parts,

    })


    body = {

        "contents": contents,

        "generationConfig": {

            "maxOutputTokens": 450,

        },

    }


    last_error = None


    for model in models[:6]:

        url = (

            "https://generativelanguage.googleapis.com/v1beta/models/"

            f"{quote(model)}:generateContent"

        )


        request = Request(

            url,

            data=json.dumps(

                body,

                ensure_ascii=False,

            ).encode("utf-8"),

            headers={

                "Content-Type": "application/json",

                "x-goog-api-key": api_key,

                "Accept": "application/json",

            },

            method="POST",

        )


        try:

            # Keep each model attempt short so a bad/overloaded endpoint

            # does not make the whole ScratchLab UI feel frozen.

            with urlopen(request, timeout=14) as response:

                payload = json.loads(

                    response.read().decode("utf-8")

                )


            if isinstance(payload.get("error"), dict):

                raise RuntimeError(

                    payload["error"].get("message")

                    or "Gemini hat einen Fehler gemeldet."

                )


            candidates = payload.get("candidates") or []

            if not candidates:

                raise RuntimeError(

                    "Gemini hat keine Antwort erzeugt."

                )


            response_parts = (

                candidates[0]

                .get("content", {})

                .get("parts", [])

            )


            answer = "\n".join(

                str(part.get("text", "")).strip()

                for part in response_parts

                if isinstance(part, dict)

                and part.get("text")

            ).strip()


            if answer:

                return answer[:1800]


            raise RuntimeError(

                "Gemini hat keine Textantwort erzeugt."

            )


        except HTTPError as exc:

            try:

                detail = exc.read().decode("utf-8")

            except Exception:

                detail = ""


            last_error = RuntimeError(

                f"Gemini API Fehler ({exc.code}) mit Modell {model}. "

                f"{detail[:350]}"

            )


            # 503/429 means this model endpoint is unavailable or busy.

            # Immediately move to the next available model instead of

            # waiting several seconds and then retrying the same model.

            if exc.code in (429, 503):

                print(

                    f"Gemini {model} -> HTTP {exc.code}; "

                    "wechsle sofort zum Fallback."

                )

                continue


            raise last_error from exc


        except (URLError, TimeoutError) as exc:

            last_error = RuntimeError(

                f"Gemini {model} ist nicht erreichbar."

            )

            print(

                f"Gemini {model} nicht erreichbar; "

                "wechsle sofort zum Fallback."

            )

            continue


        except RuntimeError as exc:

            last_error = exc

            # A model-specific failure should not kill the whole AI.

            continue


    raise last_error or RuntimeError(

        "Kein verfügbares Gemini-Modell konnte antworten."

    )




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


            elif method == "POST" and path == "/api/premium/cancel":
                self.cancel_premium()
            elif method == "POST" and path == "/api/checkout/premium":

                self.checkout_premium()


            elif method == "POST" and path == "/api/checkout/lesson":

                self.checkout_lesson()


            elif method == "POST" and path == "/api/stripe/webhook":


                self.stripe_webhook()


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


        completed_ids = {

            str(row["lesson_id"])

            for row in rows

        }


        badge_links = sb_select(

            "user_badges",

            select="badge_id,awarded_at",

            filters=[("user_id", f"eq.{user['id']}")],

            order="awarded_at.desc",

        )


        badge_ids = [

            str(item["badge_id"])

            for item in badge_links

            if item.get("badge_id")

        ]


        badges = []

        if badge_ids:

            # One request instead of one request per badge.

            quoted = ",".join(

                quote.replace("'", "''")

                for quote in badge_ids

            )

            badge_rows = sb_select(

                "badges",

                filters=[("id", f"in.({quoted})")],

            )

            badges_by_id = {

                str(row["id"]): row

                for row in badge_rows

            }

            badges = [

                badges_by_id[badge_id]

                for badge_id in badge_ids

                if badge_id in badges_by_id

            ]


        projects = sb_select(

            "projects",

            select="id,title,updated_at,is_public",

            filters=[("user_id", f"eq.{user['id']}")],

            order="updated_at.desc",

            limit=5,

        )


        self.json_response({

            "completed": rows,

            "badges": badges,

            "user": public_user(user),

            "courseProgress": course_progress(completed_ids),

            "nextLesson": next_lesson_after(completed_ids),

            "recentActivity": rows[:5],

            "projects": projects,

        })


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


    def create_stripe_checkout(

        self,

        user: dict[str, Any],

        price_id: str,

        mode: str,

        lesson_id: str | None = None,

    ) -> dict[str, Any]:

        if not STRIPE_SECRET_KEY:

            raise RuntimeError(

                "STRIPE_SECRET_KEY ist auf Render nicht gesetzt."

            )

        if not price_id:

            raise RuntimeError(

                "Der Stripe-Preis ist noch nicht konfiguriert."

            )

        if mode not in {"payment", "subscription"}:

            raise ValueError("Ungültiger Stripe-Checkout-Modus.")


        base_url = os.environ.get(

            "PUBLIC_BASE_URL",

            "https://scratchlab.onrender.com",

        ).strip().rstrip("/")


        data = {

            "mode": mode,

            "line_items[0][price]": price_id,

            "line_items[0][quantity]": "1",

            "success_url": (

                f"{base_url}/#/payment-success"

                f"?session_id={{CHECKOUT_SESSION_ID}}"

            ),

            "cancel_url": f"{base_url}/#/premium",

            "customer_email": str(user.get("email") or "").strip(),

            "client_reference_id": str(user["id"]),

            "metadata[user_id]": str(user["id"]),

            "metadata[purchase_type]": (

                "premium" if mode == "subscription" else "lesson"

            ),

        }


        if lesson_id:

            data["metadata[lesson_id]"] = str(lesson_id)

            data["cancel_url"] = f"{base_url}/#/lesson/{quote(lesson_id)}"


        request = Request(

            "https://api.stripe.com/v1/checkout/sessions",

            data=urlencode(data).encode("utf-8"),

            headers={

                "Authorization": (

                    "Basic "

                    + base64.b64encode(

                        f"{STRIPE_SECRET_KEY}:".encode("utf-8")

                    ).decode("ascii")

                ),

                "Content-Type": "application/x-www-form-urlencoded",

                "Accept": "application/json",

                "User-Agent": "ScratchLab/1.0",

            },

            method="POST",

        )


        try:

            with urlopen(request, timeout=15) as response:

                payload = json.loads(

                    response.read().decode("utf-8")

                )

        except HTTPError as exc:

            try:

                detail = exc.read().decode("utf-8")

                error_payload = json.loads(detail)

                message = (

                    error_payload.get("error", {}).get("message")

                    or detail[:500]

                )

            except Exception:

                message = "Stripe konnte die Checkout-Session nicht erstellen."

            raise RuntimeError(

                f"Stripe-Fehler ({exc.code}): {message}"

            ) from exc

        except (URLError, TimeoutError, json.JSONDecodeError) as exc:

            raise RuntimeError(

                "Stripe ist momentan nicht erreichbar."

            ) from exc


        checkout_url = payload.get("url")

        if not checkout_url:

            raise RuntimeError(

                "Stripe hat keine Checkout-URL zurückgegeben."

            )


        return {

            "checkoutUrl": checkout_url,

            "sessionId": payload.get("id"),

        }


    def _verify_stripe_signature(self, payload: bytes, signature_header: str) -> bool:
        secret = STRIPE_WEBHOOK_SECRET
        if not secret or not signature_header:
            return False

        timestamp = None
        signatures = []

        for item in signature_header.split(","):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            if key == "t":
                timestamp = value
            elif key == "v1":
                signatures.append(value)

        if not timestamp or not signatures:
            return False

        try:
            timestamp_int = int(timestamp)
        except ValueError:
            return False

        if abs(datetime.now(timezone.utc).timestamp() - timestamp_int) > 300:
            return False

        signed = f"{timestamp}.".encode("utf-8") + payload
        expected = hmac.new(
            secret.encode("utf-8"),
            signed,
            hashlib.sha256,
        ).hexdigest()

        return any(
            hmac.compare_digest(expected, candidate)
            for candidate in signatures
        )

    def stripe_webhook(self) -> None:
        signature = self.headers.get("Stripe-Signature", "")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except (TypeError, ValueError):
            length = 0

        if length <= 0 or length > 2_000_000:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.end_headers()
            return

        raw_body = self.rfile.read(length)

        if not self._verify_stripe_signature(raw_body, signature):
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.end_headers()
            return

        try:
            event = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.end_headers()
            return

        if event.get("type") != "checkout.session.completed":
            self.json_response({"received": True})
            return

        session = ((event.get("data") or {}).get("object") or {})
        payment_status = str(session.get("payment_status") or "").lower()
        metadata = session.get("metadata") or {}

        user_id = str(metadata.get("user_id") or "").strip()
        purchase_type = str(metadata.get("purchase_type") or "").strip().lower()
        lesson_id = str(metadata.get("lesson_id") or "").strip()

        if not user_id:
            raise ValueError("Stripe-Webhook: user_id fehlt.")

        if purchase_type == "premium":
            if payment_status not in {"paid", "no_payment_required"}:
                self.json_response({"received": True})
                return

            sb_update(
                "users",
                {"premium_status": "premium"},
                filters=[("id", f"eq.{user_id}")],
            )

            print("Stripe: Premium freigeschaltet fÃ¼r", user_id)

        elif purchase_type == "lesson":
            if payment_status != "paid" or not lesson_id:
                self.json_response({"received": True})
                return

            existing = sb_select(
                "lesson_purchases",
                filters=[
                    ("user_id", f"eq.{user_id}"),
                    ("lesson_id", f"eq.{lesson_id}"),
                    ("status", "eq.paid"),
                ],
                limit=1,
            )

            if not existing:
                sb_insert(
                    "lesson_purchases",
                    {
                        "user_id": user_id,
                        "lesson_id": lesson_id,
                        "status": "paid",
                        "created_at": now_iso(),
                    },
                    returning=False,
                )

            print("Stripe: Lektion freigeschaltet fÃ¼r", user_id, lesson_id)

        self.json_response({"received": True})
    def _stripe_cancel_request(self, method: str, url: str, data: dict[str, str] | None = None) -> dict[str, Any]:
        if not STRIPE_SECRET_KEY:
            raise RuntimeError("STRIPE_SECRET_KEY ist auf Render nicht gesetzt.")

        request_data = urlencode(data or {}).encode("utf-8") if data is not None else None
        request = Request(
            url,
            data=request_data,
            headers={
                "Authorization": (
                    "Basic "
                    + base64.b64encode(
                        f"{STRIPE_SECRET_KEY}:".encode("utf-8")
                    ).decode("ascii")
                ),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "ScratchLab/1.0",
            },
            method=method,
        )

        try:
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8")
                error_payload = json.loads(detail)
                message = (
                    error_payload.get("error", {}).get("message")
                    or detail[:500]
                )
            except Exception:
                message = "Stripe konnte die Anfrage nicht verarbeiten."
            raise RuntimeError(f"Stripe-Fehler ({exc.code}): {message}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("Stripe ist momentan nicht erreichbar.") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Stripe hat eine ungÃ¼ltige Antwort geliefert.")
        return payload

    def cancel_premium(self) -> None:
        user = self.require_user()
        email = str(user.get("email") or "").strip().lower()

        if not email:
            raise RuntimeError("FÃ¼r die KÃ¼ndigung fehlt die E-Mail-Adresse.")

        customers = self._stripe_cancel_request(
            "GET",
            "https://api.stripe.com/v1/customers?limit=20&email=" + quote(email, safe=""),
        )

        customer = next(
            (
                item for item in (customers.get("data") or [])
                if str(item.get("email") or "").strip().lower() == email
            ),
            None,
        )

        if not customer:
            raise ValueError("FÃ¼r dein Konto wurde kein Stripe-Kunde gefunden.")

        customer_id = str(customer.get("id") or "").strip()
        if not customer_id:
            raise RuntimeError("Die Stripe-Kunden-ID fehlt.")

        subscriptions = self._stripe_cancel_request(
            "GET",
            "https://api.stripe.com/v1/subscriptions?limit=20&customer="
            + quote(customer_id, safe="")
            + "&status=all",
        )

        active_statuses = {"active", "trialing", "past_due", "unpaid"}
        subscription = next(
            (
                item for item in (subscriptions.get("data") or [])
                if str(item.get("status") or "").lower() in active_statuses
            ),
            None,
        )

        if not subscription:
            raise ValueError("Es wurde kein aktives Premium-Abo gefunden.")

        if subscription.get("cancel_at_period_end"):
            self.json_response(
                {
                    "ok": True,
                    "alreadyScheduled": True,
                    "currentPeriodEnd": subscription.get("current_period_end"),
                }
            )
            return

        subscription_id = str(subscription.get("id") or "").strip()
        if not subscription_id:
            raise RuntimeError("Die Stripe-Abo-ID fehlt.")

        result = self._stripe_cancel_request(
            "POST",
            "https://api.stripe.com/v1/subscriptions/" + quote(subscription_id, safe=""),
            {"cancel_at_period_end": "true"},
        )

        self.json_response(
            {
                "ok": True,
                "scheduled": True,
                "currentPeriodEnd": result.get("current_period_end"),
            }
        )
    def checkout_premium(self) -> None:

        user = self.require_user()

        self.json_response(

            self.create_stripe_checkout(

                user=user,

                price_id=STRIPE_PREMIUM_PRICE_ID,

                mode="subscription",

            )

        )


    def checkout_lesson(self) -> None:

        user = self.require_user()

        payload = self.read_json()

        lesson_id = str(payload.get("lessonId") or "").strip()


        if not lesson_id:

            raise ValueError("Keine Lektion angegeben.")


        self.json_response(

            self.create_stripe_checkout(

                user=user,

                price_id=STRIPE_LESSON_PRICE_ID,

                mode="payment",

                lesson_id=lesson_id,

            )

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
