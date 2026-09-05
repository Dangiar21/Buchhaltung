import os
import json
import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QLineEdit, QPushButton, QTableView, QHeaderView, QFrame,
    QCheckBox, QMessageBox, QDialog, QFormLayout, QAbstractItemView,
    QStyledItemDelegate, QStyleOptionButton, QStyle, QApplication,
    QStyleOptionViewItem, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal, QTimer, QRect, QPointF
from PyQt6.QtGui import QFont, QColor, QPainter, QPen
import qtawesome as qta

script_dir = os.path.dirname(os.path.abspath(__file__))
prog_dir = os.path.dirname(script_dir)
if prog_dir not in sys.path:
    sys.path.append(prog_dir)

try:
    from DatabaseManager import get_db
except ImportError:
    pass

root_dir = os.path.dirname(prog_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

try:
    from src.ui.konto_picker import KontoPickerDialog, get_konto_display_map, format_konto_with_name
except ImportError:
    pass

class CenterCheckBoxDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
        is_hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        
        # Check dark mode
        qapp = QApplication.instance()
        is_dark = bool(qapp and qapp.palette().window().color().lightness() < 128)
        
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. Background
        if is_selected:
            painter.fillRect(option.rect, QColor("#1e3a5f" if is_dark else "#e4f0fa"))
        else:
            row = index.row()
            if is_dark:
                bg = QColor("#1f1f23") if row % 2 == 1 else QColor("#18181b")
            else:
                bg = QColor("#f8fafc") if row % 2 == 1 else QColor("#ffffff")
            painter.fillRect(option.rect, bg)
            
        # Cell bottom border
        painter.setPen(QPen(QColor("#27272a" if is_dark else "#f1f5f9"), 1))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        
        # 2. Checkbox Indicator
        box_size = 18
        x = option.rect.x() + (option.rect.width() - box_size) // 2
        y = option.rect.y() + (option.rect.height() - box_size) // 2
        box_rect = QRect(x, y, box_size, box_size)
        
        if checked:
            # Checked: Bright blue rounded box with crisp white checkmark
            painter.setBrush(QColor("#3a7ebf"))
            painter.setPen(QColor("#3a7ebf"))
            painter.drawRoundedRect(box_rect, 4, 4)
            
            pen = QPen(QColor("#ffffff"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            p1 = QPointF(x + 4.5, y + 9.5)
            p2 = QPointF(x + 7.5, y + 13.0)
            p3 = QPointF(x + 13.5, y + 5.5)
            painter.drawLine(p1, p2)
            painter.drawLine(p2, p3)
        else:
            # Unchecked: Neutral box with clear border
            box_bg = QColor("#27272a" if is_dark else "#ffffff")
            border_col = QColor("#38bdf8" if is_dark else "#3a7ebf") if is_hover else QColor("#52525b" if is_dark else "#cbd5e1")
            painter.setBrush(box_bg)
            painter.setPen(QPen(border_col, 1.8))
            painter.drawRoundedRect(box_rect, 4, 4)
            
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() in [event.Type.MouseButtonRelease, event.Type.MouseButtonDblClick]:
            if event.button() == Qt.MouseButton.LeftButton:
                checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
                model.setData(index, Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
                return True
        return False

class CacheTableModel(QAbstractTableModel):
    def __init__(self, data=None):
        super().__init__()
        self._data = data or [] # List of lists: [key, status, lieferant, beschreibung, wert, data_obj, is_checked]
        self.headers = ["Status", "Lieferant", "Beschreibung", "Konto / Kategorie", "Auswählen"]
        
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
        
        if role == Qt.ItemDataRole.CheckStateRole and col == 4:
            return Qt.CheckState.Checked if item[6] else Qt.CheckState.Unchecked
            
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if col == 0:
                return "🟢" if item[1] else "🔴"
            elif col == 1:
                return item[2]
            elif col == 2:
                return item[3]
            elif col == 3:
                return item[4]
                
        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 0:
                return "Status: Bestätigt (Grün)" if item[1] else "Status: Unbestätigt (Rot, Vorschlag/Entwurf)"
            elif col == 1:
                return f"Lieferant:\n{item[2]}"
            elif col == 2:
                desc = str(item[3])
                if "[KONTEXT:" in desc:
                    parts = desc.split("[KONTEXT:")
                    main_d = parts[0].strip()
                    ctx_d = parts[1].rstrip("]").strip()
                    return f"Beschreibung:\n{main_d}\n\nRechnungskontext:\n{ctx_d}"
                return f"Vollständige Beschreibung:\n{desc}"
            elif col == 3:
                return f"Konto / Kategorie:\n{item[4]}"
            elif col == 4:
                return "Zeile für Sammelaktionen auswählen"

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 0:
                return Qt.AlignmentFlag.AlignCenter
                
        elif role == Qt.ItemDataRole.ForegroundRole:
            pass # We rely on unicode emoji color now
                
        return None
        
    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def flags(self, index):
        flags = super().flags(index)
        if index.column() == 4:
            flags |= Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable
        elif index.column() == 3: # Make "Wert" column editable
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index, value, role):
        if not index.isValid():
            return False
            
        row = index.row()
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 4:
            if isinstance(value, Qt.CheckState):
                is_checked = (value == Qt.CheckState.Checked)
            else:
                is_checked = (value == 2 or value is True)
            self._data[row][6] = is_checked
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True
            
        if role == Qt.ItemDataRole.EditRole and index.column() == 3:
            self._data[row][4] = value
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
            return True
            
        return False

class CacheEntryDetailDialog(QDialog):
    def __init__(self, item, client_name="", parent=None):
        super().__init__(parent)
        self.item = item
        self.client_name = client_name
        self.setWindowTitle("Details zum Cache-Eintrag")
        self.resize(600, 440)
        
        qapp = QApplication.instance()
        is_dark = bool(qapp and qapp.palette().window().color().lightness() < 128)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 22, 22, 22)
        
        # Lieferant
        lieferant_label = QLabel(f"<b style='font-size: 13px;'>Lieferant:</b> <span style='font-size: 13px;'>{item[2]}</span>")
        lieferant_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lieferant_label)
        
        # Status & Konto
        status_badge = "<span style='color: #10b981; font-weight: bold;'>🟢 Bestätigt</span>" if item[1] else "<span style='color: #ef4444; font-weight: bold;'>🔴 Unbestätigt (Vorschlag)</span>"
        
        konto_bar = QHBoxLayout()
        self.meta_label = QLabel(f"<b style='font-size: 13px;'>Konto / Kategorie:</b> <span style='font-size: 13px;'>{item[4]}</span> &nbsp;&nbsp;|&nbsp;&nbsp; {status_badge}")
        self.meta_label.setTextFormat(Qt.TextFormat.RichText)
        konto_bar.addWidget(self.meta_label)
        konto_bar.addStretch()
        
        btn_change_konto = QPushButton("✏️ Ändern...")
        btn_change_konto.setFixedHeight(28)
        btn_change_konto.clicked.connect(self.change_konto)
        konto_bar.addWidget(btn_change_konto)
        layout.addLayout(konto_bar)
        
        # Vollständige Beschreibung
        lbl_desc = QLabel("<b style='font-size: 13px;'>Vollständige Beschreibung:</b>")
        lbl_desc.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl_desc)
        
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(str(item[3]))
        bg_col = "#27272a" if is_dark else "#ffffff"
        text_col = "#f4f4f5" if is_dark else "#1e293b"
        border_col = "#3f3f46" if is_dark else "#cbd5e1"
        self.text_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {bg_col};
                color: {text_col};
                border: 1px solid {border_col};
                border-radius: 8px;
                padding: 10px;
                font-family: 'Segoe UI', Inter, sans-serif;
                font-size: 13px;
                line-height: 1.4;
            }}
        """)
        layout.addWidget(self.text_edit, stretch=1)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_copy = QPushButton(" In Zwischenablage kopieren")
        btn_copy.setIcon(qta.icon('fa5s.copy', color='#38bdf8' if is_dark else '#3a7ebf'))
        btn_copy.setFixedHeight(34)
        btn_copy.clicked.connect(self.copy_description)
        btn_layout.addWidget(btn_copy)
        
        btn_layout.addStretch()
        
        btn_close = QPushButton("Schließen")
        btn_close.setFixedHeight(34)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)

    def change_konto(self):
        picker = KontoPickerDialog(self, client_name=self.client_name, current_konto=str(self.item[4]))
        if picker.exec():
            new_konto = picker.get_selected_konto()
            self.item[4] = new_konto
            status_badge = "<span style='color: #10b981; font-weight: bold;'>🟢 Bestätigt</span>" if self.item[1] else "<span style='color: #ef4444; font-weight: bold;'>🔴 Unbestätigt (Vorschlag)</span>"
            self.meta_label.setText(f"<b style='font-size: 13px;'>Konto / Kategorie:</b> <span style='font-size: 13px;'>{new_konto}</span> &nbsp;&nbsp;|&nbsp;&nbsp; {status_badge}")

    def copy_description(self):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(self.text_edit.toPlainText())

class CacheEditorFrame(QWidget):
    def __init__(self, master, current_client_callback):
        super().__init__(master)
        self.current_client_callback = current_client_callback
        self.is_dirty = False
        
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
        self.update_card_style()
        
        controls_layout = QVBoxLayout(self.controls_card)
        controls_layout.setContentsMargins(20, 20, 20, 20)
        controls_layout.setSpacing(15)
        
        # Row 1: Such & Filter
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        
        self.cache_type_var = QComboBox()
        self.cache_type_var.addItems(["FIBU Kontierung"])
        self.cache_type_var.currentTextChanged.connect(self.load_data)
        self.cache_type_var.setMinimumWidth(160)
        filter_layout.addWidget(self.cache_type_var)
        
        self.filter_var = QComboBox()
        self.filter_var.addItems(["Alle", "Bestätigt", "Unbestätigt"])
        self.filter_var.currentTextChanged.connect(self.apply_filters_and_render)
        self.filter_var.setMinimumWidth(120)
        filter_layout.addWidget(self.filter_var)
        
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Suchen...")
        self.search_entry.textChanged.connect(self.apply_filters_and_render)
        filter_layout.addWidget(self.search_entry)
        
        btn_refresh = QPushButton()
        btn_refresh.setObjectName("BtnRefresh")
        btn_refresh.setIcon(qta.icon('fa5s.sync-alt', color='#475569'))
        btn_refresh.setFixedWidth(40)
        btn_refresh.setFixedHeight(32)
        btn_refresh.setToolTip("Daten neu laden")
        btn_refresh.clicked.connect(self.load_data)
        filter_layout.addWidget(btn_refresh)
        
        controls_layout.addLayout(filter_layout)
        
        # Row 2: Batch Actions
        batch_layout = QHBoxLayout()
        batch_layout.setSpacing(10)
        
        self.select_all_btn = QPushButton(" Alle")
        self.select_all_btn.setObjectName("BtnSelectAll")
        self.select_all_btn.setIcon(qta.icon('fa5s.check-square', color='#475569'))
        self.select_all_btn.setFixedHeight(32)
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        batch_layout.addWidget(self.select_all_btn)
        
        self.batch_confirm_btn = QPushButton(" Bestätigen")
        self.batch_confirm_btn.setObjectName("BtnConfirm")
        self.batch_confirm_btn.setIcon(qta.icon('fa5s.check', color='white'))
        self.batch_confirm_btn.setFixedHeight(32)
        self.batch_confirm_btn.clicked.connect(self.batch_confirm)
        batch_layout.addWidget(self.batch_confirm_btn)
        
        self.batch_delete_btn = QPushButton(" Löschen")
        self.batch_delete_btn.setObjectName("BtnDelete")
        self.batch_delete_btn.setIcon(qta.icon('fa5s.trash-alt', color='white'))
        self.batch_delete_btn.setFixedHeight(32)
        self.batch_delete_btn.clicked.connect(self.batch_delete)
        batch_layout.addWidget(self.batch_delete_btn)

        self.expand_btn = QPushButton(" Ausklappen")
        self.expand_btn.setObjectName("BtnExpand")
        self.expand_btn.setCheckable(True)
        self.expand_btn.setIcon(qta.icon('fa5s.expand-alt', color='#475569'))
        self.expand_btn.setFixedHeight(32)
        self.expand_btn.setToolTip("Zeilenhöhe anpassen, um lange Beschreibungen mehrzeilig auszuklappen")
        self.expand_btn.toggled.connect(self.toggle_row_expansion)
        batch_layout.addWidget(self.expand_btn)

        self.autofit_btn = QPushButton(" Spalten anpassen")
        self.autofit_btn.setObjectName("BtnAutofit")
        self.autofit_btn.setIcon(qta.icon('fa5s.arrows-alt-h', color='#475569'))
        self.autofit_btn.setFixedHeight(32)
        self.autofit_btn.setToolTip("Spaltenbreiten automatisch an die Textlänge anpassen")
        self.autofit_btn.clicked.connect(self.autofit_columns)
        batch_layout.addWidget(self.autofit_btn)
        
        batch_layout.addStretch()
        
        self.save_btn = QPushButton(" Speichern")
        self.save_btn.setObjectName("BtnSave")
        self.save_btn.setIcon(qta.icon('fa5s.save', color='white'))
        self.save_btn.setFixedHeight(32)
        self.save_btn.clicked.connect(self.save_data)
        batch_layout.addWidget(self.save_btn)
        
        self.add_btn = QPushButton(" Neu")
        self.add_btn.setObjectName("BtnAdd")
        self.add_btn.setIcon(qta.icon('fa5s.plus', color='white'))
        self.add_btn.setFixedHeight(32)
        self.add_btn.clicked.connect(self.add_new_entry)
        batch_layout.addWidget(self.add_btn)
        
        controls_layout.addLayout(batch_layout)
        self.main_layout.addWidget(self.controls_card)
        
        # --- 3. Data Area ---
        self.table_view = QTableView()
        self.table_model = CacheTableModel()
        self.table_view.setModel(self.table_model)
        
        self.checkbox_delegate = CenterCheckBoxDelegate(self.table_view)
        self.table_view.setItemDelegateForColumn(4, self.checkbox_delegate)
        
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_view.setSortingEnabled(True)
        self.table_view.setMouseTracking(True)
        self.table_view.doubleClicked.connect(self.on_table_double_clicked)
        
        self.main_layout.addWidget(self.table_view, stretch=1)
        
        self.current_data = {}

    def update_card_style(self):
        qapp = QApplication.instance()
        is_dark = bool(qapp and qapp.palette().window().color().lightness() < 128)
        
        card_bg = "#1f1f23" if is_dark else "#f8fafc"
        card_border = "#27272a" if is_dark else "#e2e8f0"
        input_bg = "#27272a" if is_dark else "white"
        input_border = "#3f3f46" if is_dark else "#cbd5e1"
        input_color = "#f4f4f5" if is_dark else "#1e293b"
        
        neutral_btn_bg = "#27272a" if is_dark else "white"
        neutral_btn_border = "#3f3f46" if is_dark else "#cbd5e1"
        neutral_btn_color = "#e4e4e7" if is_dark else "#475569"
        neutral_btn_hover = "#3f3f46" if is_dark else "#f1f5f9"
        neutral_btn_pressed = "#18181b" if is_dark else "#e2e8f0"
        
        checked_bg = "#1e3a5f" if is_dark else "#e0f2fe"
        checked_border = "#38bdf8" if is_dark else "#38bdf8"
        checked_color = "#38bdf8" if is_dark else "#0369a1"

        self.controls_card.setStyleSheet(f"""
            #ControlsCard {{
                background-color: {card_bg};
                border-radius: 12px;
                border: 1px solid {card_border};
            }}
            QComboBox {{
                padding: 6px 10px;
                border: 1px solid {input_border};
                border-radius: 6px;
                background-color: {input_bg};
                color: {input_color};
            }}
            QLineEdit {{
                padding: 6px 10px;
                border: 1px solid {input_border};
                border-radius: 6px;
                background-color: {input_bg};
                color: {input_color};
            }}
            QPushButton {{
                padding: 6px 15px;
                border-radius: 6px;
                font-weight: bold;
                border: none;
            }}
            QPushButton#BtnRefresh {{ background-color: {neutral_btn_bg}; border: 1px solid {neutral_btn_border}; color: {neutral_btn_color}; }}
            QPushButton#BtnRefresh:hover {{ background-color: {neutral_btn_hover}; }}
            QPushButton#BtnRefresh:pressed {{ background-color: {neutral_btn_pressed}; }}

            QPushButton#BtnSelectAll {{ background-color: {neutral_btn_bg}; border: 1px solid {neutral_btn_border}; color: {neutral_btn_color}; }}
            QPushButton#BtnSelectAll:hover {{ background-color: {neutral_btn_hover}; }}
            QPushButton#BtnSelectAll:pressed {{ background-color: {neutral_btn_pressed}; }}

            QPushButton#BtnExpand {{ background-color: {neutral_btn_bg}; border: 1px solid {neutral_btn_border}; color: {neutral_btn_color}; }}
            QPushButton#BtnExpand:hover {{ background-color: {neutral_btn_hover}; }}
            QPushButton#BtnExpand:checked {{ background-color: {checked_bg}; border: 1px solid {checked_border}; color: {checked_color}; }}

            QPushButton#BtnAutofit {{ background-color: {neutral_btn_bg}; border: 1px solid {neutral_btn_border}; color: {neutral_btn_color}; }}
            QPushButton#BtnAutofit:hover {{ background-color: {neutral_btn_hover}; }}
            QPushButton#BtnAutofit:pressed {{ background-color: {neutral_btn_pressed}; }}

            QPushButton#BtnConfirm {{ background-color: #2e9e63; color: white; }}
            QPushButton#BtnConfirm:hover {{ background-color: #278654; }}
            QPushButton#BtnConfirm:pressed {{ background-color: #1e6b43; }}

            QPushButton#BtnDelete {{ background-color: #cc0000; color: white; }}
            QPushButton#BtnDelete:hover {{ background-color: #b30000; }}
            QPushButton#BtnDelete:pressed {{ background-color: #800000; }}

            QPushButton#BtnSave {{ background-color: #e58e26; color: white; }}
            QPushButton#BtnSave:hover {{ background-color: #d18123; }}
            QPushButton#BtnSave:pressed {{ background-color: #b36e1e; }}

            QPushButton#BtnAdd {{ background-color: #3a7ebf; color: white; }}
            QPushButton#BtnAdd:hover {{ background-color: #326ca3; }}
            QPushButton#BtnAdd:pressed {{ background-color: #275682; }}
        """)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_card_style()

    def toggle_row_expansion(self, checked):
        qapp = QApplication.instance()
        is_dark = bool(qapp and qapp.palette().window().color().lightness() < 128)
        if checked:
            self.expand_btn.setText(" Einklappen")
            self.expand_btn.setIcon(qta.icon('fa5s.compress-alt', color='#38bdf8' if is_dark else '#3a7ebf'))
            self.table_view.setWordWrap(True)
            self.table_view.resizeRowsToContents()
        else:
            self.expand_btn.setText(" Ausklappen")
            self.expand_btn.setIcon(qta.icon('fa5s.expand-alt', color='#475569'))
            self.table_view.setWordWrap(False)
            self.table_view.verticalHeader().setDefaultSectionSize(36)
            for r in range(self.table_model.rowCount()):
                self.table_view.setRowHeight(r, 36)

    def autofit_columns(self):
        for c in range(self.table_model.columnCount()):
            self.table_view.resizeColumnToContents(c)
        if self.table_view.columnWidth(2) < 300:
            self.table_view.setColumnWidth(2, 300)

    def on_table_double_clicked(self, index):
        if not index.isValid():
            return
        col = index.column()
        row = index.row()
        client = self.get_client()
        if col in (1, 2):
            item = self.table_model._data[row]
            orig_val = item[4]
            dialog = CacheEntryDetailDialog(item, client or "", self)
            dialog.exec()
            val_updated = item[4]
            key = item[0]
            if key in self.current_data:
                self.current_data[key]['value'] = val_updated
            self.table_model.dataChanged.emit(index, index)
            if val_updated != orig_val:
                try:
                    db = get_db()
                    confirmed = item[1]
                    db.save_konten_cache_batch(client, {key: {'value': val_updated, 'confirmed': confirmed}})
                    self.show_status(f"Konto geändert und gespeichert: {val_updated}", "#2e9e63")
                except Exception as e:
                    self.show_status(f"Fehler beim Speichern: {e}", "red")
        elif col == 3:
            # Konten-Picker öffnen
            item = self.table_model._data[row]
            current_val = item[4]
            picker = KontoPickerDialog(self, client_name=client or "", current_konto=str(current_val))
            if picker.exec():
                new_konto = picker.get_selected_konto()
                item[4] = new_konto
                key = item[0]
                if key in self.current_data:
                    self.current_data[key]['value'] = new_konto
                idx = self.table_model.index(row, 3)
                self.table_model.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])
                
                # Auto-Save direkt in SQLite
                try:
                    db = get_db()
                    confirmed = item[1]
                    db.save_konten_cache_batch(client, {key: {'value': new_konto, 'confirmed': confirmed}})
                    self.show_status(f"Konto geändert und gespeichert: {new_konto}", "#2e9e63")
                except Exception as e:
                    self.show_status(f"Fehler beim Speichern: {e}", "red")
        
    def show_status(self, text, color="text"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")
        QTimer.singleShot(4000, lambda: self.status_label.setText(""))
        
    def toggle_select_all(self):
        if not self.table_model._data:
            return
        
        all_selected = all(row[6] for row in self.table_model._data)
        new_state = not all_selected
        
        for row in self.table_model._data:
            row[6] = new_state
            
        top_left = self.table_model.index(0, 4)
        bottom_right = self.table_model.index(len(self.table_model._data) - 1, 4)
        self.table_model.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole])

    def get_client(self):
        client = self.current_client_callback()
        if not client or client == "Kein Kunde":
            return None
        return client
        
    def load_data(self, *args):
        if getattr(self, 'is_dirty', False):
            reply = QMessageBox.question(
                self,
                "Ungespeicherte Änderungen",
                "Es gibt noch ungespeicherte Änderungen für diesen Kunden.\nMöchtest du diese vor dem Wechseln speichern?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )
            if reply == QMessageBox.StandardButton.Save:
                self.save_data()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
            self.is_dirty = False

        client = self.get_client()
        if not client:
            self.table_model.set_data([])
            self.show_status("Bitte zuerst einen Kunden auswählen!", "red")
            return
            
        try:
            db = get_db()
            cache_type = self.cache_type_var.currentText()
            self.current_data = db.get_konten_cache_full(client)
            self.display_map = get_konto_display_map(client)
        except Exception as e:
            self.show_status(f"Fehler: {e}", "red")
            return
            
        self.apply_filters_and_render()
        self.show_status("Daten geladen", "green")

    def apply_filters_and_render(self, *args):
        current_filter = self.filter_var.currentText()
        search_text = self.search_entry.text().lower().strip()
        display_map = getattr(self, 'display_map', {})
        
        table_data = []
        for key, data_obj in self.current_data.items():
            confirmed = data_obj['confirmed']
            value = data_obj['value']
            val_str = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
            
            # Automatisch mit Kontenbezeichnung anreichern
            val_str = format_konto_with_name(val_str, display_map)
            data_obj['value'] = val_str
            
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
                
            table_data.append([key, confirmed, lieferant, beschreibung, val_str, data_obj, False])
            
        # Default Sort by Lieferant A-Z
        table_data.sort(key=lambda x: x[2].lower())
        
        self.table_model.set_data(table_data)
        
        # Resize columns after populating
        self.table_view.resizeColumnToContents(0)
        if self.table_view.columnWidth(1) < 180:
            self.table_view.setColumnWidth(1, 180)
        self.table_view.setColumnWidth(3, 260)
        self.table_view.resizeColumnToContents(4)

        total_w = self.table_view.viewport().width()
        col0_w = self.table_view.columnWidth(0)
        col1_w = self.table_view.columnWidth(1)
        col3_w = self.table_view.columnWidth(3)
        col4_w = self.table_view.columnWidth(4)
        rem = total_w - (col0_w + col1_w + col3_w + col4_w) - 10
        self.table_view.setColumnWidth(2, max(380, rem))

        if hasattr(self, 'expand_btn') and self.expand_btn.isChecked():
            self.table_view.resizeRowsToContents()

    def get_selected_keys(self):
        keys = set()
        for row_data in self.table_model._data:
            if row_data[6]:
                keys.add(row_data[0]) 
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
                        val = val_str
                        break
                        
                new_entries[key] = {'value': val, 'confirmed': True}
                self.current_data[key]['confirmed'] = True
                self.current_data[key]['value'] = val
                
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
        if not client:
            return
        db = get_db()
        cache_type = self.cache_type_var.currentText()
        new_entries = {}
        
        for row_data in self.table_model._data:
            key = row_data[0]
            val_str = row_data[4]
            confirmed = row_data[1]
            try:
                parsed = val_str
                new_entries[key] = {'value': parsed, 'confirmed': confirmed}
                self.current_data[key]['value'] = parsed
            except:
                new_entries[key] = {'value': val_str, 'confirmed': confirmed}
                self.current_data[key]['value'] = val_str
                
        if new_entries:
            db.save_konten_cache_batch(client, new_entries)
                
        self.is_dirty = False
        self.show_status("Manuelle Änderungen gespeichert!", "green")
        self.apply_filters_and_render()

    def closeEvent(self, event):
        if getattr(self, 'is_dirty', False):
            reply = QMessageBox.question(
                self,
                "Ungespeicherte Änderungen",
                "Es gibt noch ungespeicherte Änderungen.\nMöchtest du diese vor dem Schließen speichern?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )
            if reply == QMessageBox.StandardButton.Save:
                self.save_data()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                self.is_dirty = False
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def add_new_entry(self):
        client = self.get_client()
        if not client:
            self.show_status("Bitte zuerst einen Kunden auswählen!", "red")
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Neuen Eintrag hinzufügen")
        dialog.resize(500, 320)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        layout = QFormLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        
        liefer_var = QLineEdit()
        layout.addRow("Lieferant (z.B. Hans):", liefer_var)
        
        desc_var = QLineEdit()
        layout.addRow("Beschreibung (z.B. Kuh 25.12.2006):", desc_var)
        
        # Konto mit Picker-Auswahl
        konto_bar = QHBoxLayout()
        val_var = QLineEdit()
        val_var.setPlaceholderText("Konto auswählen oder eingeben...")
        konto_bar.addWidget(val_var, stretch=1)
        
        btn_pick = QPushButton("🔍 Auswählen...")
        def open_picker():
            picker = KontoPickerDialog(dialog, client_name=client, current_konto=val_var.text().strip())
            if picker.exec():
                val_var.setText(picker.get_selected_konto())
        btn_pick.clicked.connect(open_picker)
        konto_bar.addWidget(btn_pick)
        
        layout.addRow("Konto / Kategorie:", konto_bar)
        
        def save():
            lieferant = liefer_var.text().strip()
            desc = desc_var.text().strip()
            val = val_var.text().strip()
            if not lieferant or not desc or not val:
                return
                
            key = f"{lieferant} | {desc}".upper()
            cache_type = self.cache_type_var.currentText()
            try:
                parsed_val = val
            except:
                parsed_val = val
                
            new_entry = {key: {'value': parsed_val, 'confirmed': True}}
            
            db = get_db()
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
