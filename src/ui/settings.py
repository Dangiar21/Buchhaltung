import os
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QCheckBox, 
    QComboBox, QLineEdit, QPushButton, QMessageBox, QFrame, QApplication
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
import keyring

from src.core.translations import translator
from src.core.logger import setup_logger
from src.ui.theme import apply_theme

logger = logging.getLogger(__name__)

class SettingsFrame(QWidget):
    def __init__(self, parent, config_manager, app_instance):
        super().__init__(parent)
        self.config_manager = config_manager
        self.app = app_instance
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)
        
        title = QLabel("Einstellungen")
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        title.setFont(font)
        self.main_layout.addWidget(title)
        
        content_frame = QFrame()
        content_frame.setObjectName("SettingsFrame")
        
        form_layout = QFormLayout(content_frame)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(20)
        
        # Appearance Mode
        self.settings_mode_switch = QCheckBox(translator.get(self.app.lang, 'switch_dark'))
        if self.config_manager.get("appearance_mode", "Light") == "Dark":
            self.settings_mode_switch.setChecked(True)
        self.settings_mode_switch.toggled.connect(self.toggle_appearance_mode)
        
        lbl_appearance = QLabel("Erscheinungsbild:")
        lbl_appearance.setFont(QFont("", -1, QFont.Weight.Bold))
        form_layout.addRow(lbl_appearance, self.settings_mode_switch)
        
        # Language
        self.settings_lang = QComboBox()
        self.settings_lang.addItems(["DE", "IT"])
        self.settings_lang.setCurrentText(self.config_manager.get("language", "DE"))
        self.settings_lang.currentTextChanged.connect(self.app.change_language)
        
        lbl_lang = QLabel("Sprache:")
        lbl_lang.setFont(QFont("", -1, QFont.Weight.Bold))
        form_layout.addRow(lbl_lang, self.settings_lang)
        
        # API Key
        self.api_key_entry = QLineEdit()
        self.api_key_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_entry.setFixedWidth(300)
        
        try:
            saved_key = keyring.get_password("BuchhaltungApp", "GeminiAPI")
            if saved_key:
                self.api_key_entry.setText(saved_key)
            else:
                # Fallback: check old .env file and migrate if present
                env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Systemdaten", "gemini_key.env")
                if os.path.exists(env_path):
                    with open(env_path, "r", encoding="utf-8") as f:
                        content_key = f.read().strip()
                        if content_key.startswith("GEMINI_API_KEY="):
                            content_key = content_key.split("=", 1)[1].strip('"').strip("'")
                            self.api_key_entry.setText(content_key)
                            keyring.set_password("BuchhaltungApp", "GeminiAPI", content_key)
                            # optional: os.remove(env_path) to secure it
        except Exception as e:
            logger.error(f"Fehler beim Laden des API-Keys: {e}")
            
        lbl_api = QLabel("Gemini API Key:")
        lbl_api.setFont(QFont("", -1, QFont.Weight.Bold))
        form_layout.addRow(lbl_api, self.api_key_entry)
        
        self.main_layout.addWidget(content_frame)
        
        # Save Button
        btn_save = QPushButton("Speichern")
        btn_save.setFixedWidth(150)
        btn_save.clicked.connect(self.save_settings)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        
        self.main_layout.addLayout(btn_layout)
        self.main_layout.addStretch()
        
    def toggle_appearance_mode(self, checked):
        new_mode = "Dark" if checked else "Light"
        self.config_manager.set("appearance_mode", new_mode)
        apply_theme(QApplication.instance(), new_mode)
        
    def update_ui_text(self, lang):
        self.settings_mode_switch.setText(translator.get(lang, 'switch_dark'))

    def save_settings(self):
        key_val = self.api_key_entry.text().strip()
        try:
            if key_val:
                keyring.set_password("BuchhaltungApp", "GeminiAPI", key_val)
            else:
                try:
                    keyring.delete_password("BuchhaltungApp", "GeminiAPI")
                except keyring.errors.PasswordDeleteError:
                    pass
        except Exception as e:
            logger.error(f"Fehler beim Speichern des API-Keys: {e}")
            
        QMessageBox.information(self, "Erfolg", "Einstellungen gespeichert!")
