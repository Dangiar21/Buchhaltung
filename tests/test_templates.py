import os
import sys
import unittest
import tempfile
import shutil

# Ensure workspace root is in sys.path
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from src.core.controller import AppController
from src.ui.kontenplan_editor import parse_kontenplan, serialize_kontenplan


class TestTemplateManagement(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.kunden_dir = os.path.join(self.test_dir, "Kunden")
        self.controller = AppController(self.kunden_dir)
        # Point templates_dir to a temporary test folder
        self.temp_templates = os.path.join(self.test_dir, "Systemdaten", "Templates")
        os.makedirs(self.temp_templates, exist_ok=True)
        self.controller.templates_dir = self.temp_templates
        
        # Create initial test template files
        with open(os.path.join(self.temp_templates, "ER_Standard.txt"), "w", encoding="utf-8") as f:
            f.write("- Konto 5000: Wareneinkauf\n- Konto 7000: Dienstleistungen\n")
        with open(os.path.join(self.temp_templates, "AR_Standard.txt"), "w", encoding="utf-8") as f:
            f.write("- Konto 4000: Umsatzerlöse\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_available_templates(self):
        templates = self.controller.get_available_templates()
        self.assertIn("Standard", templates)

    def test_create_template_and_duplicate(self):
        # Create new template
        success, name = self.controller.create_template("Handel", base_template="Standard")
        self.assertTrue(success)
        self.assertEqual(name, "Handel")
        
        # Verify files exist
        er_path = self.controller.get_template_path("Handel", "ER")
        ar_path = self.controller.get_template_path("Handel", "AR")
        self.assertTrue(os.path.exists(er_path))
        self.assertTrue(os.path.exists(ar_path))
        
        # Verify content copied from Standard
        with open(er_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("5000", content)
        self.assertIn("Wareneinkauf", content)
        
        # Duplicate
        dup_success, dup_name = self.controller.duplicate_template("Handel", "Handel_Kopie")
        self.assertTrue(dup_success)
        self.assertIn("Handel_Kopie", self.controller.get_available_templates())

    def test_rename_template(self):
        self.controller.create_template("AltName")
        self.assertIn("AltName", self.controller.get_available_templates())
        
        success, new_name = self.controller.rename_template("AltName", "NeuName")
        self.assertTrue(success)
        templates = self.controller.get_available_templates()
        self.assertIn("NeuName", templates)
        self.assertNotIn("AltName", templates)

    def test_delete_template(self):
        self.controller.create_template("ToDelete")
        self.assertIn("ToDelete", self.controller.get_available_templates())
        
        # Delete
        success, _ = self.controller.delete_template("ToDelete")
        self.assertTrue(success)
        self.assertNotIn("ToDelete", self.controller.get_available_templates())
        
        # Try deleting the last template (Standard)
        fail_success, _ = self.controller.delete_template("Standard")
        self.assertFalse(fail_success)

    def test_parse_and_serialize_kontenplan(self):
        sample = "- Konto 1000: Kasse\n- Konto 1200: Bank\n"
        entries = parse_kontenplan(sample)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]['konto'], "1000")
        self.assertEqual(entries[0]['name'], "Kasse")
        
        serialized = serialize_kontenplan(entries)
        self.assertIn("1000", serialized)
        self.assertIn("Kasse", serialized)
        self.assertIn("1200", serialized)
        self.assertIn("Bank", serialized)


    def test_client_creation_with_template(self):
        self.controller.create_template("CustomTemplate", base_template="Standard")
        client_data = {
            "Kundenname": "Test GmbH",
            "Partita_IVA": "12345678901",
            "Rechtsform": "Srl"
        }
        success, final_name = self.controller.save_client("Test GmbH", False, client_data, "CustomTemplate")
        self.assertTrue(success)
        
        # Verify client directory & Nutzerdaten
        er_target = os.path.join(self.kunden_dir, "Test GmbH", "Nutzerdaten", "ER_Kontenplan.txt")
        ar_target = os.path.join(self.kunden_dir, "Test GmbH", "Nutzerdaten", "AR_Kontenplan.txt")
        self.assertTrue(os.path.exists(er_target))
        self.assertTrue(os.path.exists(ar_target))
        
        with open(er_target, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Wareneinkauf", content)


if __name__ == "__main__":
    unittest.main()
