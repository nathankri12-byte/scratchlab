import os
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
        self.assertGreaterEqual(len(courses), 1)
        self.assertEqual(courses[0]["language"], "scratch")
        self.assertGreaterEqual(len(courses[0]["lessons"]), 3)

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
        self.assertGreaterEqual(count, 3)


if __name__ == "__main__":
    unittest.main()
