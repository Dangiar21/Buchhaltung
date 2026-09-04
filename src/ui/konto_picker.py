import os
import re
from typing import List, Dict, Tuple, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.ui.kontenplan_editor import parse_kontenplan, serialize_kontenplan, KontoDetailDialog, account_sort_key


def get_base_dir() -> str:
    # src/ui/konto_picker.py -> src/ui -> src -> root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_client_kontenplan_entries(client_name: str, typ: str = "ER", base_dir: Optional[str] = None) -> Tuple[str, List[Dict[str, str]]]:
    """
    Lädt die Kontenplan-Einträge für einen Kunden.
    Gibt (file_path, entries) zurück.
    """
    if not base_dir:
        base_dir = get_base_dir()
        
    file_path = os.path.join(base_dir, "Kunden", client_name, "Nutzerdaten", f"{typ}_Kontenplan.txt")
    entries = []
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            entries = parse_kontenplan(content)
        except Exception:
            entries = []
    return file_path, entries


def get_konto_display_map(client_name: str, base_dir: Optional[str] = None) -> Dict[str, str]:
    """
    Erzeugt ein Mapping {konto_code: 'konto – name'} für ER und AR Konten eines Kunden.
    Erlaubt schnelles Nachschlagen und Anreichern von Konten.
    """
    if not client_name:
        return {}
        
    if not base_dir:
        base_dir = get_base_dir()
        
    display_map = {}
    
    # ER und AR laden
    for typ in ("ER", "AR"):
        _, entries = load_client_kontenplan_entries(client_name, typ=typ, base_dir=base_dir)
        for e in entries:
            k = e.get('konto', '').strip()
            name = e.get('name', '').strip()
            if k:
                full_val = f"{k} – {name}" if name else k
                display_map[k.upper()] = full_val
                # Auch Varianten ohne Leerzeichen mappen (z.B. "104/810001")
                k_compact = k.replace(" ", "").upper()
                display_map[k_compact] = full_val
                # Auch reines Unterkonto mappen falls "104 / 810001"
                if "/" in k:
                    sub = k.split("/", 1)[1].strip().upper()
                    if sub and sub not in display_map:
                        display_map[sub] = full_val
                        
    return display_map


def format_konto_with_name(konto_val: str, display_map: Dict[str, str]) -> str:
    """
    Stellt sicher, dass ein Konto-String immer als 'Kontonummer – Bezeichnung' formatiert ist.
    Falls bereits eine Bezeichnung enthalten ist, wird sie beibehalten.
    """
    if not konto_val:
        return ""
        
    raw = str(konto_val).strip()
    if not raw or raw in ("???", "nan", "None"):
        return raw
        
    # Falls bereits ein Gedankenstrich mit Text enthalten ist:
    # z. B. "100 / 801001 – Materialeinkauf"
    if " – " in raw or " - " in raw:
        # Schon voll formatiert
        return raw.replace(" - ", " – ")
        
    raw_upper = raw.upper()
    if raw_upper in display_map:
        return display_map[raw_upper]
        
    raw_compact = raw_upper.replace(" ", "")
    if raw_compact in display_map:
        return display_map[raw_compact]
        
    # Falls Suffix wie "_Kalb" enthalten ist: z.B. "100 / 801006_Kalb"
    if "_" in raw:
        base_part, suffix = raw.split("_", 1)
        base_clean = base_part.strip().upper()
        if base_clean in display_map:
            full_base = display_map[base_clean]
            if " – " in full_base:
                k_num, k_name = full_base.split(" – ", 1)
                return f"{k_num}_{suffix} – {k_name}"
            return f"{full_base}_{suffix}"
            
    return raw


class KontoPickerDialog(QDialog):
    """
    Durchsuchbarer Konten-Auswahldialog für den Cache-Editor.
    Ermöglicht das Auswählen bestehender Konten und das Erstellen neuer Konten direkt im Kunden-Kontenplan.
    """
    def __init__(self, parent=None, client_name: str = "", current_konto: str = "", typ: str = "ER"):
        super().__init__(parent)
        self.client_name = client_name
        self.current_konto = current_konto.strip()
        self.current_typ = typ
        self.base_dir = get_base_dir()
        
        self.selected_konto_str = self.current_konto
        
        self.setWindowTitle(f"Konto auswählen: {client_name}")
        self.resize(850, 560)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        self.er_path, self.er_entries = load_client_kontenplan_entries(client_name, "ER", self.base_dir)
        self.ar_path, self.ar_entries = load_client_kontenplan_entries(client_name, "AR", self.base_dir)
        
        self.init_ui()
        self.load_entries_for_view()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        
        # Obere Leiste: Suche & Typ-Umschalter
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)
        
        lbl_icon = QLabel("🔍")
        lbl_icon.setStyleSheet("font-size: 15px;")
        top_bar.addWidget(lbl_icon)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Konto, Bezeichnung oder Beispiele durchsuchen...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self.filter_table)
        top_bar.addWidget(self.search_edit, stretch=1)
        
        # Radio-Buttons ER / AR / Alle
        self.btn_group = QButtonGroup(self)
        self.rb_er = QRadioButton("Eingang (ER)")
        self.rb_ar = QRadioButton("Ausgang (AR)")
        self.rb_all = QRadioButton("Alle")
        
        if self.current_typ == "AR":
            self.rb_ar.setChecked(True)
        elif self.current_typ == "BEIDE":
            self.rb_all.setChecked(True)
        else:
            self.rb_er.setChecked(True)
            
        self.btn_group.addButton(self.rb_er)
        self.btn_group.addButton(self.rb_ar)
        self.btn_group.addButton(self.rb_all)
        
        self.rb_er.toggled.connect(self.load_entries_for_view)
        self.rb_ar.toggled.connect(self.load_entries_for_view)
        self.rb_all.toggled.connect(self.load_entries_for_view)
        
        top_bar.addWidget(self.rb_er)
        top_bar.addWidget(self.rb_ar)
        top_bar.addWidget(self.rb_all)
        
        layout.addLayout(top_bar)
        
        # Tabelle
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Konto", "Bezeichnung", "Notizen / Beispiele (für KI)"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.accept_selection)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 140)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(1, 240)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.table, stretch=1)
        
        # Untere Leiste: Neuerstellung & Aktionsbuttons
        bottom_bar = QHBoxLayout()
        
        btn_add = QPushButton("➕ Neues Konto im Kontenplan anlegen")
        btn_add.setFixedHeight(34)
        btn_add.clicked.connect(self.add_new_konto_to_kontenplan)
        bottom_bar.addWidget(btn_add)
        
        bottom_bar.addStretch()
        
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.setFixedHeight(34)
        btn_cancel.setFixedWidth(110)
        btn_cancel.clicked.connect(self.reject)
        bottom_bar.addWidget(btn_cancel)
        
        btn_select = QPushButton("Auswählen")
        btn_select.setDefault(True)
        btn_select.setFixedHeight(34)
        btn_select.setFixedWidth(120)
        btn_select.clicked.connect(self.accept_selection)
        bottom_bar.addWidget(btn_select)
        
        layout.addLayout(bottom_bar)

    def load_entries_for_view(self):
        """Lädt die Einträge entsprechend dem ausgewählten Radio-Button (ER/AR/Alle)."""
        if self.rb_er.isChecked():
            self.active_entries = list(self.er_entries)
            self.active_file_path = self.er_path
        elif self.rb_ar.isChecked():
            self.active_entries = list(self.ar_entries)
            self.active_file_path = self.ar_path
        else:
            # Kombiniert
            seen_konten = set()
            combined = []
            for e in self.er_entries + self.ar_entries:
                k = e.get('konto', '').strip().upper()
                if k not in seen_konten:
                    seen_konten.add(k)
                    combined.append(e)
            self.active_entries = combined
            self.active_file_path = self.er_path
            
        self.active_entries.sort(key=account_sort_key)
        self.populate_table()

    def populate_table(self):
        self.table.setRowCount(len(self.active_entries))
        current_upper = self.current_konto.upper().strip()
        matched_row = -1
        
        for row, item in enumerate(self.active_entries):
            konto_str = item.get('konto', '').strip()
            name_str = item.get('name', '').strip()
            desc_str = item.get('beschreibung', '').strip().replace('\n', ' ')
            
            k_item = QTableWidgetItem(konto_str)
            k_item.setFont(QFont("", -1, QFont.Weight.Bold))
            k_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            
            n_item = QTableWidgetItem(name_str)
            n_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            
            d_item = QTableWidgetItem(desc_str)
            d_item.setToolTip(item.get('beschreibung', ''))
            d_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            
            self.table.setItem(row, 0, k_item)
            self.table.setItem(row, 1, n_item)
            self.table.setItem(row, 2, d_item)
            
            # Prüfen ob aktuelle Auswahl
            full_val = f"{konto_str} – {name_str}".upper()
            if current_upper and (current_upper == konto_str.upper() or current_upper == full_val or current_upper.startswith(konto_str.upper() + " –")):
                matched_row = row
                
        self.filter_table()
        if matched_row >= 0:
            self.table.selectRow(matched_row)
            self.table.scrollToItem(self.table.item(matched_row, 0))

    def filter_table(self):
        query = self.search_edit.text().strip().upper()
        for row in range(self.table.rowCount()):
            k = self.table.item(row, 0).text().upper() if self.table.item(row, 0) else ""
            n = self.table.item(row, 1).text().upper() if self.table.item(row, 1) else ""
            d = self.table.item(row, 2).text().upper() if self.table.item(row, 2) else ""
            
            match = (not query) or (query in k) or (query in n) or (query in d)
            self.table.setRowHidden(row, not match)

    def add_new_konto_to_kontenplan(self):
        """Erlaubt das Anlegen eines neuen Kontos direkt aus dem Picker heraus."""
        existing = {e['konto'].strip().upper() for e in self.active_entries}
        dlg = KontoDetailDialog(self, existing_konten=existing, is_edit=False)
        if dlg.exec():
            data = dlg.get_data()
            k = data['konto']
            n = data['name']
            
            # Speichere persistent in der aktiven Kontenplan-Datei
            target_path = self.active_file_path
            # Neu einlesen um sicherzugehen
            _, current_disk_entries = load_client_kontenplan_entries(
                self.client_name, 
                "AR" if self.rb_ar.isChecked() else "ER", 
                self.base_dir
            )
            current_disk_entries.append(data)
            current_disk_entries.sort(key=account_sort_key)
            
            try:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(serialize_kontenplan(current_disk_entries))
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Konnte neues Konto nicht im Kontenplan speichern:\n{e}")
                return
                
            # Neu laden
            self.er_path, self.er_entries = load_client_kontenplan_entries(self.client_name, "ER", self.base_dir)
            self.ar_path, self.ar_entries = load_client_kontenplan_entries(self.client_name, "AR", self.base_dir)
            self.load_entries_for_view()
            
            # Das neu erstellte Konto sofort selektieren
            new_full = f"{k} – {n}"
            self.current_konto = new_full
            self.populate_table()
            
            QMessageBox.information(
                self, 
                "Konto angelegt", 
                f"Das Konto '{new_full}' wurde erfolgreich im Kontenplan von {self.client_name} gespeichert und ausgewählt!"
            )

    def accept_selection(self):
        row = self.table.currentRow()
        if row < 0 or row >= self.table.rowCount():
            QMessageBox.warning(self, "Hinweis", "Bitte wähle ein Konto aus der Tabelle aus.")
            return
            
        k = self.table.item(row, 0).text().strip()
        n = self.table.item(row, 1).text().strip()
        
        self.selected_konto_str = f"{k} – {n}" if n else k
        self.accept()

    def get_selected_konto(self) -> str:
        return self.selected_konto_str
