import os
import re
import queue
import logging
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD

from src.core.config import ConfigManager
from src.core.controller import AppController
from src.core.logger import setup_logger
from src.core.translations import translator
from src.ui.dashboard import DashboardFrame
from src.ui.client_manager import ClientManager
from src.ui.settings import SettingsFrame
from src.ui.tools import build_tool_frame

try:
    import Programme.KI_Training.Cache_Editor as Cache_Editor
    CacheEditorFrame = Cache_Editor.CacheEditorFrame
except ImportError:
    CacheEditorFrame = None

logger = logging.getLogger(__name__)
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

class TkDnD(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)

class BuchhaltungApp(TkDnD):
    def __init__(self):
        super().__init__()
        
        self.config_manager = ConfigManager()
        self.lang = self.config_manager.get("language", "DE")
        ctk.set_appearance_mode(self.config_manager.get("appearance_mode", "Light"))

        self.title("Buchhaltung Suite")
        self.geometry("1100x700")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        base_kunden_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Kunden")
        self.controller = AppController(base_kunden_dir)
        
        self.print_queue = queue.Queue()
        setup_logger(self.print_queue)

        self._build_sidebar()
        self._build_container()

        self.active_tool = None
        self.client_manager = ClientManager(self, self.controller, self.config_manager, self.on_client_changed)
        self.refresh_clients()

        self.process_print_queue()
        self.show_dashboard()

    def _build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(10, weight=1)
        self.sidebar_frame.grid_rowconfigure(11, weight=0)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Buchhaltung", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.btn_dashboard = ctk.CTkButton(self.sidebar_frame, text="🏠 Dashboard", command=self.show_dashboard, fg_color="transparent", border_width=1, text_color=("black", "white"))
        self.btn_dashboard.grid(row=1, column=0, padx=20, pady=(0, 10))

        # Client Selection area
        self.client_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.client_frame.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="nsew")
        
        search_frame = ctk.CTkFrame(self.client_frame, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 5))
        
        self.search_client_var = ctk.StringVar()
        self.search_client_entry = ctk.CTkEntry(search_frame, placeholder_text="Kunde suchen...", textvariable=self.search_client_var)
        self.search_client_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.search_client_entry.bind("<KeyRelease>", self.filter_clients)
        
        btn_add_client = ctk.CTkButton(search_frame, text="+", width=30, command=lambda: self.client_manager.open_new_client_dialog(), fg_color="#2b9e4a", hover_color="#217a39")
        btn_add_client.pack(side="right")
        
        self.client_list_frame = ctk.CTkScrollableFrame(self.client_frame, height=150, fg_color=("gray85", "gray20"))
        self.client_list_frame.pack(fill="both", expand=True, pady=(0, 5))
        
        self.btn_edit_client = ctk.CTkButton(self.client_frame, text="Kunde bearbeiten", command=lambda: self.client_manager.open_new_client_dialog(edit_client_name=self.current_client) if self.current_client and self.current_client != "Kein Kunde" else logger.error("\n❌ Bitte wähle zuerst einen Kunden aus!"), fg_color="#e58e26", hover_color="#b36916")
        self.btn_edit_client.pack(fill="x", pady=(5, 0))

        ctk.CTkLabel(self.sidebar_frame, text="WERKZEUGE", text_color="gray50", font=ctk.CTkFont(size=11, weight="bold")).grid(row=3, column=0, sticky="w", padx=25, pady=(15, 0))
        
        self.sidebar_btn_2 = ctk.CTkButton(self.sidebar_frame, text=translator.get(self.lang, 'btn_xml_to_excel'), command=lambda: self.show_tool('xml_to_excel'), text_color=("black", "white"))
        self.sidebar_btn_2.grid(row=4, column=0, padx=20, pady=(5, 10))

        self.sidebar_btn_csv = ctk.CTkButton(self.sidebar_frame, text=translator.get(self.lang, 'btn_csv_to_excel'), command=lambda: self.show_tool('csv_to_excel'), text_color=("black", "white"))
        self.sidebar_btn_csv.grid(row=5, column=0, padx=20, pady=(5, 10))

        self.sidebar_btn_3 = ctk.CTkButton(self.sidebar_frame, text=translator.get(self.lang, 'btn_buchung_erstellen'), command=lambda: self.show_tool('buchung_erstellen'), text_color=("black", "white"))
        self.sidebar_btn_3.grid(row=6, column=0, padx=20, pady=10)
        
        self.sidebar_btn_4 = ctk.CTkButton(self.sidebar_frame, text=translator.get(self.lang, 'btn_analyse'), command=lambda: self.show_tool('analyse'), text_color=("black", "white"))
        self.sidebar_btn_4.grid(row=7, column=0, padx=20, pady=10)

        ctk.CTkLabel(self.sidebar_frame, text="SYSTEM", text_color="gray50", font=ctk.CTkFont(size=11, weight="bold")).grid(row=8, column=0, sticky="w", padx=25, pady=(15, 0))

        self.sidebar_btn_5 = ctk.CTkButton(self.sidebar_frame, text="KI-Training (Cache)", command=self.show_cache_editor, text_color=("black", "white"))
        self.sidebar_btn_5.grid(row=9, column=0, padx=20, pady=(5, 10))

        self.btn_settings = ctk.CTkButton(self.sidebar_frame, text="⚙️ Einstellungen", command=self.show_settings, fg_color="transparent", border_width=1, text_color=("black", "white"))
        self.btn_settings.grid(row=11, column=0, padx=20, pady=(10, 20), sticky="s")

    def _build_container(self):
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.dashboard_frame = DashboardFrame(self.container, self.config_manager, self.controller)
        self.dashboard_frame.grid(row=0, column=0, sticky="nsew")

        self.settings_frame = SettingsFrame(self.container, self.config_manager, self)
        self.settings_frame.grid(row=0, column=0, sticky="nsew")

        # Build Tool Frames
        self.tool_frames = {}
        for tool_id, has_setup in [('buchung_erstellen', False), ('xml_to_excel', False), ('csv_to_excel', False), ('analyse', True)]:
            frame = ctk.CTkFrame(self.container, fg_color="transparent")
            frame.grid(row=0, column=0, sticky="nsew")
            lbl, btn_f, btn_d, btn_c, log_tb, prog_bar = build_tool_frame(frame, self, tool_id, has_setup)
            self.tool_frames[tool_id] = {
                'frame': frame, 'label': lbl, 'btn_f': btn_f, 'btn_d': btn_d, 'btn_c': btn_c, 'log': log_tb, 'prog': prog_bar
            }

        if CacheEditorFrame:
            self.cache_editor_frame = CacheEditorFrame(self.container, lambda: getattr(self.client_manager, 'current_client', None))
            self.cache_editor_frame.grid(row=0, column=0, sticky="nsew")
        else:
            self.cache_editor_frame = ctk.CTkFrame(self.container)
            self.cache_editor_frame.grid(row=0, column=0, sticky="nsew")
            ctk.CTkLabel(self.cache_editor_frame, text="Fehler: Cache_Editor.py nicht gefunden").pack(expand=True)

    def process_print_queue(self):
        while not self.print_queue.empty():
            try:
                msg = self.print_queue.get_nowait()
                target_widget = None
                target_progress = None
                
                if self.active_tool in self.tool_frames:
                    target_widget = self.tool_frames[self.active_tool]['log']
                    target_progress = self.tool_frames[self.active_tool]['prog']
                    
                match = re.search(r'\[PROGRESS:(\d+)\]', msg)
                if match and target_progress:
                    percent = int(match.group(1)) / 100.0
                    target_progress.set(percent)
                    msg = re.sub(r'\[PROGRESS:\d+\]', '', msg).strip()
                    if not msg:
                        continue
                    msg += "\n"
                    
                if target_widget:
                    target_widget.configure(state="normal")
                    target_widget.insert("end", msg)
                    target_widget.see("end")
                    target_widget.configure(state="disabled")
            except queue.Empty:
                break
        self.after(100, self.process_print_queue)

    def hide_all_frames(self):
        self.dashboard_frame.grid_remove()
        self.settings_frame.grid_remove()
        for t in self.tool_frames.values():
            t['frame'].grid_remove()
        self.cache_editor_frame.grid_remove()
        
    def reset_sidebar_buttons(self):
        self.btn_dashboard.configure(fg_color="transparent")
        self.sidebar_btn_2.configure(fg_color="transparent")
        self.sidebar_btn_3.configure(fg_color="transparent")
        self.sidebar_btn_4.configure(fg_color="transparent")
        self.sidebar_btn_csv.configure(fg_color="transparent")
        self.sidebar_btn_5.configure(fg_color="transparent")
        self.btn_settings.configure(fg_color="transparent")

    def show_dashboard(self):
        self.hide_all_frames()
        self.dashboard_frame.grid()
        self.dashboard_frame.refresh()
        self.reset_sidebar_buttons()
        self.btn_dashboard.configure(fg_color=("gray75", "gray25"))
        self.active_tool = 'dashboard'

    def show_tool(self, tool_id):
        self.active_tool = tool_id
        self.hide_all_frames()
        self.tool_frames[tool_id]['frame'].grid()
        self.reset_sidebar_buttons()
        
        if tool_id == 'xml_to_excel': self.sidebar_btn_2.configure(fg_color=("gray75", "gray25"))
        elif tool_id == 'csv_to_excel': self.sidebar_btn_csv.configure(fg_color=("gray75", "gray25"))
        elif tool_id == 'buchung_erstellen': self.sidebar_btn_3.configure(fg_color=("gray75", "gray25"))
        elif tool_id == 'analyse': self.sidebar_btn_4.configure(fg_color=("gray75", "gray25"))
        
        logger.info(translator.get(self.lang, 'welcome_msg'))

    def show_cache_editor(self):
        self.active_tool = 'cache_editor'
        self.hide_all_frames()
        self.cache_editor_frame.grid()
        self.reset_sidebar_buttons()
        self.sidebar_btn_5.configure(fg_color=("gray75", "gray25"))
        if hasattr(self.cache_editor_frame, 'load_data'):
            self.cache_editor_frame.load_data()

    def show_settings(self):
        self.active_tool = 'settings'
        self.hide_all_frames()
        self.settings_frame.grid()
        self.reset_sidebar_buttons()
        self.btn_settings.configure(fg_color=("gray75", "gray25"))

    def change_language(self, choice):
        self.lang = choice
        self.config_manager.set("language", choice)
        
        self.sidebar_btn_2.configure(text=translator.get(self.lang, 'btn_xml_to_excel'))
        self.sidebar_btn_csv.configure(text=translator.get(self.lang, 'btn_csv_to_excel', default='CSV zu Excel'))
        self.sidebar_btn_3.configure(text=translator.get(self.lang, 'btn_buchung_erstellen'))
        self.sidebar_btn_4.configure(text=translator.get(self.lang, 'btn_analyse'))
        self.settings_frame.update_ui_text(self.lang)
        
        for tid, t in self.tool_frames.items():
            lbl_key = 'drop_label_csv' if tid == 'csv_to_excel' else 'drop_label'
            t['label'].configure(text=translator.get(self.lang, lbl_key))
            t['btn_f'].configure(text=translator.get(self.lang, 'btn_files'))
            t['btn_d'].configure(text=translator.get(self.lang, 'btn_folder'))
            t['log'].configure(state="normal")
            t['log'].delete("1.0", "end")
            t['log'].configure(state="disabled")
            
        logger.info(translator.get(self.lang, 'welcome_msg'))

    def refresh_clients(self):
        self.client_manager.all_clients = self.controller.get_all_clients()
        
        if not self.client_manager.all_clients:
            self.current_client = None
            self.search_client_var.set("Kein Kunde")
        else:
            saved_client = self.config_manager.get("last_client")
            if saved_client and saved_client in self.client_manager.all_clients:
                self.current_client = saved_client
            elif getattr(self, 'current_client', None) not in self.client_manager.all_clients:
                self.current_client = self.client_manager.all_clients[0]
                
            self.search_client_var.set(self.current_client)
            self.on_client_changed(self.current_client)
            
        self.render_client_list()
        
    def render_client_list(self, filtered_clients=None):
        for w in self.client_list_frame.winfo_children():
            w.destroy()
            
        clients_to_show = filtered_clients if filtered_clients is not None else self.client_manager.all_clients
        
        if not clients_to_show:
            ctk.CTkLabel(self.client_list_frame, text="Kein Kunde gefunden").pack(pady=10)
            return
            
        for c in clients_to_show:
            is_active = (c == self.current_client)
            color = ("#3a7ebf", "#1f538d") if is_active else "transparent"
            text_color = "white" if is_active else ("black", "white")
            
            btn = ctk.CTkButton(
                self.client_list_frame, 
                text=c, 
                fg_color=color, 
                text_color=text_color, 
                anchor="w",
                command=lambda name=c: self.select_client_from_list(name)
            )
            btn.pack(fill="x", pady=1)

    def filter_clients(self, event=None):
        if event and event.keysym in ('Up', 'Down', 'Return', 'Escape', 'Tab'):
            return
            
        query = self.search_client_var.get().lower()
        if not query:
            filtered = self.client_manager.all_clients
        else:
            filtered = [c for c in self.client_manager.all_clients if query in c.lower()]
            
        self.render_client_list(filtered_clients=filtered)

    def select_client_from_list(self, choice):
        self.search_client_var.set(choice)
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
            # Wenn der Kunde noch nicht in der Liste ist (z.B. neu angelegt), Liste neu laden
            if choice not in self.client_manager.all_clients:
                self.refresh_clients()
                
            self.current_client = choice
            logger.info(f"\nKunde gewechselt zu: {self.current_client}")
            self.config_manager.set("last_client", self.current_client)
            self.config_manager.add_recent_client(self.current_client)
            if self.active_tool == 'dashboard':
                self.show_dashboard()
        else:
            self.current_client = None

    def get_initial_dir(self):
        if self.current_client and self.current_client != "Kein Kunde":
            rechnungen_dir = os.path.join(self.controller.base_kunden_dir, self.current_client, "Rechnungen")
            if os.path.exists(rechnungen_dir):
                return rechnungen_dir
        return os.getcwd()

    def select_files(self, tool_id):
        if tool_id == 'csv_to_excel':
            filetypes = (('CSV Dateien', '*.csv'), ('Alle Dateien', '*.*'))
            title = 'Wähle CSV Dateien aus'
        else:
            filetypes = (('Rechnungen (XML/P7M)', '*.xml *.p7m'), ('Alle Dateien', '*.*'))
            title = 'Wähle XML/P7M Dateien aus'
            
        initial_dir = self.get_initial_dir()
        filenames = ctk.filedialog.askopenfilenames(title=title, filetypes=filetypes, initialdir=initial_dir)
        if filenames:
            self.process_paths(list(filenames), tool_id)
            
    def select_folder(self, tool_id):
        initial_dir = self.get_initial_dir()
        folder_path = ctk.filedialog.askdirectory(title='Wähle einen Ordner mit Rechnungen aus', initialdir=initial_dir)
        if folder_path:
            self.process_paths([folder_path], tool_id)

    def process_paths(self, paths, tool_id=None):
        if tool_id is None:
            tool_id = self.active_tool
            
        def on_start():
            if tool_id in self.tool_frames:
                self.tool_frames[tool_id]['btn_c'].grid()

        def on_finish():
            if tool_id in self.tool_frames:
                self.tool_frames[tool_id]['btn_c'].grid_remove()

        self.controller.process_paths(
            paths=paths,
            active_tool=tool_id,
            current_client=self.current_client,
            on_start=on_start,
            on_finish=on_finish
        )

    def parse_dropped_paths(self, data):
        paths = []
        if '{' in data:
            paths = re.findall(r'\{(.*?)\}', data)
            remaining = re.sub(r'\{.*?\}', '', data).strip()
            if remaining:
                paths.extend(remaining.split())
        else:
            paths = data.split()
        return paths

    def drop_event(self, event):
        paths = self.parse_dropped_paths(event.data)
        if paths:
            self.process_paths(paths)

    def open_globale_begriffe(self):
        try:
            from Programme.GlobalTerms import ensure_global_terms_file, get_global_terms_path
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
