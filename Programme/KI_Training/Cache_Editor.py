import os
import json
import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QLineEdit, QPushButton, QTableView, QHeaderView, QFrame,
    QCheckBox, QMessageBox, QDialog, QFormLayout, QAbstractItemView,
    QStyledItemDelegate, QStyleOptionButton, QStyle, QApplication
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

script_dir = os.path.dirname(os.path.abspath(__file__))
prog_dir = os.path.dirname(script_dir)
if prog_dir not in sys.path:
    sys.path.append(prog_dir)

try:
    from DatabaseManager import get_db
except ImportError:
    pass

class CacheTableModel(QAbstractTableModel):
    def __init__(self, data=None):
        super().__init__()
        self._data = data or [] # List of tuples: (key, status, lieferant, beschreibung, wert, data_obj)
        self.headers = ["Status", "Lieferant", "Beschreibung", "Konto / Kategorie"]
        
    def set_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)
        
    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)
        
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
            
        row = index.row()
        col = index.column()
        item = self._data[row]
        
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if col == 0:
                return "✅" if item[1] else "⚠️"
            elif col == 1:
                return item[2]
            elif col == 2:
                return item[3]
            elif col == 3:
                return item[4]
                
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 0:
                return Qt.AlignmentFlag.AlignCenter
                
        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == 0:
                return QColor("green") if item[1] else QColor("orange")
                
        return None
        
    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def flags(self, index):
        flags = super().flags(index)
        if index.column() == 3: # Make "Wert" column editable
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index, value, role):
        if index.isValid() and role == Qt.ItemDataRole.EditRole and index.column() == 3:
            row = index.row()
            # Update internal data
            old_item = list(self._data[row])
            old_item[4] = value
            self._data[row] = tuple(old_item)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
            return True
        return False

class CacheEditorFrame(QWidget):
    def __init__(self, master, current_client_callback):
        super().__init__(master)
        self.current_client_callback = current_client_callback
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        
        # --- 1. Header (Title) ---
        self.header_frame = QHBoxLayout()
        
        self.title_label = QLabel("🧠 KI-Training (Gedächtnis-Editor)")
        font = QFont()
        font.setPointSize(22)
        font.setBold(True)
        self.title_label.setFont(font)
        self.header_frame.addWidget(self.title_label)
        
        self.header_frame.addStretch()
        
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("", -1, QFont.Weight.Bold))
        self.header_frame.addWidget(self.status_label)
        
        self.main_layout.addLayout(self.header_frame)
        
        # --- 2. Controls Card ---
        self.controls_card = QFrame()
        self.controls_card.setObjectName("ControlsCard")
        self.controls_card.setStyleSheet("""
            #ControlsCard {
                background-color: palette(window);
                border-radius: 10px;
                border: 1px solid palette(mid);
            }
        """)
        controls_layout = QVBoxLayout(self.controls_card)
        controls_layout.setContentsMargins(15, 15, 15, 15)
        
        # Row 1: Such & Filter
        filter_layout = QHBoxLayout()
        
        self.cache_type_var = QComboBox()
        self.cache_type_var.addItems(["Sektorenanalyse", "FIBU Kontierung"])
        self.cache_type_var.currentTextChanged.connect(self.load_data)
        filter_layout.addWidget(self.cache_type_var)
        
        self.filter_var = QComboBox()
        self.filter_var.addItems(["Alle", "Bestätigt", "Unbestätigt"])
        self.filter_var.currentTextChanged.connect(self.apply_filters_and_render)
        filter_layout.addWidget(self.filter_var)
        
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Suchen...")
        self.search_entry.textChanged.connect(self.apply_filters_and_render)
        filter_layout.addWidget(self.search_entry)
        
        btn_refresh = QPushButton("↻")
        btn_refresh.setFixedWidth(40)
        btn_refresh.clicked.connect(self.load_data)
        filter_layout.addWidget(btn_refresh)
        
        controls_layout.addLayout(filter_layout)
        
        # Row 2: Batch Actions
        batch_layout = QHBoxLayout()
        
        self.batch_confirm_btn = QPushButton("[✓] Ausgewählte bestätigen")
        self.batch_confirm_btn.setStyleSheet("background-color: #2b9e4a; color: white;")
        self.batch_confirm_btn.clicked.connect(self.batch_confirm)
        batch_layout.addWidget(self.batch_confirm_btn)
        
        self.batch_delete_btn = QPushButton("[✗] Ausgewählte löschen")
        self.batch_delete_btn.setStyleSheet("background-color: #cc0000; color: white;")
        self.batch_delete_btn.clicked.connect(self.batch_delete)
        batch_layout.addWidget(self.batch_delete_btn)
        
        batch_layout.addStretch()
        
        self.save_btn = QPushButton("💾 Manuelle Änderungen Speichern")
        self.save_btn.setStyleSheet("background-color: #e58e26; color: white;")
        self.save_btn.clicked.connect(self.save_data)
        batch_layout.addWidget(self.save_btn)
        
        self.add_btn = QPushButton("➕ Neuer Eintrag")
        self.add_btn.setStyleSheet("background-color: #3498db; color: white;")
        self.add_btn.clicked.connect(self.add_new_entry)
        batch_layout.addWidget(self.add_btn)
        
        controls_layout.addLayout(batch_layout)
        self.main_layout.addWidget(self.controls_card)
        
        # --- 3. Data Area ---
        self.table_view = QTableView()
        self.table_model = CacheTableModel()
        self.table_view.setModel(self.table_model)
        
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_view.setSortingEnabled(True) 
        
        self.main_layout.addWidget(self.table_view, stretch=1)
        
        self.current_data = {}
        
    def show_status(self, text, color="text"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")
        QTimer.singleShot(4000, lambda: self.status_label.setText(""))
        
    def get_client(self):
        client = self.current_client_callback()
        if not client or client == "Kein Kunde":
            return None
        return client
        
    def load_data(self, *args):
        client = self.get_client()
        if not client:
            self.table_model.set_data([])
            self.show_status("Bitte zuerst einen Kunden auswählen!", "red")
            return
            
        try:
            db = get_db()
            cache_type = self.cache_type_var.currentText()
            if cache_type == "Sektorenanalyse":
                self.current_data = db.get_analyse_cache_full(client)
            else:
                self.current_data = db.get_konten_cache_full(client)
        except Exception as e:
            self.show_status(f"Fehler: {e}", "red")
            return
            
        self.apply_filters_and_render()
        self.show_status("Daten geladen", "green")

    def apply_filters_and_render(self, *args):
        current_filter = self.filter_var.currentText()
        search_text = self.search_entry.text().lower().strip()
        
        table_data = []
        for key, data_obj in self.current_data.items():
            confirmed = data_obj['confirmed']
            value = data_obj['value']
            val_str = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
            key_lower = key.lower()
            
            # Status Filter
            if current_filter == "Bestätigt" and not confirmed: continue
            if current_filter == "Unbestätigt" and confirmed: continue
            
            # Search Filter
            if search_text:
                if search_text not in key_lower and search_text not in val_str.lower():
                    continue
                    
            lieferant = key
            beschreibung = "(Keine Beschreibung)"
            if " | " in key:
                parts = key.split(" | ", 1)
                lieferant = parts[0]
                beschreibung = parts[1] if parts[1].strip() else "(Keine Beschreibung)"
                
            table_data.append((key, confirmed, lieferant, beschreibung, val_str, data_obj))
            
        # Default Sort by Lieferant A-Z
        table_data.sort(key=lambda x: x[2].lower())
        
        self.table_model.set_data(table_data)
        
        # Resize columns after populating
        self.table_view.resizeColumnToContents(0) 
        if self.table_view.columnWidth(1) < 150: self.table_view.setColumnWidth(1, 150)
        if self.table_view.columnWidth(2) < 200: self.table_view.setColumnWidth(2, 200)

    def get_selected_keys(self):
        indexes = self.table_view.selectionModel().selectedRows()
        keys = set()
        for idx in indexes:
            row = idx.row()
            if row < len(self.table_model._data):
                keys.add(self.table_model._data[row][0]) 
        return keys

    def batch_confirm(self):
        selected = self.get_selected_keys()
        if not selected:
            self.show_status("Nichts ausgewählt!", "orange")
            return
            
        client = self.get_client()
        db = get_db()
        cache_type = self.cache_type_var.currentText()
        new_entries = {}
        
        for key in selected:
            if key in self.current_data:
                val = self.current_data[key]['value']
                for row_data in self.table_model._data:
                    if row_data[0] == key:
                        val_str = row_data[4]
                        try:
                            val = json.loads(val_str) if cache_type == "Sektorenanalyse" else val_str
                        except:
                            val = val_str
                        break
                        
                new_entries[key] = {'value': val, 'confirmed': True}
                self.current_data[key]['confirmed'] = True
                self.current_data[key]['value'] = val
                
        if cache_type == "Sektorenanalyse":
            db.save_analyse_cache_batch(client, new_entries)
        else:
            db.save_konten_cache_batch(client, new_entries)
            
        self.apply_filters_and_render()
        self.show_status(f"{len(new_entries)} Einträge bestätigt!", "green")

    def batch_delete(self):
        selected = self.get_selected_keys()
        if not selected:
            self.show_status("Nichts ausgewählt!", "orange")
            return
            
        reply = QMessageBox.question(self, "Löschen bestätigen", f"Möchtest du wirklich {len(selected)} Einträge löschen?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return
            
        client = self.get_client()
        db = get_db()
        cache_type = self.cache_type_var.currentText()
        
        for key in selected:
            db.delete_cache_entry(cache_type, client, key)
            if key in self.current_data:
                del self.current_data[key]
                
        self.apply_filters_and_render()
        self.show_status(f"{len(selected)} Einträge gelöscht!", "green")

    def save_data(self):
        client = self.get_client()
        db = get_db()
        cache_type = self.cache_type_var.currentText()
        new_entries = {}
        
        for row_data in self.table_model._data:
            key = row_data[0]
            val_str = row_data[4]
            confirmed = row_data[1]
            try:
                if cache_type == "Sektorenanalyse":
                    parsed = json.loads(val_str)
                else:
                    parsed = val_str
                new_entries[key] = {'value': parsed, 'confirmed': confirmed}
                self.current_data[key]['value'] = parsed
            except:
                new_entries[key] = {'value': val_str, 'confirmed': confirmed}
                self.current_data[key]['value'] = val_str
                
        if new_entries:
            if cache_type == "Sektorenanalyse":
                db.save_analyse_cache_batch(client, new_entries)
            else:
                db.save_konten_cache_batch(client, new_entries)
                
        self.show_status("Manuelle Änderungen gespeichert!", "green")
        self.apply_filters_and_render()

    def add_new_entry(self):
        client = self.get_client()
        if not client:
            self.show_status("Bitte zuerst einen Kunden auswählen!", "red")
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Neuen Eintrag hinzufügen")
        dialog.resize(450, 300)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        layout = QFormLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        
        liefer_var = QLineEdit()
        layout.addRow("Lieferant (z.B. Hans):", liefer_var)
        
        desc_var = QLineEdit()
        layout.addRow("Beschreibung (z.B. Kuh 25.12.2006):", desc_var)
        
        val_var = QLineEdit()
        layout.addRow("Konto (z.B. 4000):", val_var)
        
        def save():
            lieferant = liefer_var.text().strip()
            desc = desc_var.text().strip()
            val = val_var.text().strip()
            if not lieferant or not desc or not val:
                return
                
            key = f"{lieferant} | {desc}".upper()
            cache_type = self.cache_type_var.currentText()
            try:
                if cache_type == "Sektorenanalyse":
                    parsed_val = json.loads(val)
                else:
                    parsed_val = val
            except:
                parsed_val = val
                
            new_entry = {key: {'value': parsed_val, 'confirmed': True}}
            
            db = get_db()
            if cache_type == "Sektorenanalyse":
                db.save_analyse_cache_batch(client, new_entry)
            else:
                db.save_konten_cache_batch(client, new_entry)
                
            self.current_data[key] = new_entry[key]
            
            dialog.accept()
            self.apply_filters_and_render()
            self.show_status("Eintrag hinzugefügt!", "green")
            
        btn_save = QPushButton("Speichern")
        btn_save.setStyleSheet("background-color: #2b9e4a; color: white;")
        btn_save.clicked.connect(save)
        layout.addRow("", btn_save)
        
        dialog.exec()
