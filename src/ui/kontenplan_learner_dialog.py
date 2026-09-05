import os
import re
import asyncio
from typing import Dict, List, Any, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QRadioButton, QButtonGroup, QFileDialog, QFrame,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QStackedWidget, QWidget, QAbstractItemView,
    QLineEdit, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import qtawesome as qta

from src.core.kontenplan_learner import (
    parse_booking_excel,
    inspect_excel_file,
    synthesize_terms_for_chunk,
    clean_and_deduplicate_konto_terms,
    extract_existing_examples_from_desc,
    apply_confirmed_terms_to_kontenplan,
    get_gemini_api_key,
    get_base_dir
)
from src.ui.kontenplan_editor import parse_kontenplan


class LearnerWorker(QThread):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        excel_path: str,
        target_kontenplan_path: str,
        target_typ: str,
        selected_sheet: Optional[str] = None,
        col_konto: Optional[str] = None,
        col_desc: Optional[str] = None,
        col_supplier: Optional[str] = None
    ):
        super().__init__()
        self.excel_path = excel_path
        self.target_kontenplan_path = target_kontenplan_path
        self.target_typ = target_typ
        self.selected_sheet = selected_sheet
        self.col_konto = col_konto
        self.col_desc = col_desc
        self.col_supplier = col_supplier
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        try:
            asyncio.run(self._process())
        except Exception as e:
            self.error_signal.emit(str(e))

    async def _process(self):
        self.progress_signal.emit(5, "Lese Excel-Datei ein...")
        
        # 1. Excel parsen
        try:
            excel_data = parse_booking_excel(
                self.excel_path,
                target_typ=self.target_typ,
                selected_sheet=self.selected_sheet,
                col_konto=self.col_konto,
                col_desc=self.col_desc,
                col_supplier=self.col_supplier
            )
        except Exception as e:
            self.error_signal.emit(f"Fehler beim Lesen der Excel: {e}")
            return

        items_by_konto = excel_data.get("items_by_konto", {})
        if not items_by_konto:
            self.error_signal.emit("In der Excel-Datei wurden keine gültigen Buchungszeilen mit Konto gefunden.")
            return

        # 2. Bestehenden Kontenplan einlesen
        existing_konten_map = {}
        if os.path.exists(self.target_kontenplan_path):
            with open(self.target_kontenplan_path, "r", encoding="utf-8") as f:
                raw = f.read()
            entries = parse_kontenplan(raw)
            for e in entries:
                k = e.get("konto", "").strip()
                desc = e.get("beschreibung", "")
                existing_examples = extract_existing_examples_from_desc(desc)
                existing_konten_map[k] = {
                    "name": e.get("name", ""),
                    "desc": desc,
                    "existing_examples": existing_examples
                }

        # 3. Gemini Client initialisieren
        api_key = get_gemini_api_key()
        if not api_key:
            self.error_signal.emit(
                "Kein Gemini API-Schlüssel gefunden!\n"
                "Bitte trage deinen API-Schlüssel in den Einstellungen ein."
            )
            return

        try:
            from google import genai
            client = genai.Client(api_key=api_key)
        except Exception as e:
            self.error_signal.emit(f"Fehler beim Initialisieren des Gemini-Clients: {e}")
            return

        results = {}
        total_konten = len(items_by_konto)
        current_idx = 0

        # 4. Pro Konto in 50er Batches analysieren
        for konto_key, items in items_by_konto.items():
            if self.is_cancelled:
                return

            current_idx += 1
            pct = 10 + int((current_idx / total_konten) * 80)
            self.progress_signal.emit(
                pct, 
                f"Analysiere Konto {current_idx}/{total_konten}: {konto_key} ({len(items)} Positionen)..."
            )

            # Bestehende Beispiele für dieses Konto suchen
            matched_existing_info = None
            for ex_k, info in existing_konten_map.items():
                if konto_key.lower() in ex_k.lower() or ex_k.lower() in konto_key.lower():
                    matched_existing_info = info
                    break
                # Vergleiche reine Ziffern
                nums_input = re.findall(r'\d{4,}', konto_key)
                nums_existing = re.findall(r'\d{4,}', ex_k)
                if nums_input and nums_existing and nums_input[-1] == nums_existing[-1]:
                    matched_existing_info = info
                    break

            existing_examples = matched_existing_info["existing_examples"] if matched_existing_info else []
            is_new_konto = matched_existing_info is None

            # In Chunks von 50 Positionen an Gemini schicken
            chunk_size = 50
            raw_proposed_terms = []
            for i in range(0, len(items), chunk_size):
                if self.is_cancelled:
                    return
                chunk = items[i:i + chunk_size]
                terms = await synthesize_terms_for_chunk(client, konto_key, chunk)
                raw_proposed_terms.extend(terms)

            # Deduplizieren & Stufe 2 Bereinigung
            if raw_proposed_terms:
                cleaned_terms = await clean_and_deduplicate_konto_terms(
                    client=client,
                    konto_name=konto_key,
                    existing_terms=existing_examples,
                    raw_proposed_terms=raw_proposed_terms,
                    max_limit=20
                )
            else:
                cleaned_terms = []

            if cleaned_terms or is_new_konto:
                results[konto_key] = {
                    "is_new": is_new_konto,
                    "account_name": matched_existing_info["name"] if matched_existing_info else "",
                    "existing_examples": existing_examples,
                    "proposed_terms": cleaned_terms,
                    "item_count": len(items)
                }

        self.progress_signal.emit(100, "Analyse abgeschlossen!")
        self.finished_signal.emit(results)


class DropZone(QFrame):
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #3a7ebf;
                border-radius: 8px;
                background-color: rgba(58, 126, 191, 0.05);
            }
            QFrame:hover {
                background-color: rgba(58, 126, 191, 0.12);
            }
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            fpath = url.toLocalFile()
            if fpath.lower().endswith(('.xlsx', '.xls')):
                self.file_dropped.emit(fpath)
                break


class KontenplanLearnerDialog(QDialog):
    """
    Assistent zur KI-gestützten Extraktion von Kontenplan-Beispielen aus Buchungs-Excels.
    """
    kontenplan_updated = pyqtSignal()

    def __init__(
        self,
        parent=None,
        controller=None,
        initial_client: Optional[str] = None,
        initial_typ: str = "ER",
        initial_file_path: Optional[str] = None
    ):
        super().__init__(parent)
        self.controller = controller
        self.initial_client = initial_client
        self.initial_typ = initial_typ
        self.initial_file_path = initial_file_path

        self.selected_excel_path: Optional[str] = None
        self.excel_inspection: Optional[Dict[str, Any]] = None
        self.target_kontenplan_path: str = ""
        self.worker: Optional[LearnerWorker] = None
        self.learned_results: Dict[str, Any] = {}

        self.setWindowTitle("✨ KI-Beispiel-Generator für Kontenpläne")
        self.resize(940, 680)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self.init_ui()
        self.update_target_path()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        header_layout = QHBoxLayout()
        lbl_icon = QLabel()
        lbl_icon.setPixmap(qta.icon('fa5s.magic', color='#3a7ebf').pixmap(36, 36))
        header_layout.addWidget(lbl_icon)

        header_text_layout = QVBoxLayout()
        lbl_title = QLabel("KI-Beispiel-Generator für Kontenpläne")
        lbl_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl_sub = QLabel(
            "Lerne hochwertige, verallgemeinerte Beispielbegriffe direkt aus realen Buchungen "
            "und reichere den Kontenplan automatisch an."
        )
        lbl_sub.setStyleSheet("color: #71717a; font-size: 11px;")
        header_text_layout.addWidget(lbl_title)
        header_text_layout.addWidget(lbl_sub)
        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Trennlinie
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

        # Stacked Widget für Phasen
        self.stacked = QStackedWidget()
        main_layout.addWidget(self.stacked, stretch=1)

        # Step 1: Upload & Config
        self.page_setup = self._build_page_setup()
        self.stacked.addWidget(self.page_setup)

        # Step 2: Processing Progress
        self.page_progress = self._build_page_progress()
        self.stacked.addWidget(self.page_progress)

        # Step 3: Review Table
        self.page_review = self._build_page_review()
        self.stacked.addWidget(self.page_review)

        self.stacked.setCurrentIndex(0)

    # -------------------------------------------------------------
    # PAGE 1: SETUP & UPLOAD
    # -------------------------------------------------------------
    def _build_page_setup(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        # 1. Ziel-Auswahl Frame
        target_group = QFrame()
        target_group.setStyleSheet("QFrame { background-color: rgba(255,255,255,0.03); border: 1px solid #3f3f46; border-radius: 6px; padding: 8px; }")
        tgt_layout = QVBoxLayout(target_group)

        lbl_tgt_title = QLabel("1. Ziel-Kontenplan auswählen:")
        lbl_tgt_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        tgt_layout.addWidget(lbl_tgt_title)

        row1 = QHBoxLayout()
        self.radio_client = QRadioButton("Kunden-Kontenplan:")
        self.radio_global = QRadioButton("Globaler Standard / Vorlage:")
        self.radio_client.setChecked(True)

        self.btn_group_target = QButtonGroup(self)
        self.btn_group_target.addButton(self.radio_client)
        self.btn_group_target.addButton(self.radio_global)

        self.radio_client.toggled.connect(self.on_target_scope_changed)
        row1.addWidget(self.radio_client)

        self.combo_clients = QComboBox()
        self.combo_clients.setMinimumWidth(200)
        if self.controller:
            clients = self.controller.get_all_clients()
            self.combo_clients.addItems(clients)
            if self.initial_client and self.initial_client in clients:
                self.combo_clients.setCurrentText(self.initial_client)
        self.combo_clients.currentIndexChanged.connect(self.update_target_path)
        row1.addWidget(self.combo_clients)

        row1.addSpacing(20)
        row1.addWidget(self.radio_global)

        self.combo_templates = QComboBox()
        self.combo_templates.setMinimumWidth(160)
        if self.controller:
            templates = self.controller.get_available_templates()
            self.combo_templates.addItems(templates)
        self.combo_templates.setEnabled(False)
        self.combo_templates.currentIndexChanged.connect(self.update_target_path)
        row1.addWidget(self.combo_templates)
        row1.addStretch()

        tgt_layout.addLayout(row1)

        row2 = QHBoxLayout()
        lbl_typ = QLabel("Buchungsart:")
        row2.addWidget(lbl_typ)
        self.combo_typ = QComboBox()
        self.combo_typ.addItems(["Eingangsrechnungen (ER)", "Ausgangsrechnungen (AR)"])
        if self.initial_typ == "AR":
            self.combo_typ.setCurrentIndex(1)
        self.combo_typ.currentIndexChanged.connect(self.update_target_path)
        row2.addWidget(self.combo_typ)

        self.lbl_target_path = QLabel("")
        self.lbl_target_path.setStyleSheet("color: #a1a1aa; font-size: 10px;")
        row2.addSpacing(15)
        row2.addWidget(self.lbl_target_path)
        row2.addStretch()

        tgt_layout.addLayout(row2)
        layout.addWidget(target_group)

        # 2. Excel Upload Frame
        lbl_up_title = QLabel("2. Buchungs-Excel auswählen (z. B. Gesammelte_Buchungen.xlsx):")
        lbl_up_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(lbl_up_title)

        drop_zone = DropZone(self)
        drop_layout = QVBoxLayout(drop_zone)
        drop_layout.setContentsMargins(20, 25, 20, 25)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_drop_icon = QLabel()
        lbl_drop_icon.setPixmap(qta.icon('fa5s.file-excel', color='#3a7ebf').pixmap(42, 42))
        lbl_drop_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(lbl_drop_icon)

        lbl_drop_text = QLabel("Excel-Datei hierher ziehen oder durchsuchen...")
        lbl_drop_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_drop_text.setFont(QFont("Segoe UI", 10))
        drop_layout.addWidget(lbl_drop_text)

        btn_browse = QPushButton(" Datei auswählen...")
        btn_browse.setIcon(qta.icon('fa5s.folder-open', color='#ffffff'))
        btn_browse.setFixedWidth(160)
        btn_browse.clicked.connect(self.browse_excel)
        drop_layout.addWidget(btn_browse, alignment=Qt.AlignmentFlag.AlignCenter)

        drop_zone.file_dropped.connect(self.set_excel_file)
        layout.addWidget(drop_zone)

        # 3. Spalten- und Sheet-Zuordnung Frame (initial verborgen)
        self.mapping_group = self._build_mapping_widget()
        self.mapping_group.setVisible(False)
        layout.addWidget(self.mapping_group)

        # File Info Label
        self.lbl_file_info = QLabel("Keine Datei ausgewählt.")
        self.lbl_file_info.setStyleSheet("color: #71717a; font-style: italic;")
        layout.addWidget(self.lbl_file_info)

        layout.addStretch()

        # Action Button Bar
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(btn_cancel)

        self.btn_start = QPushButton("🚀 KI-Analyse & Beispiele generieren")
        self.btn_start.setEnabled(False)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 5px;
            }
            QPushButton:disabled {
                background-color: #3f3f46;
                color: #71717a;
            }
            QPushButton:hover:!disabled {
                background-color: #1d4ed8;
            }
        """)
        self.btn_start.clicked.connect(self.start_processing)
        btn_bar.addWidget(self.btn_start)

        layout.addLayout(btn_bar)
        return page

    def _build_mapping_widget(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("mappingFrame")
        frame.setStyleSheet("""
            QFrame#mappingFrame {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        f_layout = QVBoxLayout(frame)
        f_layout.setContentsMargins(10, 10, 10, 10)
        f_layout.setSpacing(10)

        # Header
        h_box = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(qta.icon('fa5s.table', color='#3a7ebf').pixmap(15, 15))
        h_box.addWidget(icon)
        lbl = QLabel("Spalten- & Sheet-Zuordnung:")
        lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        h_box.addWidget(lbl)
        h_box.addStretch()
        f_layout.addLayout(h_box)

        # Row 1: Sheet
        r1 = QHBoxLayout()
        lbl_sheet = QLabel("Tabellenblatt:")
        lbl_sheet.setFixedWidth(130)
        self.combo_sheet = QComboBox()
        self.combo_sheet.currentIndexChanged.connect(self.on_sheet_changed)
        r1.addWidget(lbl_sheet)
        r1.addWidget(self.combo_sheet, stretch=1)
        f_layout.addLayout(r1)

        # Row 2: Spalten
        r2 = QHBoxLayout()

        lbl_k = QLabel("Konto-Spalte:")
        lbl_k.setFixedWidth(130)
        self.combo_col_konto = QComboBox()
        self.combo_col_konto.currentIndexChanged.connect(lambda _: self.validate_and_preview_mapping())
        r2.addWidget(lbl_k)
        r2.addWidget(self.combo_col_konto, stretch=1)

        r2.addSpacing(15)

        lbl_d = QLabel("Beschreibung:")
        self.combo_col_desc = QComboBox()
        self.combo_col_desc.currentIndexChanged.connect(lambda _: self.validate_and_preview_mapping())
        r2.addWidget(lbl_d)
        r2.addWidget(self.combo_col_desc, stretch=1)

        r2.addSpacing(15)

        lbl_s = QLabel("Lieferant (opt.):")
        self.combo_col_supplier = QComboBox()
        self.combo_col_supplier.currentIndexChanged.connect(lambda _: self.validate_and_preview_mapping())
        r2.addWidget(lbl_s)
        r2.addWidget(self.combo_col_supplier, stretch=1)

        f_layout.addLayout(r2)
        return frame

    # -------------------------------------------------------------
    # PAGE 2: PROGRESS
    # -------------------------------------------------------------
    def _build_page_progress(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 40, 30, 40)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_spinner = QLabel()
        lbl_spinner.setPixmap(qta.icon('fa5s.cogs', color='#3a7ebf').pixmap(48, 48))
        lbl_spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_spinner)

        lbl_progress_title = QLabel("KI analysiert Buchungen...")
        lbl_progress_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_progress_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_progress_title)

        self.lbl_progress_detail = QLabel("Initialisiere...")
        self.lbl_progress_detail.setStyleSheet("color: #a1a1aa;")
        self.lbl_progress_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_progress_detail)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(22)
        layout.addWidget(self.progress_bar)

        layout.addSpacing(20)

        btn_cancel_worker = QPushButton("Abbrechen")
        btn_cancel_worker.setFixedWidth(120)
        btn_cancel_worker.clicked.connect(self.cancel_processing)
        layout.addWidget(btn_cancel_worker, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        return page

    # -------------------------------------------------------------
    # PAGE 3: REVIEW & CONFIRM
    # -------------------------------------------------------------
    def _build_page_review(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.lbl_review_summary = QLabel("")
        self.lbl_review_summary.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(self.lbl_review_summary)

        # Tabelle
        self.table_review = QTableWidget()
        self.table_review.setColumnCount(4)
        self.table_review.setHorizontalHeaderLabels([
            "Übernehmen", "Konto", "Bestehende Beispiele", "Neue Vorschläge (KI - doppelklicken zum Editieren)"
        ])
        self.table_review.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_review.setAlternatingRowColors(True)
        self.table_review.verticalHeader().setVisible(False)

        header = self.table_review.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table_review.setColumnWidth(0, 95)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table_review.setColumnWidth(1, 220)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table_review.setColumnWidth(2, 220)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table_review)

        # Toolbar
        bar = QHBoxLayout()
        btn_sel_all = QPushButton("☑️ Alle auswählen")
        btn_sel_all.clicked.connect(lambda: self.set_all_checkboxes(True))
        bar.addWidget(btn_sel_all)

        btn_desel_all = QPushButton("⬜ Alle abwählen")
        btn_desel_all.clicked.connect(lambda: self.set_all_checkboxes(False))
        bar.addWidget(btn_desel_all)

        btn_add_term = QPushButton("➕ Begriff hinzufügen")
        btn_add_term.clicked.connect(self.add_term_to_selected)
        bar.addWidget(btn_add_term)

        btn_delete_row = QPushButton("🗑️ Zeile verwerfen")
        btn_delete_row.clicked.connect(self.delete_selected_row)
        bar.addWidget(btn_delete_row)

        bar.addStretch()

        btn_back = QPushButton("Zurück")
        btn_back.clicked.connect(lambda: self.stacked.setCurrentIndex(0))
        bar.addWidget(btn_back)

        self.btn_apply = QPushButton("💾 In Kontenplan übernehmen")
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: white;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #15803d;
            }
        """)
        self.btn_apply.clicked.connect(self.apply_results)
        bar.addWidget(self.btn_apply)

        layout.addLayout(bar)
        return page

    # -------------------------------------------------------------
    # LOGIK & EVENTS
    # -------------------------------------------------------------
    def on_target_scope_changed(self):
        is_client = self.radio_client.isChecked()
        self.combo_clients.setEnabled(is_client)
        self.combo_templates.setEnabled(not is_client)
        self.update_target_path()

    def update_target_path(self):
        typ = "ER" if self.combo_typ.currentIndex() == 0 else "AR"
        if self.radio_client.isChecked():
            client_name = self.combo_clients.currentText().strip()
            if client_name and self.controller:
                self.target_kontenplan_path = os.path.join(
                    self.controller.base_kunden_dir, client_name, "Nutzerdaten", f"{typ}_Kontenplan.txt"
                )
            else:
                self.target_kontenplan_path = ""
        else:
            tpl_name = self.combo_templates.currentText().strip()
            if tpl_name and self.controller:
                self.target_kontenplan_path = self.controller.get_template_path(tpl_name, typ)
            else:
                self.target_kontenplan_path = ""

        if self.target_kontenplan_path:
            short_path = self.target_kontenplan_path
            if len(short_path) > 70:
                short_path = "..." + short_path[-67:]
            self.lbl_target_path.setText(f"Zieldatei: {short_path}")
        else:
            self.lbl_target_path.setText("Zieldatei: nicht definiert")

        # Falls bereits eine Datei geladen ist, bei Typwechsel (ER/AR) neu validieren
        if hasattr(self, 'selected_excel_path') and self.selected_excel_path and hasattr(self, 'combo_sheet'):
            if self.excel_inspection:
                try:
                    new_insp = inspect_excel_file(self.selected_excel_path, typ)
                    self.excel_inspection = new_insp
                    best_s = new_insp.get("best_sheet")
                    if best_s and best_s != self.combo_sheet.currentText():
                        self.combo_sheet.setCurrentText(best_s)
                except Exception:
                    pass
            self.validate_and_preview_mapping()

    def browse_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Buchungs-Excel auswählen", "", "Excel-Dateien (*.xlsx *.xls)"
        )
        if path:
            self.set_excel_file(path)

    def set_excel_file(self, path: str):
        self.selected_excel_path = path
        target_typ = "ER" if self.combo_typ.currentIndex() == 0 else "AR"
        try:
            self.excel_inspection = inspect_excel_file(path, target_typ)
            sheet_names = self.excel_inspection["sheet_names"]
            best_sheet = self.excel_inspection["best_sheet"]

            self.combo_sheet.blockSignals(True)
            self.combo_sheet.clear()
            self.combo_sheet.addItems(sheet_names)
            if best_sheet in sheet_names:
                self.combo_sheet.setCurrentText(best_sheet)
            self.combo_sheet.blockSignals(False)

            self._update_column_combos_for_sheet(best_sheet)
            self.mapping_group.setVisible(True)
            self.validate_and_preview_mapping()
        except Exception as e:
            self.lbl_file_info.setText(f"❌ Fehler bei der Analyse: {e}")
            self.lbl_file_info.setStyleSheet("color: #ef4444; font-size: 11px;")
            self.btn_start.setEnabled(False)

    def on_sheet_changed(self):
        sheet = self.combo_sheet.currentText().strip()
        if sheet and self.excel_inspection:
            self._update_column_combos_for_sheet(sheet)
            self.validate_and_preview_mapping()

    def _update_column_combos_for_sheet(self, sheet_name: str):
        if not self.excel_inspection:
            return
        sheet_meta = self.excel_inspection["sheets_info"].get(sheet_name, {})
        cols = sheet_meta.get("columns", [])

        self.combo_col_konto.blockSignals(True)
        self.combo_col_desc.blockSignals(True)
        self.combo_col_supplier.blockSignals(True)

        self.combo_col_konto.clear()
        self.combo_col_desc.clear()
        self.combo_col_supplier.clear()

        self.combo_col_konto.addItem("-- Bitte wählen --")
        self.combo_col_konto.addItems(cols)

        self.combo_col_desc.addItem("-- Bitte wählen --")
        self.combo_col_desc.addItems(cols)

        self.combo_col_supplier.addItem("(Keine / Optional)")
        self.combo_col_supplier.addItems(cols)

        col_k = sheet_meta.get("col_konto")
        if col_k and col_k in cols:
            self.combo_col_konto.setCurrentText(col_k)

        col_d = sheet_meta.get("col_desc")
        if col_d and col_d in cols:
            self.combo_col_desc.setCurrentText(col_d)

        col_s = sheet_meta.get("col_supplier")
        if col_s and col_s in cols:
            self.combo_col_supplier.setCurrentText(col_s)

        self.combo_col_konto.blockSignals(False)
        self.combo_col_desc.blockSignals(False)
        self.combo_col_supplier.blockSignals(False)

    def validate_and_preview_mapping(self):
        if not self.selected_excel_path:
            return

        sheet = self.combo_sheet.currentText().strip()
        col_konto = self.combo_col_konto.currentText().strip()
        if col_konto == "-- Bitte wählen --":
            col_konto = None

        col_desc = self.combo_col_desc.currentText().strip()
        if col_desc == "-- Bitte wählen --":
            col_desc = None

        col_supplier = self.combo_col_supplier.currentText().strip()
        if col_supplier.startswith("("):
            col_supplier = None

        target_typ = "ER" if self.combo_typ.currentIndex() == 0 else "AR"
        fname = os.path.basename(self.selected_excel_path)

        if not col_konto or not col_desc:
            if "xml" in fname.lower():
                self.lbl_file_info.setText(
                    f"ℹ️ <b>{fname}</b> | Enthält Rohdaten ohne Buchungskonten.<br>"
                    "Tipp: Verwende für den KI-Beispiel-Generator eine kontierte Datei wie z. B. <i>Gesammelte_Buchungen.xlsx</i>."
                )
                self.lbl_file_info.setStyleSheet("color: #eab308; font-size: 11px;")
            else:
                missing = []
                if not col_konto: missing.append("Konto-Spalte")
                if not col_desc: missing.append("Beschreibungs-Spalte")
                self.lbl_file_info.setText(
                    f"⚠️ <b>Zuordnung erforderlich:</b> Bitte wähle oben die {' und '.join(missing)} aus."
                )
                self.lbl_file_info.setStyleSheet("color: #eab308; font-size: 11px;")
            self.btn_start.setEnabled(False)
            return

        try:
            summary = parse_booking_excel(
                self.selected_excel_path,
                target_typ=target_typ,
                selected_sheet=sheet,
                col_konto=col_konto,
                col_desc=col_desc,
                col_supplier=col_supplier
            )
            konten_cnt = len(summary["items_by_konto"])
            rows_cnt = summary["valid_rows"]
            if konten_cnt == 0:
                self.lbl_file_info.setText(
                    f"⚠️ <b>{fname}</b> | Keine Positionen mit Kontonummer gefunden. "
                    f"(Alle Konten leer oder als '???' markiert)"
                )
                self.lbl_file_info.setStyleSheet("color: #eab308; font-size: 11px;")
                self.btn_start.setEnabled(False)
            else:
                supplier_info = f" | Lieferant: <b>{col_supplier}</b>" if col_supplier else ""
                self.lbl_file_info.setText(
                    f"✅ <b>{fname}</b> | Sheet: <i>{sheet}</i> | "
                    f"Konto: <b>{col_konto}</b> | Text: <b>{col_desc}</b>{supplier_info}<br>"
                    f"Erkannt: <b>{konten_cnt}</b> Konten mit <b>{rows_cnt}</b> Positionen bereit für KI-Analyse."
                )
                self.lbl_file_info.setStyleSheet("color: #22c55e; font-size: 11px;")
                self.btn_start.setEnabled(True)
        except Exception as e:
            self.lbl_file_info.setText(f"❌ Fehler bei der Analyse: {e}")
            self.lbl_file_info.setStyleSheet("color: #ef4444; font-size: 11px;")
            self.btn_start.setEnabled(False)

    def start_processing(self):
        if not self.selected_excel_path or not self.target_kontenplan_path:
            QMessageBox.warning(self, "Hinweis", "Bitte wähle eine Excel-Datei und einen Ziel-Kontenplan aus.")
            return

        target_typ = "ER" if self.combo_typ.currentIndex() == 0 else "AR"
        sheet = self.combo_sheet.currentText().strip()
        col_konto = self.combo_col_konto.currentText().strip()
        if col_konto == "-- Bitte wählen --":
            col_konto = None

        col_desc = self.combo_col_desc.currentText().strip()
        if col_desc == "-- Bitte wählen --":
            col_desc = None

        col_supplier = self.combo_col_supplier.currentText().strip()
        if col_supplier.startswith("("):
            col_supplier = None

        self.stacked.setCurrentIndex(1)
        self.progress_bar.setValue(0)
        self.lbl_progress_detail.setText("Starte KI-Batchverarbeitung...")

        self.worker = LearnerWorker(
            excel_path=self.selected_excel_path,
            target_kontenplan_path=self.target_kontenplan_path,
            target_typ=target_typ,
            selected_sheet=sheet,
            col_konto=col_konto,
            col_desc=col_desc,
            col_supplier=col_supplier
        )
        self.worker.progress_signal.connect(self.on_worker_progress)
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.error_signal.connect(self.on_worker_error)
        self.worker.start()

    def cancel_processing(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        self.stacked.setCurrentIndex(0)

    def on_worker_progress(self, pct: int, status: str):
        self.progress_bar.setValue(pct)
        self.lbl_progress_detail.setText(status)

    def on_worker_error(self, err: str):
        QMessageBox.critical(self, "Fehler", f"Bei der Generierung ist ein Fehler aufgetreten:\n\n{err}")
        self.stacked.setCurrentIndex(0)

    def on_worker_finished(self, results: Dict[str, Any]):
        self.learned_results = results
        self.populate_review_table()
        self.stacked.setCurrentIndex(2)

    def populate_review_table(self):
        self.table_review.setRowCount(0)
        total_terms = sum(len(d.get("proposed_terms", [])) for d in self.learned_results.values())
        konten_count = len(self.learned_results)

        self.lbl_review_summary.setText(
            f"Vorschau: {total_terms} neue Beispielbegriffe für {konten_count} Konten generiert."
        )

        for konto_key, data in self.learned_results.items():
            row = self.table_review.rowCount()
            self.table_review.insertRow(row)

            # Col 0: Checkbox
            item_check = QTableWidgetItem()
            item_check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item_check.setCheckState(Qt.CheckState.Checked)
            self.table_review.setItem(row, 0, item_check)

            # Col 1: Konto & Name (+ Badge falls neu)
            name = data.get("account_name", "")
            is_new = data.get("is_new", False)
            title = f"{konto_key}" + (f" – {name}" if name else "")
            if is_new:
                title = f"[NEU] {title}"
            item_konto = QTableWidgetItem(title)
            item_konto.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            if is_new:
                item_konto.setForeground(QColor("#eab308"))
            item_konto.setData(Qt.ItemDataRole.UserRole, konto_key)
            self.table_review.setItem(row, 1, item_konto)

            # Col 2: Bestehend
            existing = data.get("existing_examples", [])
            item_exist = QTableWidgetItem(", ".join(existing) if existing else "(Keine)")
            item_exist.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_exist.setForeground(QColor("#71717a"))
            self.table_review.setItem(row, 2, item_exist)

            # Col 3: Neue Vorschläge (editierbar)
            proposed = data.get("proposed_terms", [])
            item_prop = QTableWidgetItem(", ".join(proposed))
            item_prop.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
            )
            self.table_review.setItem(row, 3, item_prop)

    def set_all_checkboxes(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table_review.rowCount()):
            item = self.table_review.item(row, 0)
            if item:
                item.setCheckState(state)

    def add_term_to_selected(self):
        row = self.table_review.currentRow()
        if row < 0:
            QMessageBox.information(self, "Hinweis", "Bitte wähle zuerst eine Kontenzeile aus.")
            return

        text, ok = QInputDialog.getText(
            self, "Begriff hinzufügen", "Zusätzlicher Beispielbegriff für dieses Konto:"
        )
        if ok and text.strip():
            item_prop = self.table_review.item(row, 3)
            curr = item_prop.text().strip()
            new_text = f"{curr}, {text.strip()}" if curr else text.strip()
            item_prop.setText(new_text)

    def delete_selected_row(self):
        row = self.table_review.currentRow()
        if row >= 0:
            self.table_review.removeRow(row)

    def apply_results(self):
        confirmed_updates: Dict[str, Dict[str, Any]] = {}
        for row in range(self.table_review.rowCount()):
            item_check = self.table_review.item(row, 0)
            if item_check and item_check.checkState() == Qt.CheckState.Checked:
                item_konto = self.table_review.item(row, 1)
                konto_key = item_konto.data(Qt.ItemDataRole.UserRole) or item_konto.text().replace("[NEU] ", "").strip()
                item_prop = self.table_review.item(row, 3)
                raw_prop = item_prop.text().strip() if item_prop else ""
                
                terms = [t.strip() for t in raw_prop.split(",") if t.strip()]
                if terms:
                    orig_data = self.learned_results.get(konto_key, {})
                    confirmed_updates[konto_key] = {
                        "name": orig_data.get("account_name", ""),
                        "terms": terms,
                        "is_new": orig_data.get("is_new", False)
                    }

        if not confirmed_updates:
            QMessageBox.warning(self, "Hinweis", "Es wurden keine Konten zur Übernahme ausgewählt.")
            return

        success, msg, count = apply_confirmed_terms_to_kontenplan(
            target_kontenplan_path=self.target_kontenplan_path,
            confirmed_updates=confirmed_updates,
            max_limit=20
        )

        if success:
            QMessageBox.information(
                self, 
                "Erfolg", 
                f"Die Beispiele wurden erfolgreich in den Kontenplan geschrieben!\n\n"
                f"{msg}\n\n"
                f"Datei: {os.path.basename(self.target_kontenplan_path)}"
            )
            self.kontenplan_updated.emit()
            self.accept()
        else:
            QMessageBox.critical(self, "Fehler beim Speichern", msg)
