import os
import re
import queue
import logging
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QStackedWidget, QFileDialog, QLineEdit, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QFont, QPalette, QColor
import qtawesome as qta


from src.core.config import ConfigManager
from src.core.controller import AppController
from src.core.logger import setup_logger
from src.core.translations import translator

from src.ui.dashboard import DashboardFrame
from src.ui.settings import SettingsFrame

from src.ui.client_manager import ClientManager
from src.ui.tools import build_tool_frame
from Programme.KI_Training.Cache_Editor import CacheEditorFrame

logger = logging.getLogger(__name__)

# QObject for signals
class Signaller(QObject):
    log_signal = pyqtSignal(str)

class BuchhaltungApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.lang = self.config_manager.get("language", "DE")
        
        self.setWindowTitle("Buchhaltung Suite")
        self.resize(1100, 700)
        # Apply custom style.qss (or style_dark.qss)
        appearance = self.config_manager.get("appearance_mode", "Light")
        style_file = "style_dark.qss" if appearance == "Dark" else "style.qss"
        style_path = os.path.join(os.path.dirname(__file__), style_file)
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                QApplication.instance().setStyleSheet(f.read())

        base_kunden_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Kunden")
        self.controller = AppController(base_kunden_dir)
        
        self.print_queue = queue.Queue()
        setup_logger(self.print_queue)
        
        self.signaller = Signaller()
        self.signaller.log_signal.connect(self.handle_log_signal)

        # Drag & Drop support
        self.setAcceptDrops(True)
        
        # Main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.active_tool = None
        self.client_manager = ClientManager(self, self.controller, self.config_manager, self.on_client_changed)
        
        self._build_sidebar()
        self._build_container()

        self.refresh_clients()
        
        # Start queue processing
        self.process_print_queue()
        
        self.show_dashboard()

    def _build_sidebar(self):
        self.sidebar_frame = QWidget()
        self.sidebar_frame.setFixedWidth(240)
        
        self.sidebar_frame.setObjectName("SidebarFrame")
        
        self.sidebar_layout = QVBoxLayout(self.sidebar_frame)
        self.sidebar_layout.setContentsMargins(15, 20, 15, 20)
        self.sidebar_layout.setSpacing(10)
        
        self.main_layout.addWidget(self.sidebar_frame)

        self.logo_label = QLabel("Buchhaltung Suite")
        self.logo_label.setObjectName("SidebarTitle")
        self.sidebar_layout.addWidget(self.logo_label)

        # Dashboard Button
        self.btn_dashboard = QPushButton(" Dashboard")
        self.btn_dashboard.setObjectName("SidebarBtn")
        self.btn_dashboard.setIcon(qta.icon('fa5s.home', color='#8c98a4'))
        self.btn_dashboard.clicked.connect(self.show_dashboard)
        self.sidebar_layout.addWidget(self.btn_dashboard)

        # Client Section
        self.search_client_entry = QLineEdit()
        self.search_client_entry.setPlaceholderText("Kunden suchen...")
        self.search_client_entry.addAction(qta.icon('fa5s.search', color='#8c98a4'), QLineEdit.ActionPosition.LeadingPosition)
        self.search_client_entry.textChanged.connect(self.filter_clients)
        self.search_client_entry.editingFinished.connect(lambda: self.search_client_entry.setCursorPosition(0))
        
        client_search_layout = QHBoxLayout()
        client_search_layout.setContentsMargins(0,0,0,0)
        client_search_layout.addWidget(self.search_client_entry)
        
        btn_add_client = QPushButton("+")
        btn_add_client.setObjectName("ActionBtn")
        btn_add_client.setFixedWidth(30)
        btn_add_client.clicked.connect(lambda: self.client_manager.open_new_client_dialog())
        client_search_layout.addWidget(btn_add_client)
        
        self.sidebar_layout.addLayout(client_search_layout)
        
        self.client_scroll = QScrollArea()
        self.client_scroll.setWidgetResizable(True)
        self.client_scroll.setFixedHeight(150)
        self.client_list_widget = QWidget()
        self.client_list_layout = QVBoxLayout(self.client_list_widget)
        self.client_list_layout.setContentsMargins(0,0,0,0)
        self.client_list_layout.setSpacing(2)
        self.client_list_layout.addStretch() # keep buttons at top
        self.client_scroll.setWidget(self.client_list_widget)
        self.sidebar_layout.addWidget(self.client_scroll)
        
        self.btn_edit_client = QPushButton("Kunde bearbeiten")
        self.btn_edit_client.setObjectName("ActionBtn")
        self.btn_edit_client.clicked.connect(
            lambda: self.client_manager.open_new_client_dialog(edit_client_name=self.current_client) 
            if self.current_client and self.current_client != "Kein Kunde" else logger.error("\n❌ Bitte wähle zuerst einen Kunden aus!")
        )
        self.sidebar_layout.addWidget(self.btn_edit_client)

        # Tools Section
        lbl_tools = QLabel("WERKZEUGE")
        lbl_tools.setObjectName("SidebarSectionLabel")
        self.sidebar_layout.addWidget(lbl_tools)
        
        self.sidebar_btn_2 = QPushButton(translator.get(self.lang, 'btn_xml_to_excel'))
        self.sidebar_btn_2.setObjectName("SidebarBtn")
        self.sidebar_btn_2.setIcon(qta.icon('fa5s.file-excel', color='#8c98a4'))
        self.sidebar_btn_2.clicked.connect(lambda: self.show_tool('xml_to_excel'))
        self.sidebar_layout.addWidget(self.sidebar_btn_2)

        self.sidebar_btn_csv = QPushButton(translator.get(self.lang, 'btn_csv_to_excel', default='CSV zu Excel'))
        self.sidebar_btn_csv.setObjectName("SidebarBtn")
        self.sidebar_btn_csv.setIcon(qta.icon('fa5s.file-csv', color='#8c98a4'))
        self.sidebar_btn_csv.clicked.connect(lambda: self.show_tool('csv_to_excel'))
        self.sidebar_layout.addWidget(self.sidebar_btn_csv)

        self.sidebar_btn_3 = QPushButton(translator.get(self.lang, 'btn_buchung_erstellen'))
        self.sidebar_btn_3.setObjectName("SidebarBtn")
        self.sidebar_btn_3.setIcon(qta.icon('fa5s.edit', color='#8c98a4'))
        self.sidebar_btn_3.clicked.connect(lambda: self.show_tool('buchung_erstellen'))
        self.sidebar_layout.addWidget(self.sidebar_btn_3)
        


        # System Section
        lbl_system = QLabel("SYSTEM")
        lbl_system.setObjectName("SidebarSectionLabel")
        self.sidebar_layout.addWidget(lbl_system)

        self.sidebar_btn_5 = QPushButton("KI-Training (Cache)")
        self.sidebar_btn_5.setObjectName("SidebarBtn")
        self.sidebar_btn_5.setIcon(qta.icon('fa5s.database', color='#8c98a4'))
        self.sidebar_btn_5.clicked.connect(self.show_cache_editor)
        self.sidebar_layout.addWidget(self.sidebar_btn_5)

        self.sidebar_layout.addStretch()

        self.btn_settings = QPushButton(" Einstellungen")
        self.btn_settings.setObjectName("SettingsBtn")
        self.btn_settings.setIcon(qta.icon('fa5s.cog', color='#8c98a4'))
        self.btn_settings.clicked.connect(self.show_settings)
        self.sidebar_layout.addWidget(self.btn_settings)

    def _build_container(self):
        self.container = QStackedWidget()
        self.main_layout.addWidget(self.container, 1) # stretch 1

        self.dashboard_frame = DashboardFrame(self.container, self.config_manager, self.controller)
        self.container.addWidget(self.dashboard_frame)

        self.settings_frame = SettingsFrame(self.container, self.config_manager, self)
        self.container.addWidget(self.settings_frame)

        # Build Tool Frames
        self.tool_frames = {}
        for tool_id, has_setup in [('buchung_erstellen', False), ('xml_to_excel', False), ('csv_to_excel', False)]:
            frame = QWidget()
            lbl, btn_f, btn_d, btn_c, log_tb, prog_bar = build_tool_frame(frame, self, tool_id, has_setup)
            self.container.addWidget(frame)
            self.tool_frames[tool_id] = {
                'frame': frame, 'label': lbl, 'btn_f': btn_f, 'btn_d': btn_d, 'btn_c': btn_c, 'log': log_tb, 'prog': prog_bar
            }

        if CacheEditorFrame:
            self.cache_editor_frame = CacheEditorFrame(self.container, lambda: getattr(self.client_manager, 'current_client', None))
            self.container.addWidget(self.cache_editor_frame)
        else:
            self.cache_editor_frame = QWidget()
            layout = QVBoxLayout(self.cache_editor_frame)
            layout.addWidget(QLabel("Fehler: Cache_Editor.py nicht gefunden"))
            self.container.addWidget(self.cache_editor_frame)

    # --- Queue & Logging ---
    def process_print_queue(self):
        import threading
        def worker():
            while True:
                msg = self.print_queue.get()
                self.signaller.log_signal.emit(msg)
                
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        
    def handle_log_signal(self, msg):
        target_widget = None
        target_progress = None
        
        if self.active_tool in self.tool_frames:
            target_widget = self.tool_frames[self.active_tool]['log']
            target_progress = self.tool_frames[self.active_tool]['prog']
            
        match = re.search(r'\[PROGRESS:(\d+)\]', msg)
        if match and target_progress:
            percent = int(match.group(1))
            target_progress.setValue(percent)
            msg = re.sub(r'\[PROGRESS:\d+\]', '', msg).strip()
            if not msg:
                return
            msg += "\n"
            
        if target_widget:
            target_widget.insertPlainText(msg)
            target_widget.ensureCursorVisible()

    def reset_sidebar_buttons(self):
        buttons = [
            (self.btn_dashboard, 'dashboard'),
            (self.sidebar_btn_2, 'xml_to_excel'),
            (self.sidebar_btn_csv, 'csv_to_excel'),
            (self.sidebar_btn_3, 'buchung_erstellen'),

            (self.sidebar_btn_5, 'cache_editor'),
            (self.btn_settings, 'settings')
        ]
        
        for btn, tool_id in buttons:
            is_active = (self.active_tool == tool_id)
            btn.setProperty("active", "true" if is_active else "false")
            
            # Icon Farbe anpassen
            icon_name = None
            if btn == self.btn_dashboard: icon_name = 'fa5s.home'
            elif btn == self.sidebar_btn_2: icon_name = 'fa5s.file-excel'
            elif btn == self.sidebar_btn_csv: icon_name = 'fa5s.file-csv'
            elif btn == self.sidebar_btn_3: icon_name = 'fa5s.edit'

            elif btn == self.sidebar_btn_5: icon_name = 'fa5s.database'
            elif btn == self.btn_settings: icon_name = 'fa5s.cog'
            
            if icon_name:
                color = '#3a7ebf' if is_active else '#8c98a4'
                btn.setIcon(qta.icon(icon_name, color=color))
            
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def show_dashboard(self):
        self.container.setCurrentWidget(self.dashboard_frame)
        self.dashboard_frame.refresh()
        self.reset_sidebar_buttons()
        self.active_tool = 'dashboard'

    def show_tool(self, tool_id):
        self.active_tool = tool_id
        self.container.setCurrentWidget(self.tool_frames[tool_id]['frame'])
        self.reset_sidebar_buttons()
        logger.info(translator.get(self.lang, 'welcome_msg'))

    def show_cache_editor(self):
        self.active_tool = 'cache_editor'
        self.container.setCurrentWidget(self.cache_editor_frame)
        self.reset_sidebar_buttons()
        if hasattr(self.cache_editor_frame, 'load_data'):
            self.cache_editor_frame.load_data()

    def show_settings(self):
        self.active_tool = 'settings'
        self.container.setCurrentWidget(self.settings_frame)
        self.reset_sidebar_buttons()

    def change_language(self, choice):
        self.lang = choice
        self.config_manager.set("language", choice)
        
        self.sidebar_btn_2.setText(translator.get(self.lang, 'btn_xml_to_excel'))
        self.sidebar_btn_csv.setText(translator.get(self.lang, 'btn_csv_to_excel', default='CSV zu Excel'))
        self.sidebar_btn_3.setText(translator.get(self.lang, 'btn_buchung_erstellen'))

        self.settings_frame.update_ui_text(self.lang)
            
        for tid, t in self.tool_frames.items():
            lbl_key = 'drop_label_csv' if tid == 'csv_to_excel' else 'drop_label'
            t['label'].setText(translator.get(self.lang, lbl_key))
            t['btn_f'].setText(translator.get(self.lang, 'btn_files'))
            t['btn_d'].setText(translator.get(self.lang, 'btn_folder'))
            t['log'].clear()

        logger.info(translator.get(self.lang, 'welcome_msg'))

    def refresh_clients(self):
        self.client_manager.all_clients = self.controller.get_all_clients()
        
        if not self.client_manager.all_clients:
            self.current_client = None
            self.search_client_entry.setText("Kein Kunde")
            self.search_client_entry.setCursorPosition(0)
        else:
            saved_client = self.config_manager.get("last_client")
            if saved_client and saved_client in self.client_manager.all_clients:
                self.current_client = saved_client
            elif getattr(self, 'current_client', None) not in self.client_manager.all_clients:
                self.current_client = self.client_manager.all_clients[0]
                
            self.search_client_entry.setText(self.current_client)
            self.search_client_entry.setCursorPosition(0)
            self.on_client_changed(self.current_client)
            
        self.render_client_list()
        
    def render_client_list(self, filtered_clients=None):
        for i in reversed(range(self.client_list_layout.count())): 
            item = self.client_list_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
            elif item.spacerItem():
                self.client_list_layout.removeItem(item)
                
        clients_to_show = filtered_clients if filtered_clients is not None else self.client_manager.all_clients
        
        if not clients_to_show:
            self.client_list_layout.addWidget(QLabel("Kein Kunde gefunden"))
            self.client_list_layout.addStretch()
            return
            
        unconfirmed_set = set()
        try:
            import sys
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            prog_dir = os.path.join(base_dir, "Programme")
            if prog_dir not in sys.path:
                sys.path.append(prog_dir)
            from DatabaseManager import get_db
            unconfirmed_set = get_db().get_unconfirmed_status_for_all()
        except Exception as e:
            logger.error(f"Fehler beim Laden des Unbestätigt-Status: {e}")
            
        for c in clients_to_show:
            item_widget = QWidget()
            item_widget.setObjectName("ClientItem")
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(5, 5, 5, 5)
            
            # Avatar Icon
            avatar = QLabel()
            avatar.setPixmap(qta.icon('fa5s.user-circle', color='#8c98a4').pixmap(18, 18))
            item_layout.addWidget(avatar)
            
            # Name
            lbl_name = QLabel(c)
            lbl_name.setObjectName("ClientName")
            
            is_active = (c == self.current_client)
            item_widget.setProperty("active", "true" if is_active else "false")
            lbl_name.setProperty("active", "true" if is_active else "false")
            
            item_layout.addWidget(lbl_name)
            item_layout.addStretch()
            
            # Status Dot
            dot = QLabel()
            dot_color = '#cc0000' if c in unconfirmed_set else '#2e9e63'
            dot.setPixmap(qta.icon('fa5s.circle', color=dot_color).pixmap(8, 8))
            item_layout.addWidget(dot)
            
            # Make widget clickable
            item_widget.mousePressEvent = lambda event, name=c: self.select_client_from_list(name)
            item_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            
            self.client_list_layout.addWidget(item_widget)
            
        self.client_list_layout.addStretch()

    def filter_clients(self, text):
        query = text.lower()
        if not query:
            filtered = self.client_manager.all_clients
        else:
            filtered = [c for c in self.client_manager.all_clients if query in c.lower()]
        self.render_client_list(filtered_clients=filtered)

    def select_client_from_list(self, choice):
        self.search_client_entry.setText(choice)
        self.search_client_entry.setCursorPosition(0)
        self.on_client_changed(choice)
        self.render_client_list() 

    @property
    def current_client(self):
        return self.client_manager.current_client

    @current_client.setter
    def current_client(self, value):
        self.client_manager.current_client = value

    def on_client_changed(self, choice):
        if choice and choice != "Kein Kunde" and choice != "Kein Kunde gefunden":
            if choice not in self.client_manager.all_clients:
                self.refresh_clients()
                
            self.current_client = choice
            logger.info(f"\nKunde gewechselt zu: {self.current_client}")
            self.config_manager.set("last_client", self.current_client)
            self.config_manager.add_recent_client(self.current_client)
            if self.active_tool == 'dashboard':
                self.show_dashboard()
            elif self.active_tool == 'cache_editor':
                if hasattr(self, 'cache_editor_frame') and hasattr(self.cache_editor_frame, 'load_data'):
                    self.cache_editor_frame.load_data()
        else:
            self.current_client = None

    def get_initial_dir(self):
        if self.current_client and self.current_client != "Kein Kunde":
            rechnungen_dir = os.path.join(self.controller.base_kunden_dir, self.current_client, "Rechnungen")
            if os.path.exists(rechnungen_dir):
                return rechnungen_dir
        return os.getcwd()

    def select_files(self, tool_id=None):
        if tool_id:
            self.active_tool = tool_id
        initial_dir = self.get_initial_dir()
        files, _ = QFileDialog.getOpenFileNames(self, "Dateien auswählen", initial_dir)
        if files:
            self.process_paths(files)

    def select_folder(self, tool_id=None):
        if tool_id:
            self.active_tool = tool_id
        initial_dir = self.get_initial_dir()
        folder = QFileDialog.getExistingDirectory(self, "Ordner auswählen", initial_dir)
        if folder:
            self.process_paths([folder])

    def process_paths(self, paths, tool_id=None):
        if tool_id is None:
            tool_id = self.active_tool
            
        from PyQt6.QtCore import QTimer
            
        def on_start():
            if tool_id in self.tool_frames:
                QTimer.singleShot(0, lambda: self.tool_frames[tool_id]['btn_c'].show())

        def on_finish():
            if tool_id in self.tool_frames:
                QTimer.singleShot(0, lambda: self.tool_frames[tool_id]['btn_c'].hide())

        self.controller.process_paths(
            paths=paths,
            active_tool=tool_id,
            current_client=self.current_client,
            on_start=on_start,
            on_finish=on_finish
        )

    # --- Drag and Drop ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            paths.append(url.toLocalFile())
        if paths:
            self.process_paths(paths)

    def open_globale_begriffe(self):
        try:
            from Programme.GlobalTerms import ensure_global_terms_file, get_global_terms_path
            import subprocess
            import sys
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            ensure_global_terms_file(base_dir)
            
            setup_path = get_global_terms_path(base_dir)
            logger.info(f"Öffne {setup_path}...")
            if os.name == 'nt' or sys.platform == 'win32':
                os.startfile(setup_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', setup_path], check=True)
            else:
                subprocess.run(['xdg-open', setup_path], check=True)
        except Exception as e:
            logger.error(f"Fehler beim Öffnen der Globalen Begriffe: {e}")


