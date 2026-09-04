import os
import sys
import unittest
import tempfile
import pandas as pd

# Add project root to sys.path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from src.core.kontenplan_learner import (
    parse_booking_excel,
    extract_existing_examples_from_desc,
    merge_examples_into_desc,
    apply_confirmed_terms_to_kontenplan
)

class TestKontenplanLearner(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        
    def tearDown(self):
        self.test_dir.cleanup()

    def test_extract_and_merge_examples(self):
        desc = "(Z. B. Vakuumsäcke, Garn)"
        existing = extract_existing_examples_from_desc(desc)
        self.assertEqual(existing, ["Vakuumsäcke", "Garn"])

        # Test merge with new terms and deduplication
        new_terms = ["garn", "Klebefolien", "Verpackungskarton"]
        merged = merge_examples_into_desc(desc, new_terms, max_limit=20)
        self.assertIn("(Z. B. Vakuumsäcke, Garn, Klebefolien, Verpackungskarton)", merged)

        # Test max limit enforcement (e.g. max 4)
        merged_limited = merge_examples_into_desc(desc, new_terms, max_limit=3)
        self.assertEqual(merged_limited, "(Z. B. Vakuumsäcke, Garn, Klebefolien)")

    def test_parse_booking_excel(self):
        # Create a sample excel file
        data = {
            "Lieferant": ["Bürodiscount", "Bürodiscount", "Würth", "Unbekannt"],
            "Beschreibung": ["Druckerpapier A4 80g", "Druckerpapier A4 80g", "Torx Schrauben 4x40", "Sonderposten"],
            "Unterkonto": ["104 / 821001", "104 / 821001", "104 / 801015", "???"],
            "Aktiv/Passiv": ["Passiva", "Passiva", "Passiva", "Passiva"]
        }
        df = pd.DataFrame(data)
        excel_path = os.path.join(self.test_dir.name, "test_buchungen.xlsx")
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Eingangsrechnungen", index=False)

        res = parse_booking_excel(excel_path, target_typ="ER")
        self.assertEqual(res["sheet_name"], "Eingangsrechnungen")
        items_by_konto = res["items_by_konto"]
        
        # Check that '???' was ignored
        self.assertNotIn("???", items_by_konto)
        # Check that 104 / 821001 was grouped and deduplicated (2 identical rows -> 1 item)
        self.assertIn("104 / 821001", items_by_konto)
        self.assertEqual(len(items_by_konto["104 / 821001"]), 1)
        self.assertIn("104 / 801015", items_by_konto)
        self.assertEqual(len(items_by_konto["104 / 801015"]), 1)

    def test_apply_confirmed_terms_to_kontenplan(self):
        kontenplan_path = os.path.join(self.test_dir.name, "ER_Kontenplan.txt")
        initial_content = (
            "104 / 801015 - Verbrauchsmaterial\n"
            "(Z. B. Vakuumsäcke, Garn)\n\n"
            "104 / 821001 – Büromaterial\n"
            "(Z. B. Druckerpapier)\n"
        )
        with open(kontenplan_path, "w", encoding="utf-8") as f:
            f.write(initial_content)

        updates = {
            "104 / 801015": {
                "name": "Verbrauchsmaterial",
                "terms": ["Klebefolie", "Kartonagen"],
                "is_new": False
            },
            "104 / 999999": {
                "name": "Neues Spezialkonto",
                "terms": ["Spezialwerkzeug"],
                "is_new": True
            }
        }

        success, msg, count = apply_confirmed_terms_to_kontenplan(
            kontenplan_path, updates, max_limit=20
        )
        self.assertTrue(success)
        self.assertEqual(count, 2)

        # Verify file content
        with open(kontenplan_path, "r", encoding="utf-8") as f:
            new_content = f.read()

        self.assertIn("Klebefolie", new_content)
        self.assertIn("Kartonagen", new_content)
        self.assertIn("Vakuumsäcke", new_content) # preserved!
        self.assertIn("104 / 999999 – Neues Spezialkonto", new_content)
        self.assertIn("(Z. B. Spezialwerkzeug)", new_content)

        # Verify backup creation
        backups = [f for f in os.listdir(self.test_dir.name) if "backup" in f]
        self.assertEqual(len(backups), 1)

    def test_ui_import(self):
        # Verify that KontenplanLearnerDialog imports without errors
        from src.ui.kontenplan_learner_dialog import KontenplanLearnerDialog
        self.assertTrue(callable(KontenplanLearnerDialog))


if __name__ == "__main__":
    unittest.main()
