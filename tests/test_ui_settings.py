import os
import sys
import unittest
import tempfile
import shutil

# Ensure workspace root is in sys.path
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from PyQt6.QtWidgets import QApplication
from src.core.config import ConfigManager
from src.core.controller import AppController
from src.ui.settings import SettingsFrame, NewTemplateDialog

# Ensure single QApplication instance
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class DummyBuchhaltungApp:
    def __init__(self, controller):
        self.lang = "DE"
        self.controller = controller
        
    def change_language(self, lang):
        self.lang = lang


class TestSettingsUI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.kunden_dir = os.path.join(self.test_dir, "Kunden")
        self.controller = AppController(self.kunden_dir)
        self.temp_templates = os.path.join(self.test_dir, "Systemdaten", "Templates")
        os.makedirs(self.temp_templates, exist_ok=True)
        self.controller.templates_dir = self.temp_templates
        
        with open(os.path.join(self.temp_templates, "ER_Codice_Civile_2424.txt"), "w", encoding="utf-8") as f:
            f.write("- Konto 0100: Anlagevermögen\n- Konto 5000: Materialaufwand\n")
        with open(os.path.join(self.temp_templates, "AR_Codice_Civile_2424.txt"), "w", encoding="utf-8") as f:
            f.write("- Konto 4000: Umsatzerlöse\n")
            
        self.config_manager = ConfigManager(config_path=os.path.join(self.test_dir, "config.json"))
        self.dummy_app = DummyBuchhaltungApp(self.controller)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_settings_frame_initialization(self):
        settings_frame = SettingsFrame(None, self.config_manager, self.dummy_app)
        self.assertIsNotNone(settings_frame)
        self.assertEqual(settings_frame.tab_widget.count(), 2)
        self.assertEqual(settings_frame.tab_widget.tabText(0), "Allgemein")
        self.assertEqual(settings_frame.tab_widget.tabText(1), "Globale Kontenpläne")
        
        # Verify template combo contains Codice_Civile_2424
        combo_items = [settings_frame.template_combo.itemText(i) for i in range(settings_frame.template_combo.count())]
        self.assertIn("Codice_Civile_2424", combo_items)
        
        # Verify ER and AR table have rows
        self.assertEqual(settings_frame.table_er.rowCount(), 2)
        self.assertEqual(settings_frame.table_ar.rowCount(), 1)
        self.assertIn("2 Konten", settings_frame.lbl_count_er.text())
        # Verify confidence threshold control
        self.assertEqual(settings_frame.confidence_spin.value(), 8)
        settings_frame.confidence_spin.setValue(9)
        from unittest.mock import patch
        with patch("src.ui.settings.QMessageBox.information"):
            settings_frame.save_settings()
        self.assertEqual(self.config_manager.get("confidence_threshold"), 9)

    def test_buchung_ki_reads_confidence_threshold(self):
        buchungen_dir = os.path.join(script_dir, "Programme", "Buchungen erstellen")
        if buchungen_dir not in sys.path:
            sys.path.append(buchungen_dir)
        import Buchung_KI
        self.assertIn(Buchung_KI.get_confidence_threshold(), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])


if __name__ == "__main__":
    unittest.main()
