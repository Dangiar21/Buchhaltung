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

    def test_parse_booking_excel_datev_style(self):
        # Test DATEV / BMD style column names: Sachkonto and Buchungstext
        data = {
            "Geschäftspartner": ["Bürodiscount", "Würth"],
            "Buchungstext": ["Kopierpapier A4", "Bohrer Set"],
            "Sachkonto": ["840001", "840002"]
        }
        df = pd.DataFrame(data)
        excel_path = os.path.join(self.test_dir.name, "test_datev.xlsx")
        df.to_excel(excel_path, sheet_name="Journal", index=False)

        res = parse_booking_excel(excel_path)
        self.assertEqual(res["col_konto"], "Sachkonto")
        self.assertEqual(res["col_desc"], "Buchungstext")
        self.assertIn("840001", res["items_by_konto"])
        self.assertEqual(res["items_by_konto"]["840001"][0]["beschreibung"], "Kopierpapier A4")

    def test_parse_booking_excel_italian_style(self):
        # Test Italian column names: Codice Conto and Causale
        data = {
            "Fornitore": ["Fornitore Alfa", "Fornitore Beta"],
            "Causale": ["Materiale di consumo", "Consulenza tecnica"],
            "Codice Conto": ["conto_101", "conto_202"]
        }
        df = pd.DataFrame(data)
        excel_path = os.path.join(self.test_dir.name, "test_italian.xlsx")
        df.to_excel(excel_path, sheet_name="Prima_Nota", index=False)

        res = parse_booking_excel(excel_path)
        self.assertEqual(res["col_konto"], "Codice Conto")
        self.assertEqual(res["col_desc"], "Causale")
        self.assertIn("conto_101", res["items_by_konto"])

    def test_parse_booking_excel_offset_header_row(self):
        # Test file with title and metadata in the first 2 rows, header on row 3 (index 2)
        raw_rows = [
            ["Buchungsjournal Export - Firma Muster", None, None],
            ["Filter: Zeitraum 01.01.2025 - 31.12.2025", None, None],
            ["Konto-Nr.", "Verwendungszweck", "Partner"],
            ["7001", "Transportkosten LKW", "Spedition Express"],
            ["7002", "Benzinquittung", "Eni Tankstelle"]
        ]
        df = pd.DataFrame(raw_rows)
        excel_path = os.path.join(self.test_dir.name, "test_offset_header.xlsx")
        df.to_excel(excel_path, sheet_name="Export", index=False, header=False)

        res = parse_booking_excel(excel_path)
        self.assertEqual(res["header_row"], 2)
        self.assertIn("7001", res["items_by_konto"])
        self.assertEqual(res["items_by_konto"]["7001"][0]["beschreibung"], "Transportkosten LKW")

    def test_parse_booking_excel_explicit_columns(self):
        # Test explicit column mapping for non-standard column names
        data = {
            "Col_A": ["K123", "K456"],
            "Col_B": ["Text für K123", "Text für K456"],
            "Col_C": ["Lieferant 1", "Lieferant 2"]
        }
        df = pd.DataFrame(data)
        excel_path = os.path.join(self.test_dir.name, "test_custom_cols.xlsx")
        df.to_excel(excel_path, sheet_name="Tabelle1", index=False)

        res = parse_booking_excel(
            excel_path,
            selected_sheet="Tabelle1",
            col_konto="Col_A",
            col_desc="Col_B",
            col_supplier="Col_C"
        )
        self.assertIn("K123", res["items_by_konto"])
        self.assertEqual(res["items_by_konto"]["K123"][0]["beschreibung"], "Text für K123")

    def test_parse_booking_excel_unbooked_file_diagnostic(self):
        # Test helpful error message when an unbooked file (like Gesammelte_XML_Daten.xlsx) is loaded
        data = {
            "Rechnungsnummer": ["RE-001", "RE-002"],
            "Lieferant": ["Lieferant A", "Lieferant B"],
            "Beschreibung": ["Position 1", "Position 2"],
            "Betrag": [100.0, 200.0]
        }
        df = pd.DataFrame(data)
        excel_path = os.path.join(self.test_dir.name, "Gesammelte_XML_Daten.xlsx")
        df.to_excel(excel_path, sheet_name="Eingangsrechnungen", index=False)

        with self.assertRaises(ValueError) as ctx:
            parse_booking_excel(excel_path)
        self.assertIn("Gesammelte_XML_Daten.xlsx", str(ctx.exception))
        self.assertIn("Gesammelte_Buchungen.xlsx", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

