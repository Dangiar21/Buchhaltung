import unittest
import sys
import os
import tempfile
import shutil

from PyQt6.QtWidgets import QApplication

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
prog_dir = os.path.join(base_dir, "Programme")
src_dir = os.path.join(base_dir, "src")
for p in [base_dir, prog_dir, src_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.ui.kontenplan_editor import KontenplanEditorDialog, parse_kontenplan, serialize_kontenplan
from DatabaseManager import DatabaseManager

app = QApplication.instance()
if not app:
    app = QApplication([])

class TestEditorSafety(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.kontenplan_file = os.path.join(self.temp_dir, "ER_Kontenplan.txt")
        with open(self.kontenplan_file, "w", encoding="utf-8") as f:
            f.write("- Konto 100 / 801001 – Wareneinkauf: Beispiele: Fleisch, Wurst\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_kontenplan_dirty_flag_and_title(self):
        """Verifies that is_dirty tracks changes and updates the window title."""
        editor = KontenplanEditorDialog(file_path=self.kontenplan_file, client_name="TestKunde", typ="ER")
        self.assertFalse(editor.is_dirty)
        self.assertNotIn("*", editor.windowTitle())

        # Set dirty
        editor.set_dirty(True)
        self.assertTrue(editor.is_dirty)
        self.assertTrue(editor.windowTitle().startswith("*"))
        self.assertIn("(ungespeichert)", editor.windowTitle())

        # Reset dirty
        editor.set_dirty(False)
        self.assertFalse(editor.is_dirty)
        self.assertFalse(editor.windowTitle().startswith("*"))

    def test_kontenplan_sort_sets_dirty(self):
        """Sorting the accounts should mark the document as dirty."""
        editor = KontenplanEditorDialog(file_path=self.kontenplan_file, client_name="TestKunde", typ="ER")
        self.assertFalse(editor.is_dirty)

        editor.entries.append({"konto": "100 / 801000", "name": "A-Konto", "beschreibung": ""})
        editor.sort_by_konto()
        self.assertTrue(editor.is_dirty)

    def test_kontenplan_save_resets_dirty(self):
        """save_and_close should persist changes and reset is_dirty to False."""
        editor = KontenplanEditorDialog(file_path=self.kontenplan_file, client_name="TestKunde", typ="ER")
        editor.entries.append({"konto": "100 / 801002", "name": "Diesel LKW", "beschreibung": "Treibstoff"})
        editor.set_dirty(True)
        self.assertTrue(editor.is_dirty)

        success = editor.save_and_close()
        self.assertTrue(success)
        self.assertFalse(editor.is_dirty)

        # Check file content on disk
        with open(self.kontenplan_file, "r", encoding="utf-8") as f:
            saved_content = f.read()
        self.assertIn("801002", saved_content)
        self.assertIn("Diesel LKW", saved_content)

    def test_cache_database_auto_save(self):
        """Verify that db.save_konten_cache_batch persists entries immediately."""
        db_file = os.path.join(self.temp_dir, "test_cache.db")
        db = DatabaseManager(db_file)

        client = "TestKunde"
        new_entry = {
            "ENI | DIESEL [KONTEXT: LKW]": {"value": "810005", "confirmed": True}
        }
        db.save_konten_cache_batch(client, new_entry)

        cache = db.get_konten_cache(client)
        self.assertIn("ENI | DIESEL [KONTEXT: LKW]", cache)
        self.assertEqual(cache["ENI | DIESEL [KONTEXT: LKW]"], "810005")

        cache_full = db.get_konten_cache_full(client)
        self.assertTrue(cache_full["ENI | DIESEL [KONTEXT: LKW]"]["confirmed"])

if __name__ == "__main__":
    unittest.main()
