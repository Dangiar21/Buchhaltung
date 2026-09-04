import os
import re
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QCheckBox, 
    QComboBox, QLineEdit, QPushButton, QMessageBox, QFrame, QApplication,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QInputDialog, QDialog, QSplitter, QSpinBox
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
import qtawesome as qta
import keyring

from src.core.translations import translator
from src.core.logger import setup_logger
from src.ui.theme import apply_theme
from src.ui.kontenplan_editor import KontenplanEditorDialog, parse_kontenplan

logger = logging.getLogger(__name__)


class NewTemplateDialog(QDialog):
    """Dialog zur Neuanlage einer globalen Kontenplan-Vorlage."""
    def __init__(self, parent=None, existing_templates=None):
        super().__init__(parent)
        self.existing_templates = existing_templates or []
        self.setWindowTitle("Neue Kontenplan-Vorlage anlegen")
        self.resize(450, 220)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        lbl_title = QLabel("Neue Kontenplan-Vorlage")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        lbl_title.setFont(font)
        layout.addWidget(lbl_title)
        
        form = QFormLayout()
        form.setSpacing(12)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("z.B. SKR03, Handel, Handwerk...")
        form.addRow("Vorlagenname *:", self.name_edit)
        
        self.base_combo = QComboBox()
        self.base_combo.addItem("Standard-Grundgerüst (neu)", None)
        for t in self.existing_templates:
            self.base_combo.addItem(f"Kopie von '{t}'", t)
        form.addRow("Basierend auf:", self.base_combo)
        
        layout.addLayout(form)
        
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.error_label)
        
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        
        btn_create = QPushButton("Vorlage erstellen")
        btn_create.setObjectName("PrimaryBtn")
        btn_create.setDefault(True)
        btn_create.clicked.connect(self.validate_and_accept)
        btn_box.addWidget(btn_create)
        
        layout.addLayout(btn_box)

    def validate_and_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            self.error_label.setText("Fehler: Bitte geben Sie einen Namen ein.")
            return
        
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', name).strip()
        if clean_name in self.existing_templates:
            self.error_label.setText(f"Fehler: Eine Vorlage namens '{clean_name}' existiert bereits.")
            return
            
        self.accept()

    def get_data(self):
        name = self.name_edit.text().strip()
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', name).strip()
        base = self.base_combo.currentData()
        return clean_name, base


class SettingsFrame(QWidget):
    def __init__(self, parent, config_manager, app_instance):
        super().__init__(parent)
        self.config_manager = config_manager
        self.app = app_instance
        self.controller = getattr(app_instance, "controller", None)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 25, 30, 25)
        self.main_layout.setSpacing(15)
        
        title = QLabel("Einstellungen")
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        title.setFont(font)
        self.main_layout.addWidget(title)
        
        # Tabs für Einstellungen
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # Tab 1: Allgemein
        self.tab_general = QWidget()
        self._build_general_tab()
        self.tab_widget.addTab(self.tab_general, "Allgemein")
        
        # Tab 2: Kontenplan-Vorlagen
        self.tab_templates = QWidget()
        self._build_templates_tab()
        self.tab_widget.addTab(self.tab_templates, "Globale Kontenpläne")

    # -------------------------------------------------------------
    # TAB 1: ALLGEMEIN
    # -------------------------------------------------------------
    def _build_general_tab(self):
        layout = QVBoxLayout(self.tab_general)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
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
        self.api_key_entry.setFixedWidth(320)
        
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
        except Exception as e:
            logger.error(f"Fehler beim Laden des API-Keys: {e}")
            
        lbl_api = QLabel("Gemini API Key:")
        lbl_api.setFont(QFont("", -1, QFont.Weight.Bold))
        form_layout.addRow(lbl_api, self.api_key_entry)
        
        # KI-Konfidenz (Stufe 1)
        conf_layout = QHBoxLayout()
        self.confidence_spin = QSpinBox()
        self.confidence_spin.setRange(1, 10)
        self.confidence_spin.setValue(self.config_manager.get("confidence_threshold", 8))
        self.confidence_spin.setFixedWidth(70)
        conf_layout.addWidget(self.confidence_spin)
        
        lbl_conf_hint = QLabel("Mindest-Konfidenz (1-10) für Stufe 1 (Lite-Modell). Liegt der Wert darunter, prüft Stufe 2 (Flash-Wasserfall). (Standard: 8)")
        lbl_conf_hint.setStyleSheet("color: #64748b; font-size: 9.5pt;")
        conf_layout.addWidget(lbl_conf_hint)
        conf_layout.addStretch()
        
        lbl_conf = QLabel("KI-Konfidenz (Stufe 1):")
        lbl_conf.setFont(QFont("", -1, QFont.Weight.Bold))
        form_layout.addRow(lbl_conf, conf_layout)
        
        layout.addWidget(content_frame)
        
        # Save Button
        btn_save = QPushButton("Speichern")
        btn_save.setFixedWidth(150)
        btn_save.clicked.connect(self.save_settings)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        
        layout.addLayout(btn_layout)
        layout.addStretch()

    # -------------------------------------------------------------
    # TAB 2: GLOBALE KONTENPLAN-VORLAGEN
    # -------------------------------------------------------------
    def _build_templates_tab(self):
        layout = QVBoxLayout(self.tab_templates)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Header Info
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        
        lbl_header = QLabel("Globale Kontenplan-Vorlagen verwalten")
        lbl_header.setFont(QFont("", 13, QFont.Weight.Bold))
        header_layout.addWidget(lbl_header)
        
        lbl_desc = QLabel(
            "Diese Vorlagen stehen beim Erstellen eines neuen Kunden zur Auswahl bereit.\n"
            "Bearbeiten Sie hier die Standardkonten für Eingangsrechnungen (ER) und Ausgangsrechnungen (AR)."
        )
        lbl_desc.setStyleSheet("color: #64748b; font-size: 10pt;")
        header_layout.addWidget(lbl_desc)
        
        layout.addWidget(header_widget)
        
        # Toolbar: Vorlagen-Auswahl + Aktionen
        toolbar_frame = QFrame()
        toolbar_frame.setObjectName("SettingsFrame")
        tb_layout = QHBoxLayout(toolbar_frame)
        tb_layout.setContentsMargins(12, 10, 12, 10)
        tb_layout.setSpacing(10)
        
        lbl_select = QLabel("Aktive Vorlage:")
        lbl_select.setFont(QFont("", 10, QFont.Weight.Bold))
        tb_layout.addWidget(lbl_select)
        
        self.template_combo = QComboBox()
        self.template_combo.setMinimumWidth(220)
        self.template_combo.currentIndexChanged.connect(self.on_template_selection_changed)
        tb_layout.addWidget(self.template_combo)
        
        tb_layout.addSpacing(10)
        
        # Buttons
        self.btn_new_template = QPushButton("➕ Neu")
        self.btn_new_template.setToolTip("Neue globale Vorlage anlegen")
        self.btn_new_template.clicked.connect(self.add_new_template)
        tb_layout.addWidget(self.btn_new_template)
        
        self.btn_duplicate_template = QPushButton("📋 Duplizieren")
        self.btn_duplicate_template.setToolTip("Ausgewählte Vorlage duplizieren")
        self.btn_duplicate_template.clicked.connect(self.duplicate_template)
        tb_layout.addWidget(self.btn_duplicate_template)
        
        self.btn_rename_template = QPushButton("✏️ Umbenennen")
        self.btn_rename_template.setToolTip("Ausgewählte Vorlage umbenennen")
        self.btn_rename_template.clicked.connect(self.rename_template)
        tb_layout.addWidget(self.btn_rename_template)
        
        self.btn_delete_template = QPushButton("🗑️ Löschen")
        self.btn_delete_template.setToolTip("Ausgewählte Vorlage löschen")
        self.btn_delete_template.clicked.connect(self.delete_template)
        tb_layout.addWidget(self.btn_delete_template)
        
        tb_layout.addStretch()
        layout.addWidget(toolbar_frame)
        
        # Zwei Karten für ER und AR
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(15)
        
        # Karte ER
        self.card_er, self.lbl_count_er, self.table_er, self.btn_edit_er = self._create_plan_card(
            title="Eingangsrechnungen (ER)",
            typ="ER",
            accent_color="#2e9e63"
        )
        cards_layout.addWidget(self.card_er, 1)
        
        # Karte AR
        self.card_ar, self.lbl_count_ar, self.table_ar, self.btn_edit_ar = self._create_plan_card(
            title="Ausgangsrechnungen (AR)",
            typ="AR",
            accent_color="#3a7ebf"
        )
        cards_layout.addWidget(self.card_ar, 1)
        
        layout.addLayout(cards_layout, 1)
        
        # Vorlagen laden
        self.refresh_templates()

    def _create_plan_card(self, title, typ, accent_color):
        """Erzeugt eine übersichtliche Karte für einen Vorlagen-Kontenplan (ER oder AR)."""
        card = QFrame()
        card.setObjectName("SettingsFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(15, 15, 15, 15)
        card_layout.setSpacing(10)
        
        # Header der Karte
        head_layout = QHBoxLayout()
        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("", 11, QFont.Weight.Bold))
        head_layout.addWidget(lbl_title)
        
        head_layout.addStretch()
        
        lbl_count = QLabel("0 Konten")
        lbl_count.setStyleSheet(f"color: {accent_color}; font-weight: bold; font-size: 9.5pt;")
        head_layout.addWidget(lbl_count)
        card_layout.addLayout(head_layout)
        
        # Vorschau-Tabelle
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Konto", "Bezeichnung"])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 100)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        card_layout.addWidget(table, 1)
        
        # Button zum Öffnen des Vollwertigen Kontenplan-Editors
        btn_edit = QPushButton(f"✏️ {typ}-Kontenplan bearbeiten")
        btn_edit.setMinimumHeight(34)
        btn_edit.clicked.connect(lambda: self.open_kontenplan_editor(typ))
        table.doubleClicked.connect(lambda: self.open_kontenplan_editor(typ))
        card_layout.addWidget(btn_edit)
        
        return card, lbl_count, table, btn_edit

    def refresh_templates(self, select_template_name=None):
        """Lädt alle verfügbaren Vorlagen neu in das Dropdown."""
        if not self.controller:
            return
            
        current = select_template_name or self.template_combo.currentText()
        templates = self.controller.get_available_templates()
        
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItems(templates)
        
        if current in templates:
            self.template_combo.setCurrentText(current)
        elif templates:
            self.template_combo.setCurrentIndex(0)
            
        self.template_combo.blockSignals(False)
        self.refresh_preview()

    def on_template_selection_changed(self):
        self.refresh_preview()

    def refresh_preview(self):
        """Aktualisiert die Vorschautabellen und Zählungen für die aktive Vorlage."""
        if not self.controller:
            return
            
        template_name = self.template_combo.currentText()
        if not template_name:
            self.lbl_count_er.setText("0 Konten")
            self.table_er.setRowCount(0)
            self.lbl_count_ar.setText("0 Konten")
            self.table_ar.setRowCount(0)
            return
            
        # ER laden
        er_path = self.controller.get_template_path(template_name, "ER")
        self._populate_preview_table(er_path, self.table_er, self.lbl_count_er)
        
        # AR laden
        ar_path = self.controller.get_template_path(template_name, "AR")
        self._populate_preview_table(ar_path, self.table_ar, self.lbl_count_ar)

    def _populate_preview_table(self, file_path, table_widget, label_count):
        entries = []
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                entries = parse_kontenplan(content)
            except Exception as e:
                logger.error(f"Fehler beim Laden von {file_path}: {e}")
                
        count_text = f"{len(entries)} Konto hinterlegt" if len(entries) == 1 else f"{len(entries)} Konten hinterlegt"
        label_count.setText(count_text)
        
        table_widget.setRowCount(len(entries))
        for row, item in enumerate(entries):
            k_item = QTableWidgetItem(item.get('konto', ''))
            k_item.setFont(QFont("", -1, QFont.Weight.Bold))
            n_item = QTableWidgetItem(item.get('name', ''))
            desc = item.get('beschreibung', '').strip()
            if desc:
                n_item.setToolTip(desc)
            table_widget.setItem(row, 0, k_item)
            table_widget.setItem(row, 1, n_item)

    def open_kontenplan_editor(self, typ):
        """Öffnet den vollwertigen Kontenplan-Editor für die ausgewählte globale Vorlage."""
        template_name = self.template_combo.currentText()
        if not template_name or not self.controller:
            return
            
        file_path = self.controller.get_template_path(template_name, typ)
        editor = KontenplanEditorDialog(
            parent=self,
            file_path=file_path,
            client_name=f"Vorlage '{template_name}'",
            typ=typ
        )
        editor.exec()
        # Nach dem Schließen des Editors stets Vorschau aktualisieren
        self.refresh_preview()

    def add_new_template(self):
        """Erstellt eine neue Kontenplan-Vorlage."""
        if not self.controller:
            return
            
        existing = self.controller.get_available_templates()
        dlg = NewTemplateDialog(parent=self, existing_templates=existing)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            clean_name, base_template = dlg.get_data()
            success, res = self.controller.create_template(clean_name, base_template=base_template)
            if success:
                self.refresh_templates(select_template_name=clean_name)
                QMessageBox.information(
                    self, 
                    "Vorlage erstellt", 
                    f"Die Kontenplan-Vorlage <b>'{clean_name}'</b> wurde erfolgreich angelegt.<br>"
                    "Sie können diese nun anpassen."
                )
            else:
                QMessageBox.warning(self, "Fehler", f"Konnte Vorlage nicht erstellen:\n{res}")

    def duplicate_template(self):
        """Dupliziert die aktuelle Vorlage."""
        if not self.controller:
            return
            
        cur = self.template_combo.currentText()
        if not cur:
            return
            
        new_name, ok = QInputDialog.getText(
            self, 
            "Vorlage duplizieren", 
            f"Geben Sie einen Namen für die Kopie von '{cur}' ein:",
            text=f"{cur}_Kopie"
        )
        if ok and new_name.strip():
            clean_name = re.sub(r'[<>:"/\\|?*]', '_', new_name).strip()
            success, res = self.controller.duplicate_template(cur, clean_name)
            if success:
                self.refresh_templates(select_template_name=clean_name)
                QMessageBox.information(self, "Dupliziert", f"Vorlage '{clean_name}' wurde erfolgreich erstellt.")
            else:
                QMessageBox.warning(self, "Fehler", f"Konnte Vorlage nicht duplizieren:\n{res}")

    def rename_template(self):
        """Benennt die ausgewählte Vorlage um."""
        if not self.controller:
            return
            
        cur = self.template_combo.currentText()
        if not cur:
            return
            
        new_name, ok = QInputDialog.getText(
            self, 
            "Vorlage umbenennen", 
            f"Neuer Name für die Vorlage '{cur}':",
            text=cur
        )
        if ok and new_name.strip():
            clean_name = re.sub(r'[<>:"/\\|?*]', '_', new_name).strip()
            if clean_name == cur:
                return
            success, res = self.controller.rename_template(cur, clean_name)
            if success:
                self.refresh_templates(select_template_name=clean_name)
                QMessageBox.information(self, "Umbenannt", f"Vorlage wurde in '{clean_name}' umbenannt.")
            else:
                QMessageBox.warning(self, "Fehler", f"Konnte Vorlage nicht umbenennen:\n{res}")

    def delete_template(self):
        """Löscht die ausgewählte Vorlage."""
        if not self.controller:
            return
            
        cur = self.template_combo.currentText()
        if not cur:
            return
            
        templates = self.controller.get_available_templates()
        if len(templates) <= 1:
            QMessageBox.warning(
                self, 
                "Löschen nicht möglich", 
                "Es muss mindestens eine Kontenplan-Vorlage im System verbleiben."
            )
            return
            
        reply = QMessageBox.question(
            self,
            "Vorlage löschen",
            f"Möchten Sie die Vorlage <b>'{cur}'</b> wirklich unwiderruflich löschen?<br><br>"
            "Bestehende Kunden sind davon nicht betroffen, aber die Vorlage steht bei künftigen Kundenerstellungen nicht mehr zur Verfügung.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            success, res = self.controller.delete_template(cur)
            if success:
                self.refresh_templates()
                QMessageBox.information(self, "Gelöscht", f"Vorlage '{cur}' wurde erfolgreich gelöscht.")
            else:
                QMessageBox.warning(self, "Fehler", f"Konnte Vorlage nicht löschen:\n{res}")

    # -------------------------------------------------------------
    # ALLGEMEINE AKTIONEN
    # -------------------------------------------------------------
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
            
        # KI-Konfidenz speichern
        conf_val = self.confidence_spin.value()
        self.config_manager.set("confidence_threshold", conf_val)
            
        QMessageBox.information(self, "Erfolg", "Einstellungen gespeichert!")
