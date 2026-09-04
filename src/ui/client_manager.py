import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, 
    QLineEdit, QComboBox, QTextEdit, QPushButton, QTabWidget, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class ClientManager:
    def __init__(self, parent, controller, config_manager, on_client_selected):
        self.parent = parent
        self.controller = controller
        self.config_manager = config_manager
        self.on_client_selected = on_client_selected
        
        self.all_clients = []
        self.current_client = None

    def open_new_client_dialog(self, edit_client_name=None):
        is_edit = edit_client_name is not None
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Kunde bearbeiten" if is_edit else "Neuer Kunde")
        dialog.resize(550, 650)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_title = QLabel(f"Kunde '{edit_client_name}' bearbeiten" if is_edit else "Neuen Kunden anlegen")
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        lbl_title.setFont(font)
        layout.addWidget(lbl_title)
        
        tabview = QTabWidget()
        layout.addWidget(tabview)
        
        # --- Tab 1: Basis & KI ---
        tab1 = QWidget()
        form1 = QFormLayout(tab1)
        form1.setContentsMargins(20, 20, 20, 20)
        
        name_entry = QLineEdit()
        form1.addRow("Firmenname (Ordnername) *", name_entry)
        
        forma_combo = QComboBox()
        forma_combo.addItems(["Srl", "SpA", "snc", "sas", "Ditta Individuale", "Libero Professionista", "Altro"])
        forma_combo.setCurrentText("Srl")
        form1.addRow("Rechtsform", forma_combo)
        
        template_combo = QComboBox()
        if not is_edit:
            template_combo.addItems(["Codice_Civile_2424", "Standard"])
            template_combo.setCurrentText("Codice_Civile_2424")
            form1.addRow("Kontenplan Vorlage (ER & AR)", template_combo)
        else:
            def open_editor(typ, title):
                editor = QDialog(dialog)
                editor.setWindowTitle(f"{title}: {edit_client_name}")
                editor.resize(600, 500)
                editor.setWindowModality(Qt.WindowModality.ApplicationModal)
                ed_layout = QVBoxLayout(editor)
                
                txt = QTextEdit()
                ed_layout.addWidget(txt)
                
                file_path = os.path.join(self.controller.base_kunden_dir, edit_client_name, "Nutzerdaten", f"{typ}_Kontenplan.txt")
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        txt.setPlainText(f.read())
                        
                def save_txt():
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(txt.toPlainText())
                    editor.accept()
                    
                btn_s = QPushButton("Speichern")
                btn_s.clicked.connect(save_txt)
                ed_layout.addWidget(btn_s)
                editor.exec()

            btn_layout = QHBoxLayout()
            btn_edit_er = QPushButton("ER-Kontenplan bearbeiten")
            btn_edit_er.clicked.connect(lambda: open_editor("ER", "ER-Kontenplan"))
            btn_layout.addWidget(btn_edit_er)
            
            btn_edit_ar = QPushButton("AR-Kontenplan bearbeiten")
            btn_edit_ar.clicked.connect(lambda: open_editor("AR", "AR-Kontenplan"))
            btn_layout.addWidget(btn_edit_ar)
            
            form1.addRow("", btn_layout)

        desc_text = QTextEdit()
        desc_text.setFixedHeight(150)
        form1.addRow("Beschreibung\n(Wichtig für KI)", desc_text)
        
        tabview.addTab(tab1, "Basis & KI")
        
        # --- Tab 2: Steuerdaten ---
        tab2 = QWidget()
        form2 = QFormLayout(tab2)
        form2.setContentsMargins(20, 20, 20, 20)
        
        piva_entry = QLineEdit()
        form2.addRow("Partita IVA (MwSt.-Nummer) *", piva_entry)
        
        cf_entry = QLineEdit()
        form2.addRow("Codice Fiscale", cf_entry)
        
        tabview.addTab(tab2, "Steuerdaten")
        
        # --- Tab 3: Buchhaltung ---
        tab3 = QWidget()
        form3 = QFormLayout(tab3)
        form3.setContentsMargins(20, 20, 20, 20)
        
        regime_combo = QComboBox()
        regime_combo.addItems(["Ordinaria", "Semplificata", "Forfettario"])
        regime_combo.setCurrentText("Ordinaria")
        form3.addRow("Regime Contabile", regime_combo)
        
        liq_combo = QComboBox()
        liq_combo.addItems(["Mensile", "Trimestrale"])
        liq_combo.setCurrentText("Mensile")
        form3.addRow("Liquidazione IVA", liq_combo)
        
        tabview.addTab(tab3, "Buchhaltung")
        
        # --- Tab 4: Kontakt ---
        tab4 = QWidget()
        form4 = QFormLayout(tab4)
        form4.setContentsMargins(20, 20, 20, 20)
        
        addr_entry = QLineEdit()
        form4.addRow("Adresse (Sede Legale)", addr_entry)
        
        pec_entry = QLineEdit()
        form4.addRow("PEC", pec_entry)
        
        sdi_entry = QLineEdit()
        form4.addRow("Codice Destinatario (SDI)", sdi_entry)
        
        iban_entry = QLineEdit()
        form4.addRow("IBAN", iban_entry)
        
        tabview.addTab(tab4, "Kontakt")
        
        if is_edit:
            name_entry.setText(edit_client_name)
            name_entry.setEnabled(False)
            
            data = self.controller.get_client_data(edit_client_name)
            if data:
                if "Rechtsform" in data and data["Rechtsform"]: forma_combo.setCurrentText(data["Rechtsform"])
                if "Beschreibung" in data and data["Beschreibung"]: desc_text.setPlainText(data["Beschreibung"])
                if "Partita_IVA" in data and data["Partita_IVA"]: piva_entry.setText(data["Partita_IVA"])
                if "Codice_Fiscale" in data and data["Codice_Fiscale"]: cf_entry.setText(data["Codice_Fiscale"])
                if "Regime_Contabile" in data and data["Regime_Contabile"]: regime_combo.setCurrentText(data["Regime_Contabile"])
                if "Liquidazione_IVA" in data and data["Liquidazione_IVA"]: liq_combo.setCurrentText(data["Liquidazione_IVA"])
                if "Adresse" in data and data["Adresse"]: addr_entry.setText(data["Adresse"])
                if "PEC" in data and data["PEC"]: pec_entry.setText(data["PEC"])
                if "SDI" in data and data["SDI"]: sdi_entry.setText(data["SDI"])
                if "IBAN" in data and data["IBAN"]: iban_entry.setText(data["IBAN"])
        
        error_label = QLabel("")
        error_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(error_label)

        def save_client():
            error_label.setText("")
            name_raw = name_entry.text().strip()
            if not name_raw:
                error_label.setText("Fehler: Firmenname darf nicht leer sein!")
                return
                
            client_data = {
                "Kundenname": name_raw,
                "Rechtsform": forma_combo.currentText(),
                "Beschreibung": desc_text.toPlainText().strip(),
                "Partita_IVA": piva_entry.text().strip(),
                "Codice_Fiscale": cf_entry.text().strip(),
                "Regime_Contabile": regime_combo.currentText(),
                "Liquidazione_IVA": liq_combo.currentText(),
                "Adresse": addr_entry.text().strip(),
                "PEC": pec_entry.text().strip(),
                "SDI": sdi_entry.text().strip(),
                "IBAN": iban_entry.text().strip()
            }
            template_name = template_combo.currentText() if not is_edit else None
            
            success, final_name = self.controller.save_client(name_raw, is_edit, client_data, template_name)
            if success:
                self.on_client_selected(final_name)
                dialog.accept()
            else:
                error_label.setText(f"Fehler: {final_name}")

        btn_save = QPushButton("Speichern")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setMinimumHeight(40)
        btn_save.clicked.connect(save_client)
        layout.addWidget(btn_save)
        
        dialog.exec()
