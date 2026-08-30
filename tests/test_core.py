import io
import os
import json
import zipfile
import tempfile
import unittest
from pathlib import Path

from backend import app


class ScratchLabCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite3"
        app.init_db(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_password_hash_uses_salt_and_verifies(self):
        hashed, salt = app.hash_password("super-secret")
        self.assertNotEqual(hashed, "super-secret")
        self.assertTrue(app.verify_password("super-secret", hashed, salt))
        self.assertFalse(app.verify_password("wrong-password", hashed, salt))

    def test_level_calculation(self):
        self.assertEqual(app.calculate_level(0), 1)
        self.assertEqual(app.calculate_level(99), 1)
        self.assertEqual(app.calculate_level(100), 2)
        self.assertEqual(app.calculate_level(240), 3)

    def test_courses_are_data_driven(self):
        courses = app.load_courses()
        self.assertGreaterEqual(len(courses), 10)
        self.assertEqual(courses[0]["language"], "scratch")
        self.assertGreaterEqual(sum(len(course["lessons"]) for course in courses), 50)
        first_lesson = courses[0]["lessons"][0]
        for key in ["learning_goal", "example", "challenge", "hints", "success_condition"]:
            self.assertIn(key, first_lesson)

    def test_assistant_refuses_complete_solution(self):
        response, label = app.assistant_reply("Gib mir die komplette Loesung", "hello-sprite")
        self.assertEqual(label, "blocked_solution")
        self.assertIn("keinen fertigen", response)

    def test_assistant_varies_repeated_hints(self):
        first, _ = app.assistant_reply("Meine Variable geht nicht", "hello-sprite", 0)
        second, _ = app.assistant_reply("Meine Variable geht nicht", "hello-sprite", 1)
        self.assertNotEqual(first, second)
        self.assertIn("Naechster Hinweis", second)

    def test_gemini_without_key_uses_fallback_path(self):
        old_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            self.assertIsNone(app.call_gemini("Warum geht das nicht?", "hello-sprite", []))
        finally:
            if old_key:
                os.environ["GEMINI_API_KEY"] = old_key

    def test_badges_are_seeded(self):
        with app.connect(self.db_path) as db:
            count = db.execute("SELECT COUNT(*) AS c FROM badges").fetchone()["c"]
        self.assertGreaterEqual(count, 9)

    def test_course_progress_recommends_first_open_lesson(self):
        completed = {"hello-sprite"}
        progress = app.course_progress(completed)
        self.assertEqual(progress[0]["completedCount"], 1)
        self.assertEqual(app.next_lesson_after(completed)["id"], "move-sprite")

    def test_sb3_analysis_and_lesson_evaluation(self):
        project = {
            "targets": [
                {
                    "blocks": {
                        "a": {"opcode": "event_whenflagclicked", "fields": {}},
                        "b": {"opcode": "looks_sayforsecs", "fields": {}},
                    },
                    "variables": {},
                    "lists": {},
                    "broadcasts": {},
                }
            ]
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("project.json", json.dumps(project))
        analysis = app.analyze_scratch_project(buffer.getvalue())
        _, lesson = app.find_lesson("hello-sprite")
        result = app.evaluate_project_for_lesson(analysis, lesson)
        self.assertEqual(result["score"], result["total"])

    def test_pricing_constants_match_product_model(self):
        self.assertEqual(app.SINGLE_LESSON_PRICE_EUR, 5)
        self.assertEqual(app.PREMIUM_MONTHLY_PRICE_EUR, 15)


if __name__ == "__main__":
    unittest.main()
