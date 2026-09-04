import os
import re
from typing import List, Dict, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QMessageBox, QAbstractItemView, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


def parse_kontenplan(raw_text: str) -> List[Dict[str, str]]:
    """
    Parst eine Kontenplan-Textdatei robust in eine Liste von Einträgen:
    [{'konto': '100 / 801001', 'name': 'Materialeinkauf', 'beschreibung': '...'}, ...]
    """
    entries = []
    lines = [l.strip() for l in raw_text.splitlines()]
    current_entry = None
    
    # Erkennt Kontonummer und Bezeichnung in gängigen Formaten:
    # 100 / 801001 – Name
    # 104 / 819020_RR - Name
    # - Konto 0100: Name
    header_pattern = re.compile(
        r'^(?:-\s*)?(?:Konto\s+)?(\d+(?:\s*/\s*[\w]+)?)\s*[:–-]\s*(.+)$',
        re.IGNORECASE
    )
    
    for line in lines:
        if not line:
            continue
        m = header_pattern.match(line)
        if m:
            if current_entry:
                entries.append(current_entry)
            current_entry = {
                'konto': m.group(1).strip(),
                'name': m.group(2).strip(),
                'beschreibung': ''
            }
        else:
            if current_entry:
                if current_entry['beschreibung']:
                    current_entry['beschreibung'] += '\n' + line
                else:
                    current_entry['beschreibung'] = line
            else:
                # Falls eine Zeile vor dem ersten Header existiert, als unformatiert merken
                pass
                
    if current_entry:
        entries.append(current_entry)
        
    return entries


def serialize_kontenplan(entries: List[Dict[str, str]]) -> str:
    """
    Formatiert eine Liste von Einträgen sauber zurück in die .txt-Struktur für die KI.
    """
    blocks = []
    for e in entries:
        konto = e.get('konto', '').strip()
        name = e.get('name', '').strip()
        desc = e.get('beschreibung', '').strip()
        if not konto and not name:
            continue
            
        if desc:
            blocks.append(f"{konto} – {name}\n{desc}")
        else:
            blocks.append(f"{konto} – {name}")
            
    return '\n\n'.join(blocks) + '\n' if blocks else ''


def account_sort_key(entry: Dict[str, str]):
    """Erzeugt einen numerischen Sortierschlüssel für Kontonummern (z.B. 100 / 801001)."""
    konto_str = entry.get('konto', '').strip()
    numbers = re.findall(r'\d+', konto_str)
    if numbers:
        return (tuple(int(n) for n in numbers), konto_str.upper())
    return ((999999,), konto_str.upper())


class KontoDetailDialog(QDialog):
    """Dialog zum Erstellen oder Bearbeiten eines einzelnen Kontos."""
    def __init__(self, parent=None, konto="", name="", beschreibung="", existing_konten=None, is_edit=False):
        super().__init__(parent)
        self.setWindowTitle("Konto bearbeiten" if is_edit else "Neues Konto anlegen")
        self.resize(500, 320)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        self.existing_konten = existing_konten or set()
        self.initial_konto = konto.strip().upper()
        self.is_edit = is_edit
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.konto_edit = QLineEdit(konto)
        self.konto_edit.setPlaceholderText("z. B. 104 / 810001 oder 810001")
        form.addRow("Kontonummer *:", self.konto_edit)
        
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("z. B. Stromspesen oder Materialeinkauf")
        form.addRow("Bezeichnung *:", self.name_edit)
        
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlainText(beschreibung)
        self.desc_edit.setPlaceholderText("Optionale Stichworte oder Beispiele für die KI\n(z. B. Energieverkauf, Stromkosten, Netzausgaben, Steuern)")
        self.desc_edit.setFixedHeight(100)
        form.addRow("Notizen / Beispiele (für KI):", self.desc_edit)
        
        layout.addLayout(form)
        
        self.lbl_warning = QLabel("")
        self.lbl_warning.setStyleSheet("color: #e53935; font-size: 11px;")
        layout.addWidget(self.lbl_warning)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_save = QPushButton("Übernehmen")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.validate_and_accept)
        btn_layout.addWidget(btn_save)
        
        layout.addLayout(btn_layout)
        
    def validate_and_accept(self):
        k = self.konto_edit.text().strip()
        n = self.name_edit.text().strip()
        
        if not k:
            self.lbl_warning.setText("Bitte eine Kontonummer angeben.")
            self.konto_edit.setFocus()
            return
        if not n:
            self.lbl_warning.setText("Bitte eine Kontenbezeichnung angeben.")
            self.name_edit.setFocus()
            return
            
        k_upper = k.upper()
        if not self.is_edit or k_upper != self.initial_konto:
            if k_upper in self.existing_konten:
                self.lbl_warning.setText(f"Das Konto '{k}' existiert bereits im Kontenplan!")
                self.konto_edit.setFocus()
                return
                
        self.accept()
        
    def get_data(self) -> Dict[str, str]:
        return {
            'konto': self.konto_edit.text().strip(),
            'name': self.name_edit.text().strip(),
            'beschreibung': self.desc_edit.toPlainText().strip()
        }


class KontenplanEditorDialog(QDialog):
    """
    Moderner Kontenplan-Editor mit:
    - Tab 1: Strukturierter Tabellen-Ansicht mit Live-Suche, Sortierung, Add/Edit/Delete
    - Tab 2: Rohtext-Modus für schnelles Copy-Paste
    - Automatischer Zwei-Wege-Synchronisation
    """
    def __init__(self, parent=None, file_path="", client_name="", typ="ER"):
        super().__init__(parent)
        self.file_path = file_path
        self.client_name = client_name
        self.typ = typ
        
        typ_text = "Eingangsrechnungen (ER)" if typ == "ER" else "Ausgangsrechnungen (AR)"
        self.setWindowTitle(f"Kontenplan-Editor: {client_name} [{typ_text}]")
        self.resize(950, 680)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        self.entries: List[Dict[str, str]] = []
        
        self.init_ui()
        self.load_file()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # Tabs
        self.tab_widget = QTabWidget()
        
        # --- TAB 1: Strukturierte Ansicht ---
        tab_table = QWidget()
        tab_layout = QVBoxLayout(tab_table)
        tab_layout.setContentsMargins(10, 10, 10, 10)
        tab_layout.setSpacing(10)
        
        # Filter & Suchleiste
        search_layout = QHBoxLayout()
        lbl_search = QLabel("🔍")
        lbl_search.setStyleSheet("font-size: 14px;")
        search_layout.addWidget(lbl_search)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Suchbegriff eingeben (Konto, Bezeichnung oder Beispiele durchsuchen)...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self.filter_table)
        search_layout.addWidget(self.search_edit, stretch=1)
        
        tab_layout.addLayout(search_layout)
        
        # Tabelle
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Konto", "Bezeichnung", "Notizen / Beispiele (für KI)"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.edit_selected)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 140)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(1, 260)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        tab_layout.addWidget(self.table)
        
        # Toolbar unter Tabelle
        btn_bar = QHBoxLayout()
        
        btn_add = QPushButton("➕ Neues Konto")
        btn_add.clicked.connect(self.add_konto)
        btn_bar.addWidget(btn_add)
        
        btn_edit = QPushButton("✏️ Bearbeiten")
        btn_edit.clicked.connect(self.edit_selected)
        btn_bar.addWidget(btn_edit)
        
        btn_delete = QPushButton("🗑️ Löschen")
        btn_delete.clicked.connect(self.delete_selected)
        btn_bar.addWidget(btn_delete)
        
        btn_bar.addSpacing(15)
        
        btn_sort = QPushButton("🔢 Nach Kontonummer sortieren")
        btn_sort.clicked.connect(self.sort_by_konto)
        btn_bar.addWidget(btn_sort)
        
        btn_bar.addStretch()
        tab_layout.addLayout(btn_bar)
        
        self.tab_widget.addTab(tab_table, "📋 Strukturierte Übersicht")
        
        # --- TAB 2: Rohtext ---
        tab_raw = QWidget()
        raw_layout = QVBoxLayout(tab_raw)
        raw_layout.setContentsMargins(10, 10, 10, 10)
        raw_layout.setSpacing(8)
        
        lbl_raw_info = QLabel("Hier kannst du den Kontenplan direkt im Textformat einsehen oder per Copy-Paste bearbeiten:")
        lbl_raw_info.setStyleSheet("color: #888; font-size: 11px;")
        raw_layout.addWidget(lbl_raw_info)
        
        self.raw_text_edit = QTextEdit()
        self.raw_text_edit.setFont(QFont("Consolas, Courier New, Monospace", 10))
        raw_layout.addWidget(self.raw_text_edit)
        
        self.tab_widget.addTab(tab_raw, "📝 Rohtext (Copy-Paste)")
        
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(self.tab_widget)
        
        # Footer
        footer = QHBoxLayout()
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #666; font-size: 11px;")
        footer.addWidget(self.lbl_status)
        footer.addStretch()
        
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setFixedWidth(120)
        footer.addWidget(btn_cancel)
        
        btn_save = QPushButton("💾 Speichern")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.save_and_close)
        btn_save.setFixedWidth(130)
        footer.addWidget(btn_save)
        
        main_layout.addLayout(footer)

    def load_file(self):
        """Liest die Datei von der Festplatte ein."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.raw_text_edit.setPlainText(content)
                self.entries = parse_kontenplan(content)
            except Exception as e:
                QMessageBox.warning(self, "Fehler", f"Konnte Kontenplan nicht laden: {e}")
                self.entries = []
        else:
            self.entries = []
            self.raw_text_edit.setPlainText("")
            
        self.populate_table()
        self.update_status()

    def populate_table(self):
        """Befüllt die Tabelle mit den aktuellen Einträgen."""
        self.table.setRowCount(len(self.entries))
        for row, item in enumerate(self.entries):
            k_item = QTableWidgetItem(item.get('konto', ''))
            k_item.setFont(QFont("", -1, QFont.Weight.Bold))
            k_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            
            n_item = QTableWidgetItem(item.get('name', ''))
            n_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            
            # Erste Zeile oder Zusammenfassung der Beschreibung für die Tabelle
            desc_text = item.get('beschreibung', '').strip().replace('\n', ' ')
            d_item = QTableWidgetItem(desc_text)
            d_item.setToolTip(item.get('beschreibung', ''))
            d_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            
            self.table.setItem(row, 0, k_item)
            self.table.setItem(row, 1, n_item)
            self.table.setItem(row, 2, d_item)
            
        self.filter_table()

    def filter_table(self):
        """Filtert Zeilen nach dem Suchtext."""
        query = self.search_edit.text().strip().upper()
        visible_count = 0
        
        for row in range(self.table.rowCount()):
            k = self.table.item(row, 0).text().upper() if self.table.item(row, 0) else ""
            n = self.table.item(row, 1).text().upper() if self.table.item(row, 1) else ""
            d = self.table.item(row, 2).text().upper() if self.table.item(row, 2) else ""
            
            match = (not query) or (query in k) or (query in n) or (query in d)
            self.table.setRowHidden(row, not match)
            if match:
                visible_count += 1
                
        self.update_status(visible_count)

    def update_status(self, visible_count=None):
        total = len(self.entries)
        if visible_count is None or visible_count == total:
            self.lbl_status.setText(f"{total} Konten hinterlegt")
        else:
            self.lbl_status.setText(f"{visible_count} von {total} Konten angezeigt (gefiltert)")

    def add_konto(self):
        existing = {e['konto'].strip().upper() for e in self.entries}
        dlg = KontoDetailDialog(self, existing_konten=existing, is_edit=False)
        if dlg.exec():
            data = dlg.get_data()
            self.entries.append(data)
            self.populate_table()
            # Markiere die neu hinzugefügte Zeile
            new_row = self.table.rowCount() - 1
            self.table.selectRow(new_row)
            self.table.scrollToItem(self.table.item(new_row, 0))

    def edit_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.entries):
            return
            
        # Finde den korrekten Index in self.entries, auch wenn gefiltert
        k_val = self.table.item(row, 0).text().strip()
        idx = -1
        for i, e in enumerate(self.entries):
            if e['konto'].strip() == k_val:
                idx = i
                break
        if idx == -1:
            idx = row
            
        current_data = self.entries[idx]
        existing = {e['konto'].strip().upper() for i, e in enumerate(self.entries) if i != idx}
        
        dlg = KontoDetailDialog(
            self,
            konto=current_data.get('konto', ''),
            name=current_data.get('name', ''),
            beschreibung=current_data.get('beschreibung', ''),
            existing_konten=existing,
            is_edit=True
        )
        if dlg.exec():
            self.entries[idx] = dlg.get_data()
            self.populate_table()
            self.table.selectRow(row)

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.entries):
            return
            
        k_val = self.table.item(row, 0).text().strip()
        n_val = self.table.item(row, 1).text().strip()
        
        reply = QMessageBox.question(
            self,
            "Konto löschen",
            f"Möchtest du das Konto '{k_val} – {n_val}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            idx = -1
            for i, e in enumerate(self.entries):
                if e['konto'].strip() == k_val:
                    idx = i
                    break
            if idx != -1:
                self.entries.pop(idx)
            else:
                self.entries.pop(row)
                
            self.populate_table()

    def sort_by_konto(self):
        """Sortiert alle Einträge numerisch aufsteigend nach Kontonummer."""
        if not self.entries:
            return
        self.entries.sort(key=account_sort_key)
        self.populate_table()

    def on_tab_changed(self, index):
        """Synchronisiert Daten zwischen Tabelle und Rohtext."""
        if index == 1:
            # Wechsel zu Rohtext: Tabelle -> Rohtext
            serialized = serialize_kontenplan(self.entries)
            self.raw_text_edit.setPlainText(serialized)
        elif index == 0:
            # Wechsel zu Tabelle: Rohtext -> Tabelle
            raw_text = self.raw_text_edit.toPlainText()
            self.entries = parse_kontenplan(raw_text)
            self.populate_table()

    def save_and_close(self):
        """Speichert den Kontenplan in die Textdatei."""
        # Falls der Benutzer zuletzt im Rohtext-Modus war, Rohtext nehmen
        if self.tab_widget.currentIndex() == 1:
            content_to_save = self.raw_text_edit.toPlainText().strip() + '\n'
        else:
            content_to_save = serialize_kontenplan(self.entries)
            
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(content_to_save)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Speicherfehler", f"Fehler beim Speichern der Datei:\n{e}")
