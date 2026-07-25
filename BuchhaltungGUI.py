import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD
import os
import sys
import threading
import re
import queue
import subprocess
import logging

# Modulpfade hinzufügen, damit die Unterordner erkannt werden
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
sys.path.append(os.path.join(script_dir, 'Programme', 'Buchungen erstellen'))
sys.path.append(os.path.join(script_dir, 'Programme', 'XML zu Excel'))
sys.path.append(os.path.join(script_dir, 'Programme', 'Analyse erstellen'))
sys.path.append(os.path.join(script_dir, 'Programme', 'KI_Training'))
sys.path.append(os.path.join(script_dir, 'Programme', 'CSV zu Excel'))

from config import ConfigManager
from logger import setup_logger
from controller import AppController

logger = logging.getLogger(__name__)

try:
    import Analyse_Config
except ImportError as e:
    print("Fehler beim Import von Analyse_Config:", e)
    Analyse_Config = None

try:
    from Cache_Editor import CacheEditorFrame
except ImportError as e:
    print("Fehler beim Import von Cache_Editor:", e)
    CacheEditorFrame = None

# CustomTkinter Theme
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# TkinterDnD wrapper for CustomTkinter
class TkDnD(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)



TRANSLATIONS = {
    'DE': {
        'btn_csv_to_excel': 'CSV zu Excel',
        'btn_xml_to_excel': 'XML zu Excel',
        'btn_buchung_erstellen': 'Buchung erstellen',
        'btn_analyse': 'Analyse erstellen',
        'drop_label': 'Ordner oder XML/P7M Dateien hier ablegen\n(Drag & Drop)',
        'btn_files': 'Dateien auswählen',
        'btn_folder': 'Ordner auswählen',
        'welcome_msg': 'Willkommen bei der Buchhaltungs Suite!\nZiehe deine Dateien oder Ordner einfach in den Bereich oben.',
        'switch_dark': 'Dark Mode'
    },
    'IT': {
        'btn_csv_to_excel': 'CSV a Excel',
        'btn_xml_to_excel': 'XML a Excel',
        'btn_buchung_erstellen': 'Crea Registrazioni',
        'btn_analyse': 'Crea Analisi',
        'drop_label': 'Trascina qui file XML/P7M o cartelle\n(Drag & Drop)',
        'btn_files': 'Seleziona file',
        'btn_folder': 'Seleziona cartelle',
        'welcome_msg': 'Benvenuto nella Suite di Contabilità!\nTrascina i tuoi file o cartelle nell\'area in alto.',
        'switch_dark': 'Modalità Scura'
    }
}

class BuchhaltungApp(TkDnD):
    def __init__(self):
        super().__init__()
        
        self.config_manager = ConfigManager()
        self.lang = self.config_manager.get("language", "DE")
        ctk.set_appearance_mode(self.config_manager.get("appearance_mode", "Light"))

        self.title("Buchhaltung Suite")
        self.geometry("1100x700")

        # Set grid layout 1x2
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(10, weight=1)
        self.sidebar_frame.grid_rowconfigure(11, weight=0)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Buchhaltung", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.btn_dashboard = ctk.CTkButton(self.sidebar_frame, text="🏠 Dashboard", command=self.show_dashboard, fg_color="transparent", border_width=1, text_color=("black", "white"))
        self.btn_dashboard.grid(row=1, column=0, padx=20, pady=(0, 10))

        # --- Client Selection ---
        self.client_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.client_frame.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="nsew")
        
        search_frame = ctk.CTkFrame(self.client_frame, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 5))
        
        self.search_client_var = ctk.StringVar()
        self.search_client_entry = ctk.CTkEntry(search_frame, placeholder_text="Kunde suchen...", textvariable=self.search_client_var)
        self.search_client_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.search_client_entry.bind("<KeyRelease>", self.filter_clients)
        
        btn_add_client = ctk.CTkButton(search_frame, text="+", width=30, command=self.open_new_client_dialog, fg_color="#2b9e4a", hover_color="#217a39")
        btn_add_client.pack(side="right")
        
        self.client_list_frame = ctk.CTkScrollableFrame(self.client_frame, height=150, fg_color=("gray85", "gray20"))
        self.client_list_frame.pack(fill="both", expand=True, pady=(0, 5))
        
        self.btn_edit_client = ctk.CTkButton(self.client_frame, text="Kunde bearbeiten", command=self.open_edit_client_dialog, fg_color="#e58e26", hover_color="#b36916")
        self.btn_edit_client.pack(fill="x", pady=(5, 0))

        ctk.CTkLabel(self.sidebar_frame, text="WERKZEUGE", text_color="gray50", font=ctk.CTkFont(size=11, weight="bold")).grid(row=3, column=0, sticky="w", padx=25, pady=(15, 0))
        
        self.sidebar_btn_2 = ctk.CTkButton(self.sidebar_frame, text=TRANSLATIONS[self.lang]['btn_xml_to_excel'], command=self.show_xml_to_excel, text_color=("black", "white"))
        self.sidebar_btn_2.grid(row=4, column=0, padx=20, pady=(5, 10))

        self.sidebar_btn_csv = ctk.CTkButton(self.sidebar_frame, text=TRANSLATIONS[self.lang].get('btn_csv_to_excel', 'CSV zu Excel'), command=self.show_csv_to_excel, text_color=("black", "white"))
        self.sidebar_btn_csv.grid(row=5, column=0, padx=20, pady=(5, 10))

        self.sidebar_btn_3 = ctk.CTkButton(self.sidebar_frame, text=TRANSLATIONS[self.lang]['btn_buchung_erstellen'], command=self.show_buchung_erstellen, text_color=("black", "white"))
        self.sidebar_btn_3.grid(row=6, column=0, padx=20, pady=10)
        
        self.sidebar_btn_4 = ctk.CTkButton(self.sidebar_frame, text=TRANSLATIONS[self.lang]['btn_analyse'], command=self.show_analyse, text_color=("black", "white"))
        self.sidebar_btn_4.grid(row=7, column=0, padx=20, pady=10)

        ctk.CTkLabel(self.sidebar_frame, text="SYSTEM", text_color="gray50", font=ctk.CTkFont(size=11, weight="bold")).grid(row=8, column=0, sticky="w", padx=25, pady=(15, 0))

        self.sidebar_btn_5 = ctk.CTkButton(self.sidebar_frame, text="KI-Training (Cache)", command=self.show_cache_editor, text_color=("black", "white"))
        self.sidebar_btn_5.grid(row=9, column=0, padx=20, pady=(5, 10))

        self.btn_settings = ctk.CTkButton(self.sidebar_frame, text="⚙️ Einstellungen", command=self.show_settings, fg_color="transparent", border_width=1, text_color=("black", "white"))
        self.btn_settings.grid(row=11, column=0, padx=20, pady=(10, 20), sticky="s")

        # --- Container (Right Side) ---
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        # --- Frames ---
        self.build_dashboard_frame()
        self.build_settings_frame()
        self.build_xml_to_excel_frame()
        self.build_csv_to_excel_frame()
        self.build_buchung_erstellen_frame()
        self.build_analyse_frame()
        self.build_cache_editor_frame()

        self.base_kunden_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Kunden")
        self.controller = AppController(self.base_kunden_dir)
        
        self.current_client = None
        self.all_clients = []
        
        self.active_tool = None
        
        self.print_queue = queue.Queue()
        setup_logger(self.print_queue)
        
        self.refresh_clients()
        self.process_print_queue()
        
        # Startansicht
        self.show_dashboard()

    def process_print_queue(self):
        while not self.print_queue.empty():
            try:
                msg = self.print_queue.get_nowait()
                target_widget = None
                target_progress = None
                if self.active_tool == 'buchung_erstellen':
                    target_widget = getattr(self, "log_textbox", None)
                    target_progress = getattr(self, "progress_bar_buchung", None)
                elif self.active_tool == 'xml_to_excel':
                    target_widget = getattr(self, "xml2ex_log_textbox", None)
                    target_progress = getattr(self, "progress_bar_xml", None)
                elif self.active_tool == 'analyse':
                    target_widget = getattr(self, "analyse_log_textbox", None)
                    target_progress = getattr(self, "progress_bar_analyse", None)
                elif self.active_tool == 'csv_to_excel':
                    target_widget = getattr(self, "csv2ex_log_textbox", None)
                    target_progress = getattr(self, "progress_bar_csv", None)
                    
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

    def build_tool_frame(self, parent_frame, has_setup=False):
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(1, weight=1)

        drop_frame = ctk.CTkFrame(parent_frame, fg_color=("gray75", "gray25"), corner_radius=15)
        drop_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        drop_frame.grid_columnconfigure(0, weight=1)
        drop_frame.grid_rowconfigure(0, weight=1)
        drop_frame.grid_rowconfigure(1, weight=1)
        drop_frame.grid_rowconfigure(2, weight=1)
        
        drop_label = ctk.CTkLabel(drop_frame, text=TRANSLATIONS[self.lang]['drop_label'], font=ctk.CTkFont(size=16))
        drop_label.grid(row=0, column=0, pady=(20, 10), sticky="s")
        
        btn_frame = ctk.CTkFrame(drop_frame, fg_color="transparent")
        btn_frame.grid(row=1, column=0, pady=(10, 20), sticky="n")
        
        btn_files = ctk.CTkButton(btn_frame, text=TRANSLATIONS[self.lang]['btn_files'], command=self.select_files)
        btn_files.grid(row=0, column=0, padx=10)
        
        btn_folder = ctk.CTkButton(btn_frame, text=TRANSLATIONS[self.lang]['btn_folder'], command=self.select_folder)
        btn_folder.grid(row=0, column=1, padx=10)
        
        btn_setup = None
        if has_setup:
            btn_setup = ctk.CTkButton(btn_frame, text="Kategorien-Setup öffnen", command=self.open_analyse_setup, fg_color="#c85a17", hover_color="#a84b13")
            btn_setup.grid(row=0, column=2, padx=10)
            
        btn_cancel = ctk.CTkButton(btn_frame, text="Abbrechen & Speichern", command=self.cancel_task, fg_color="red", hover_color="darkred")
        btn_cancel.grid(row=0, column=3 if has_setup else 2, padx=10)
        btn_cancel.grid_remove()

        log_textbox = ctk.CTkTextbox(parent_frame, height=200)
        log_textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 5))
        log_textbox.configure(state="disabled")

        progress_bar = ctk.CTkProgressBar(parent_frame, height=10)
        progress_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        progress_bar.set(0)

        drop_frame.drop_target_register(DND_FILES)
        drop_frame.dnd_bind('<<Drop>>', self.drop_event)
        
        return drop_label, btn_files, btn_folder, btn_cancel, log_textbox, progress_bar

    def build_buchung_erstellen_frame(self):
        self.buchung_erstellen_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.buchung_erstellen_frame.grid(row=0, column=0, sticky="nsew")
        self.drop_label, self.btn_files, self.btn_folder, self.btn_cancel_buchung, self.log_textbox, self.progress_bar_buchung = self.build_tool_frame(self.buchung_erstellen_frame)

    def build_xml_to_excel_frame(self):
        self.xml_to_excel_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.xml_to_excel_frame.grid(row=0, column=0, sticky="nsew")
        self.xml2ex_drop_label, self.xml2ex_btn_files, self.xml2ex_btn_folder, _, self.xml2ex_log_textbox, self.progress_bar_xml = self.build_tool_frame(self.xml_to_excel_frame)

    def build_csv_to_excel_frame(self):
        self.csv_to_excel_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.csv_to_excel_frame.grid(row=0, column=0, sticky="nsew")
        self.csv2ex_drop_label, self.csv2ex_btn_files, self.csv2ex_btn_folder, self.csv2ex_btn_cancel, self.csv2ex_log_textbox, self.progress_bar_csv = self.build_tool_frame(self.csv_to_excel_frame)
        self.csv2ex_drop_label.configure(text="CSV Dateien (z.B. Shopify) hier ablegen\\n(Drag & Drop)")

    def build_analyse_frame(self):
        self.analyse_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.analyse_frame.grid(row=0, column=0, sticky="nsew")
        self.analyse_drop_label, self.analyse_btn_files, self.analyse_btn_folder, self.btn_cancel_analyse, self.analyse_log_textbox, self.progress_bar_analyse = self.build_tool_frame(self.analyse_frame, has_setup=True)

    def open_analyse_setup(self):
        if not self.current_client or self.current_client == "Kein Kunde":
            logger.error("\n❌ Bitte wähle zuerst einen Kunden in der Seitenleiste aus!")
            return
            
        client_dir = os.path.join(self.base_kunden_dir, self.current_client)
        nutzerdaten_dir = os.path.join(client_dir, "Nutzerdaten")
        setup_path = os.path.join(nutzerdaten_dir, "Analyse_Setup.xlsx")
        
        if Analyse_Config:
            Analyse_Config.ensure_setup_file(nutzerdaten_dir)
            
            logger.info(f"Öffne {setup_path}...")
            if os.name == 'nt' or sys.platform == 'win32':
                os.startfile(setup_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', setup_path], check=True)
            else:
                subprocess.run(['xdg-open', setup_path], check=True)
        else:
            print("Analyse_Config.py konnte nicht importiert werden.")

    def open_globale_begriffe(self):
        try:
            from Programme.GlobalTerms import ensure_global_terms_file, get_global_terms_path
            base_dir = os.path.dirname(os.path.abspath(__file__))
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

    def build_cache_editor_frame(self):
        if CacheEditorFrame:
            self.cache_editor_frame = CacheEditorFrame(self.container, lambda: self.current_client)
            self.cache_editor_frame.grid(row=0, column=0, sticky="nsew")
        else:
            self.cache_editor_frame = ctk.CTkFrame(self.container)
            self.cache_editor_frame.grid(row=0, column=0, sticky="nsew")
            ctk.CTkLabel(self.cache_editor_frame, text="Fehler: Cache_Editor.py nicht gefunden").pack(expand=True)
            
    def show_cache_editor(self):
        self.active_tool = 'cache_editor'
        self.hide_all_frames()
        self.cache_editor_frame.grid()
        self.reset_sidebar_buttons()
        self.sidebar_btn_5.configure(fg_color=("gray75", "gray25"))
        if hasattr(self.cache_editor_frame, 'load_data'):
            self.cache_editor_frame.load_data()

    def hide_all_frames(self):
        self.dashboard_frame.grid_remove()
        self.settings_frame.grid_remove()
        self.xml_to_excel_frame.grid_remove()
        self.buchung_erstellen_frame.grid_remove()
        self.analyse_frame.grid_remove()
        self.csv_to_excel_frame.grid_remove()
        self.cache_editor_frame.grid_remove()
        
    def reset_sidebar_buttons(self):
        self.btn_dashboard.configure(fg_color="transparent")
        self.sidebar_btn_2.configure(fg_color="transparent")
        self.sidebar_btn_3.configure(fg_color="transparent")
        self.sidebar_btn_4.configure(fg_color="transparent")
        self.sidebar_btn_5.configure(fg_color="transparent")
        if hasattr(self, 'sidebar_btn_csv'):
            self.sidebar_btn_csv.configure(fg_color="transparent")
        self.btn_settings.configure(fg_color="transparent")

    def show_xml_to_excel(self):
        self.active_tool = 'xml_to_excel'
        self.hide_all_frames()
        self.xml_to_excel_frame.grid()
        self.reset_sidebar_buttons()
        self.sidebar_btn_2.configure(fg_color=("gray75", "gray25"))
        logger.info(TRANSLATIONS[self.lang]['welcome_msg'])

    def show_csv_to_excel(self):
        self.active_tool = 'csv_to_excel'
        self.hide_all_frames()
        self.csv_to_excel_frame.grid()
        self.reset_sidebar_buttons()
        if hasattr(self, 'sidebar_btn_csv'):
            self.sidebar_btn_csv.configure(fg_color=("gray75", "gray25"))
        logger.info(TRANSLATIONS[self.lang]['welcome_msg'])

    def show_buchung_erstellen(self):
        self.active_tool = 'buchung_erstellen'
        self.hide_all_frames()
        self.buchung_erstellen_frame.grid()
        self.reset_sidebar_buttons()
        self.sidebar_btn_3.configure(fg_color=("gray75", "gray25"))
        logger.info(TRANSLATIONS[self.lang]['welcome_msg'])

    def show_analyse(self):
        self.active_tool = 'analyse'
        self.hide_all_frames()
        self.analyse_frame.grid()
        self.reset_sidebar_buttons()
        self.sidebar_btn_4.configure(fg_color=("gray75", "gray25"))
        logger.info(TRANSLATIONS[self.lang]['welcome_msg'])

    def change_language(self, choice):
        self.lang = choice
        self.config_manager.set("language", choice)
        t = TRANSLATIONS[self.lang]
        self.sidebar_btn_2.configure(text=t['btn_xml_to_excel'])
        self.sidebar_btn_3.configure(text=t['btn_buchung_erstellen'])
        self.sidebar_btn_4.configure(text=t['btn_analyse'])
        self.appearance_mode_switch.configure(text=t['switch_dark'])
        self.drop_label.configure(text=t['drop_label'])
        self.btn_files.configure(text=t['btn_files'])
        self.btn_folder.configure(text=t['btn_folder'])
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        
        self.xml2ex_drop_label.configure(text=t['drop_label'])
        self.xml2ex_btn_files.configure(text=t['btn_files'])
        self.xml2ex_btn_folder.configure(text=t['btn_folder'])
        self.xml2ex_log_textbox.configure(state="normal")
        self.xml2ex_log_textbox.delete("1.0", "end")
        self.xml2ex_log_textbox.configure(state="disabled")
        
        self.analyse_drop_label.configure(text=t['drop_label'])
        self.analyse_btn_files.configure(text=t['btn_files'])
        self.analyse_btn_folder.configure(text=t['btn_folder'])
        self.analyse_log_textbox.configure(state="normal")
        self.analyse_log_textbox.delete("1.0", "end")
        self.analyse_log_textbox.configure(state="disabled")
        
        logger.info(t['welcome_msg'])


    def toggle_appearance_mode(self):
        mode = self.appearance_mode_switch.get()
        new_mode = "Dark" if mode == 1 else "Light"
        ctk.set_appearance_mode(new_mode)
        self.config_manager.set("appearance_mode", new_mode)
        
    def create_backup_gui(self):
        import tkinter.messagebox
        success = self.controller.create_backup()
        if success:
            tkinter.messagebox.showinfo("Backup", "Backup wird im Hintergrund erstellt. Siehe Logfenster für Details.")
        else:
            tkinter.messagebox.showerror("Backup Fehler", "Fehler beim Starten des Backups.")

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

    def get_initial_dir(self):
        if self.current_client and self.current_client != "Kein Kunde":
            rechnungen_dir = os.path.join(self.base_kunden_dir, self.current_client, "Rechnungen")
            if os.path.exists(rechnungen_dir):
                return rechnungen_dir
        return os.getcwd()

    def select_files(self):
        if self.active_tool == 'csv_to_excel':
            filetypes = (('CSV Dateien', '*.csv'), ('Alle Dateien', '*.*'))
            title = 'Wähle CSV Dateien aus'
        else:
            filetypes = (('Rechnungen (XML/P7M)', '*.xml *.p7m'), ('Alle Dateien', '*.*'))
            title = 'Wähle XML/P7M Dateien aus'
            
        initial_dir = self.get_initial_dir()
        filenames = ctk.filedialog.askopenfilenames(title=title, filetypes=filetypes, initialdir=initial_dir)
        if filenames:
            self.process_paths(list(filenames))
            
    def select_folder(self):
        initial_dir = self.get_initial_dir()
        folder_path = ctk.filedialog.askdirectory(title='Wähle einen Ordner mit Rechnungen aus', initialdir=initial_dir)
        if folder_path:
            self.process_paths([folder_path])

    def process_paths(self, paths):
        def on_start():
            if self.active_tool == 'buchung_erstellen':
                self.btn_cancel_buchung.grid()
            elif self.active_tool == 'analyse':
                self.btn_cancel_analyse.grid()

        def on_finish():
            if self.active_tool == 'buchung_erstellen':
                self.btn_cancel_buchung.grid_remove()
            elif self.active_tool == 'analyse':
                self.btn_cancel_analyse.grid_remove()

        self.controller.process_paths(
            paths=paths,
            active_tool=self.active_tool,
            current_client=self.current_client,
            on_start=on_start,
            on_finish=on_finish
        )

    def cancel_task(self):
        self.controller.cancel_task()

    def refresh_clients(self):
        self.all_clients = self.controller.get_all_clients()
        
        if not self.all_clients:
            self.current_client = None
            self.search_client_var.set("Kein Kunde")
        else:
            saved_client = self.config_manager.get("last_client")
            if saved_client and saved_client in self.all_clients:
                self.current_client = saved_client
            elif self.current_client not in self.all_clients:
                self.current_client = self.all_clients[0]
                
            self.search_client_var.set(self.current_client)
            self.on_client_changed(self.current_client)
            
        self.render_client_list()
        
    def render_client_list(self, filtered_clients=None):
        for w in self.client_list_frame.winfo_children():
            w.destroy()
            
        clients_to_show = filtered_clients if filtered_clients is not None else self.all_clients
        
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
        # Ignore navigation keys
        if event and event.keysym in ('Up', 'Down', 'Return', 'Escape', 'Tab'):
            return
            
        query = self.search_client_var.get().lower()
        if not query:
            filtered = self.all_clients
        else:
            filtered = [c for c in self.all_clients if query in c.lower()]
            
        self.render_client_list(filtered_clients=filtered)

    def select_client_from_list(self, choice):
        self.search_client_var.set(choice)
        self.on_client_changed(choice)
        self.render_client_list() # Update active color

    def on_client_changed(self, choice):
        if choice and choice != "Kein Kunde" and choice != "Kein Kunde gefunden":
            self.current_client = choice
            logger.info(f"\nKunde gewechselt zu: {self.current_client}")
            self.config_manager.set("last_client", self.current_client)
            self.config_manager.add_recent_client(self.current_client)
            if getattr(self, "active_tool", None) == 'dashboard':
                self.show_dashboard()
        else:
            self.current_client = None

    def open_edit_client_dialog(self):
        if not self.current_client or self.current_client == "Kein Kunde":
            logger.error("\n❌ Bitte wähle zuerst einen Kunden aus, den du bearbeiten möchtest!")
            return
        self.open_new_client_dialog(edit_client_name=self.current_client)

    def open_new_client_dialog(self, edit_client_name=None):
        is_edit = edit_client_name is not None
        dialog = ctk.CTkToplevel(self)
        dialog.title("Kunde bearbeiten" if is_edit else "Neuer Kunde")
        dialog.geometry("500x600")
        dialog.attributes('-topmost', 'true')
        
        lbl = ctk.CTkLabel(dialog, text=f"Kunde '{edit_client_name}' bearbeiten" if is_edit else "Neuen Kunden anlegen", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=(15, 5))
        
        tabview = ctk.CTkTabview(dialog, width=450, height=450)
        tabview.pack(pady=10, padx=20, fill="both", expand=True)
        
        tabview.add("Basis & KI")
        tabview.add("Steuerdaten")
        tabview.add("Buchhaltung")
        tabview.add("Kontakt")
        
        # --- Tab 1: Basis & KI ---
        lbl_name = ctk.CTkLabel(tabview.tab("Basis & KI"), text="Firmenname (Ordnername) *")
        lbl_name.pack(anchor="w", padx=10, pady=(10, 0))
        name_entry = ctk.CTkEntry(tabview.tab("Basis & KI"), width=400)
        name_entry.pack(padx=10, pady=(0, 10))
        
        lbl_forma = ctk.CTkLabel(tabview.tab("Basis & KI"), text="Rechtsform")
        lbl_forma.pack(anchor="w", padx=10)
        forma_combo = ctk.CTkOptionMenu(tabview.tab("Basis & KI"), values=["Srl", "SpA", "snc", "sas", "Ditta Individuale", "Libero Professionista", "Altro"], width=400)
        forma_combo.pack(padx=10, pady=(0, 10))
        forma_combo.set("Srl")
        
        # KI-Kontenplan Template
        if not is_edit:
            lbl_template = ctk.CTkLabel(tabview.tab("Basis & KI"), text="Kontenplan Vorlage (ER & AR)")
            lbl_template.pack(anchor="w", padx=10)
            template_combo = ctk.CTkOptionMenu(tabview.tab("Basis & KI"), values=["Codice_Civile_2424", "Standard"], width=400)
            template_combo.pack(padx=10, pady=(0, 10))
            template_combo.set("Codice_Civile_2424")
        else:
            def open_editor(typ, title):
                editor = ctk.CTkToplevel(dialog)
                editor.title(f"{title}: {edit_client_name}")
                editor.geometry("600x500")
                editor.attributes('-topmost', 'true')
                
                # Zwingt das Fenster, strikt im Vordergrund von 'dialog' zu bleiben
                editor.transient(dialog)
                # Blockiert alle Eingaben für die Fenster darunter
                editor.grab_set()
                
                txt = ctk.CTkTextbox(editor, width=550, height=400)
                txt.pack(padx=20, pady=20)
                
                file_path = os.path.join(self.base_kunden_dir, edit_client_name, "Nutzerdaten", f"{typ}_Kontenplan.txt")
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        txt.insert("1.0", f.read())
                        
                def save_txt():
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(txt.get("1.0", "end-1c"))
                    editor.destroy()
                    print(f"{title} für {edit_client_name} gespeichert.")
                    
                btn_s = ctk.CTkButton(editor, text="Speichern", command=save_txt)
                btn_s.pack()

            frame_btns = ctk.CTkFrame(tabview.tab("Basis & KI"), fg_color="transparent")
            frame_btns.pack(padx=10, pady=(0, 10), fill="x")
            
            btn_edit_er = ctk.CTkButton(frame_btns, text="ER-Kontenplan bearbeiten", command=lambda: open_editor("ER", "ER-Kontenplan"), fg_color="#c85a17", hover_color="#a84b13", width=190)
            btn_edit_er.pack(side="left", padx=(0, 5))
            
            btn_edit_ar = ctk.CTkButton(frame_btns, text="AR-Kontenplan bearbeiten", command=lambda: open_editor("AR", "AR-Kontenplan"), fg_color="#c85a17", hover_color="#a84b13", width=190)
            btn_edit_ar.pack(side="left", padx=(5, 0))

        lbl_desc = ctk.CTkLabel(tabview.tab("Basis & KI"), text="Beschreibung (Wichtig für KI)")
        lbl_desc.pack(anchor="w", padx=10)
        desc_text = ctk.CTkTextbox(tabview.tab("Basis & KI"), width=400, height=150)
        desc_text.pack(padx=10, pady=(0, 10))
        
        # --- Tab 2: Steuerdaten ---
        lbl_piva = ctk.CTkLabel(tabview.tab("Steuerdaten"), text="Partita IVA (MwSt.-Nummer) *")
        lbl_piva.pack(anchor="w", padx=10, pady=(10, 0))
        piva_entry = ctk.CTkEntry(tabview.tab("Steuerdaten"), width=400)
        piva_entry.pack(padx=10, pady=(0, 10))
        
        lbl_cf = ctk.CTkLabel(tabview.tab("Steuerdaten"), text="Codice Fiscale")
        lbl_cf.pack(anchor="w", padx=10)
        cf_entry = ctk.CTkEntry(tabview.tab("Steuerdaten"), width=400)
        cf_entry.pack(padx=10, pady=(0, 10))
        
        # --- Tab 3: Buchhaltung ---
        lbl_regime = ctk.CTkLabel(tabview.tab("Buchhaltung"), text="Regime Contabile")
        lbl_regime.pack(anchor="w", padx=10, pady=(10, 0))
        regime_combo = ctk.CTkOptionMenu(tabview.tab("Buchhaltung"), values=["Ordinaria", "Semplificata", "Forfettario"], width=400)
        regime_combo.pack(padx=10, pady=(0, 10))
        regime_combo.set("Ordinaria")
        
        lbl_liq = ctk.CTkLabel(tabview.tab("Buchhaltung"), text="Liquidazione IVA")
        lbl_liq.pack(anchor="w", padx=10)
        liq_combo = ctk.CTkOptionMenu(tabview.tab("Buchhaltung"), values=["Mensile", "Trimestrale"], width=400)
        liq_combo.pack(padx=10, pady=(0, 10))
        liq_combo.set("Mensile")
        
        # --- Tab 4: Kontakt ---
        lbl_addr = ctk.CTkLabel(tabview.tab("Kontakt"), text="Adresse (Sede Legale)")
        lbl_addr.pack(anchor="w", padx=10, pady=(10, 0))
        addr_entry = ctk.CTkEntry(tabview.tab("Kontakt"), width=400)
        addr_entry.pack(padx=10, pady=(0, 10))
        
        lbl_pec = ctk.CTkLabel(tabview.tab("Kontakt"), text="PEC")
        lbl_pec.pack(anchor="w", padx=10)
        pec_entry = ctk.CTkEntry(tabview.tab("Kontakt"), width=400)
        pec_entry.pack(padx=10, pady=(0, 10))
        
        lbl_sdi = ctk.CTkLabel(tabview.tab("Kontakt"), text="Codice Destinatario (SDI)")
        lbl_sdi.pack(anchor="w", padx=10)
        sdi_entry = ctk.CTkEntry(tabview.tab("Kontakt"), width=400)
        sdi_entry.pack(padx=10, pady=(0, 10))
        
        lbl_iban = ctk.CTkLabel(tabview.tab("Kontakt"), text="IBAN")
        lbl_iban.pack(anchor="w", padx=10)
        iban_entry = ctk.CTkEntry(tabview.tab("Kontakt"), width=400)
        iban_entry.pack(padx=10, pady=(0, 10))
        
        if is_edit:
            name_entry.insert(0, edit_client_name)
            name_entry.configure(state="disabled")
            
            data = self.controller.get_client_data(edit_client_name)
            if data:
                if "Rechtsform" in data and data["Rechtsform"]: forma_combo.set(data["Rechtsform"])
                if "Beschreibung" in data and data["Beschreibung"]: 
                    desc_text.delete("1.0", "end")
                    desc_text.insert("1.0", data["Beschreibung"])
                if "Partita_IVA" in data and data["Partita_IVA"]: piva_entry.insert(0, data["Partita_IVA"])
                if "Codice_Fiscale" in data and data["Codice_Fiscale"]: cf_entry.insert(0, data["Codice_Fiscale"])
                if "Regime_Contabile" in data and data["Regime_Contabile"]: regime_combo.set(data["Regime_Contabile"])
                if "Liquidazione_IVA" in data and data["Liquidazione_IVA"]: liq_combo.set(data["Liquidazione_IVA"])
                if "Adresse" in data and data["Adresse"]: addr_entry.insert(0, data["Adresse"])
                if "PEC" in data and data["PEC"]: pec_entry.insert(0, data["PEC"])
                if "SDI" in data and data["SDI"]: sdi_entry.insert(0, data["SDI"])
                if "IBAN" in data and data["IBAN"]: iban_entry.insert(0, data["IBAN"])
        
        error_label = ctk.CTkLabel(dialog, text="", text_color="red")
        error_label.pack(pady=(5, 0))

        def save_client():
            error_label.configure(text="")
            name_raw = name_entry.get().strip()
            if not name_raw:
                error_label.configure(text="Fehler: Firmenname darf nicht leer sein!")
                return
                
            client_data = {
                "Kundenname": name_raw,
                "Rechtsform": forma_combo.get(),
                "Beschreibung": desc_text.get("1.0", "end").strip(),
                "Partita_IVA": piva_entry.get().strip(),
                "Codice_Fiscale": cf_entry.get().strip(),
                "Regime_Contabile": regime_combo.get(),
                "Liquidazione_IVA": liq_combo.get(),
                "Adresse": addr_entry.get().strip(),
                "PEC": pec_entry.get().strip(),
                "SDI": sdi_entry.get().strip(),
                "IBAN": iban_entry.get().strip()
            }
            template_name = template_combo.get() if not is_edit else None
            
            success, final_name = self.controller.save_client(name_raw, is_edit, client_data, template_name)
            if success:
                if not is_edit:
                    self.refresh_clients()
                    self.select_client_from_list(final_name)
                dialog.destroy()
            else:
                error_label.configure(text=f"Fehler: {final_name}")

        btn_save = ctk.CTkButton(dialog, text="Speichern", command=save_client)
        btn_save.pack(pady=10)


    def build_dashboard_frame(self):
        self.dashboard_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.dashboard_frame.grid(row=0, column=0, sticky="nsew")
        self.dashboard_frame.grid_columnconfigure((0, 1), weight=1)
        
        title = ctk.CTkLabel(self.dashboard_frame, text="Dashboard", font=ctk.CTkFont(size=28, weight="bold"))
        title.grid(row=0, column=0, columnspan=2, pady=(20, 30), sticky="w", padx=20)
        
        # Stats Cards Container
        stats_frame = ctk.CTkFrame(self.dashboard_frame, fg_color="transparent")
        stats_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20)
        stats_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # Client Count Card
        self.card_clients = ctk.CTkFrame(stats_frame, corner_radius=15, fg_color=("white", "gray20"), border_width=1, border_color=("gray85", "gray15"))
        self.card_clients.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(self.card_clients, text="Gesamte Kunden", font=ctk.CTkFont(size=14)).pack(pady=(15, 5))
        self.lbl_client_count = ctk.CTkLabel(self.card_clients, text="-", font=ctk.CTkFont(size=32, weight="bold"))
        self.lbl_client_count.pack(pady=(0, 15))
        
        # Backup Card
        self.card_backup = ctk.CTkFrame(stats_frame, corner_radius=15, fg_color=("white", "gray20"), border_width=1, border_color=("gray85", "gray15"))
        self.card_backup.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(self.card_backup, text="Letztes Backup", font=ctk.CTkFont(size=14)).pack(pady=(15, 5))
        self.lbl_last_backup = ctk.CTkLabel(self.card_backup, text="-", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_last_backup.pack(pady=(10, 15))
        
        # Recent Clients Card
        self.card_recent = ctk.CTkFrame(stats_frame, corner_radius=15, fg_color=("white", "gray20"), border_width=1, border_color=("gray85", "gray15"))
        self.card_recent.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(self.card_recent, text="Zuletzt verwendet", font=ctk.CTkFont(size=14)).pack(pady=(15, 5))
        self.lbl_recent_clients = ctk.CTkLabel(self.card_recent, text="-", font=ctk.CTkFont(size=14))
        self.lbl_recent_clients.pack(pady=(0, 15))
        
        # Quick Actions
        ctk.CTkLabel(self.dashboard_frame, text="Schnellzugriff", font=ctk.CTkFont(size=20, weight="bold")).grid(row=2, column=0, columnspan=2, pady=(40, 10), sticky="w", padx=20)
        
        actions_frame = ctk.CTkFrame(self.dashboard_frame, fg_color="transparent")
        actions_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=20)
        
        btn1 = ctk.CTkButton(actions_frame, text="[+] Neuen Kunden anlegen", font=ctk.CTkFont(weight="bold"), command=self.open_new_client_dialog, fg_color="#2b9e4a", hover_color="#217a39")
        btn1.pack(side="left", padx=10)
        
        btn2 = ctk.CTkButton(actions_frame, text="[↓] Backup jetzt erstellen", font=ctk.CTkFont(weight="bold"), command=self.create_backup_gui, fg_color="#2b9e4a", hover_color="#217a39")
        btn2.pack(side="left", padx=10)

    def show_dashboard(self):
        self.hide_all_frames()
        self.dashboard_frame.grid()
        self.reset_sidebar_buttons()
        self.btn_dashboard.configure(fg_color=("gray75", "gray25"))
        self.active_tool = 'dashboard'
        
        # Update Stats
        if hasattr(self, 'controller'):
            stats = self.controller.get_dashboard_stats()
            self.lbl_client_count.configure(text=str(stats.get("client_count", 0)))
            self.lbl_last_backup.configure(text=stats.get("last_backup", "Nie"))
            
            recent = self.config_manager.get("recent_clients", [])
            if recent:
                self.lbl_recent_clients.configure(text="\n".join(recent))
            else:
                self.lbl_recent_clients.configure(text="Keine")

    def build_settings_frame(self):
        self.settings_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.settings_frame.grid(row=0, column=0, sticky="nsew")
        self.settings_frame.grid_columnconfigure(0, weight=1)
        
        title = ctk.CTkLabel(self.settings_frame, text="Einstellungen", font=ctk.CTkFont(size=28, weight="bold"))
        title.grid(row=0, column=0, pady=(20, 30), sticky="w", padx=20)
        
        content = ctk.CTkFrame(self.settings_frame, corner_radius=15)
        content.grid(row=1, column=0, sticky="nsew", padx=20)
        content.grid_columnconfigure(1, weight=1)
        
        row_idx = 0
        
        # Appearance Mode
        ctk.CTkLabel(content, text="Erscheinungsbild:", font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, padx=20, pady=20, sticky="w")
        self.settings_mode_switch = ctk.CTkSwitch(content, text=TRANSLATIONS[self.lang]['switch_dark'], command=self.toggle_appearance_mode)
        if self.config_manager.get("appearance_mode", "Light") == "Dark":
            self.settings_mode_switch.select()
        self.settings_mode_switch.grid(row=row_idx, column=1, padx=20, pady=20, sticky="w")
        self.appearance_mode_switch = self.settings_mode_switch  # Repoint old ref
        row_idx += 1
        
        # Language
        ctk.CTkLabel(content, text="Sprache:", font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, padx=20, pady=20, sticky="w")
        self.settings_lang = ctk.CTkSegmentedButton(content, values=["DE", "IT"], command=self.change_language)
        self.settings_lang.set(self.config_manager.get("language", "DE"))
        self.settings_lang.grid(row=row_idx, column=1, padx=20, pady=20, sticky="w")
        self.lang_switch = self.settings_lang  # Repoint old ref
        row_idx += 1
        
        # API Key
        ctk.CTkLabel(content, text="Gemini API Key:", font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, padx=20, pady=20, sticky="w")
        self.api_key_entry = ctk.CTkEntry(content, width=300, show="*")
        self.api_key_entry.grid(row=row_idx, column=1, padx=20, pady=20, sticky="w")
        
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Systemdaten", "gemini_key.env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    content_key = f.read().strip()
                    if content_key.startswith("GEMINI_API_KEY="):
                        content_key = content_key.split("=", 1)[1].strip('"').strip("'")
                    self.api_key_entry.insert(0, content_key)
            except Exception as e:
                logger.error(f"Fehler beim Lesen des API-Keys: {e}")
                
        row_idx += 1
        
        # Globale Begriffe Button
        ctk.CTkLabel(content, text="Deduplizierung:", font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, padx=20, pady=20, sticky="w")
        btn_globale_begriffe = ctk.CTkButton(content, text="Globale Begriffsliste bearbeiten", command=self.open_globale_begriffe)
        btn_globale_begriffe.grid(row=row_idx, column=1, padx=20, pady=20, sticky="w")
        
        row_idx += 1
        
        # Save Button
        btn_save = ctk.CTkButton(content, text="Speichern", command=self.save_settings)
        btn_save.grid(row=row_idx, column=1, padx=20, pady=30, sticky="e")
        
    def save_settings(self):
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Systemdaten", "gemini_key.env")
        os.makedirs(os.path.dirname(env_path), exist_ok=True)
        key_val = self.api_key_entry.get().strip()
        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(f"GEMINI_API_KEY={key_val}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern des API-Keys: {e}")
            
        import tkinter.messagebox
        tkinter.messagebox.showinfo("Erfolg", "Einstellungen gespeichert!")

    def show_settings(self):
        self.hide_all_frames()
        self.settings_frame.grid()
        self.reset_sidebar_buttons()
        self.btn_settings.configure(fg_color=("gray75", "gray25"))
        self.active_tool = 'settings'

if __name__ == "__main__":
    app = BuchhaltungApp()
    app.mainloop()
