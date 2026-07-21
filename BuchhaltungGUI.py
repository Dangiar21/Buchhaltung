import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD
import os
import sys
import threading
import io
import re
import queue

# Modulpfade hinzufügen, damit die Unterordner erkannt werden
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
sys.path.append(os.path.join(script_dir, 'Programme', 'Buchungen erstellen'))
sys.path.append(os.path.join(script_dir, 'Programme', 'XML Preview'))
sys.path.append(os.path.join(script_dir, 'Programme', 'XML zu Excel'))
sys.path.append(os.path.join(script_dir, 'Programme', 'Analyse erstellen'))
sys.path.append(os.path.join(script_dir, 'Programme', 'KI_Training'))

# Versuche Module zu importieren
try:
    from BuchungenErstellen import run_conversion
except ImportError as e:
    print("Fehler beim Import von BuchungenErstellen:", e)
    run_conversion = None

try:
    from XMLzuExcel import run_conversion as run_xml_to_excel
except ImportError as e:
    print("Fehler beim Import von XMLzuExcel:", e)
    run_xml_to_excel = None

try:
    from Analyse_Main import run_analyse
    import Analyse_Config
except ImportError as e:
    print("Fehler beim Import von Analyse_Main:", e)
    run_analyse = None
    Analyse_Config = None

try:
    from XMLPreviewGUI import XMLPreviewFrame
except ImportError as e:
    print("Fehler beim Import von XMLPreviewGUI:", e)
    XMLPreviewFrame = None

try:
    from Cache_Editor import CacheEditorFrame
except ImportError as e:
    print("Fehler beim Import von Cache_Editor:", e)
    CacheEditorFrame = None

try:
    from Buchung_KI import ensure_konten_template
except ImportError as e:
    print("Fehler beim Import von ensure_konten_template:", e)
    ensure_konten_template = None

# CustomTkinter Theme
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# TkinterDnD wrapper for CustomTkinter
class TkDnD(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)

class RedirectText(io.StringIO):
    def __init__(self, text_queue, target_widget):
        super().__init__()
        self.text_queue = text_queue
        self.target_widget = target_widget

    def write(self, string):
        self.text_queue.put((string, self.target_widget))
        
    def flush(self):
        pass

TRANSLATIONS = {
    'DE': {
        'btn_xml_preview': 'XML Preview',
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
        'btn_xml_preview': 'Anteprima XML',
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

        self.lang = "DE"
        self.title("Buchhaltung Suite")
        self.geometry("1100x700")

        # Set grid layout 1x2
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)
        self.sidebar_frame.grid_rowconfigure(7, weight=0)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Buchhaltung", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # --- Client Selection ---
        self.client_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.client_frame.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="nsew")
        
        self.search_client_var = ctk.StringVar()
        self.search_client_entry = ctk.CTkEntry(self.client_frame, placeholder_text="Kunde suchen...", textvariable=self.search_client_var)
        self.search_client_entry.pack(fill="x", pady=(0, 5))
        self.search_client_entry.bind("<KeyRelease>", self.filter_clients)
        
        self.client_list_frame = ctk.CTkScrollableFrame(self.client_frame, height=150, fg_color=("gray85", "gray20"))
        self.client_list_frame.pack(fill="both", expand=True, pady=(0, 5))
        
        self.btn_new_client = ctk.CTkButton(self.client_frame, text="+ Neuer Kunde", command=self.open_new_client_dialog, fg_color="#2b9e4a", hover_color="#217a39")
        self.btn_new_client.pack(fill="x")

        self.sidebar_btn_1 = ctk.CTkButton(self.sidebar_frame, text=TRANSLATIONS[self.lang]['btn_xml_preview'], command=self.show_xml_preview, text_color=("black", "white"))
        self.sidebar_btn_1.grid(row=2, column=0, padx=20, pady=10)

        self.sidebar_btn_2 = ctk.CTkButton(self.sidebar_frame, text=TRANSLATIONS[self.lang]['btn_xml_to_excel'], command=self.show_xml_to_excel, text_color=("black", "white"))
        self.sidebar_btn_2.grid(row=3, column=0, padx=20, pady=10)

        self.sidebar_btn_3 = ctk.CTkButton(self.sidebar_frame, text=TRANSLATIONS[self.lang]['btn_buchung_erstellen'], command=self.show_buchung_erstellen, text_color=("black", "white"))
        self.sidebar_btn_3.grid(row=4, column=0, padx=20, pady=10)
        
        self.sidebar_btn_4 = ctk.CTkButton(self.sidebar_frame, text=TRANSLATIONS[self.lang]['btn_analyse'], command=self.show_analyse, text_color=("black", "white"))
        self.sidebar_btn_4.grid(row=5, column=0, padx=20, pady=10)

        self.sidebar_btn_5 = ctk.CTkButton(self.sidebar_frame, text="KI-Training (Cache)", command=self.show_cache_editor, text_color=("black", "white"))
        self.sidebar_btn_5.grid(row=6, column=0, padx=20, pady=10)

        self.appearance_mode_switch = ctk.CTkSwitch(self.sidebar_frame, text=TRANSLATIONS[self.lang]['switch_dark'], command=self.toggle_appearance_mode)
        self.appearance_mode_switch.grid(row=7, column=0, padx=20, pady=(20, 10), sticky="s")
        
        self.lang_switch = ctk.CTkSegmentedButton(self.sidebar_frame, values=["DE", "IT"], command=self.change_language)
        self.lang_switch.set("DE")
        self.lang_switch.grid(row=8, column=0, padx=20, pady=(10, 20), sticky="s")

        # --- Container (Right Side) ---
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        # --- Frames ---
        self.build_xml_preview_frame()
        self.build_xml_to_excel_frame()
        self.build_buchung_erstellen_frame()
        self.build_analyse_frame()
        self.build_cache_editor_frame()
        
        # Load Clients
        self.base_kunden_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Kunden")
        if not os.path.exists(self.base_kunden_dir):
            os.makedirs(self.base_kunden_dir)
            
        self.current_client = None
        self.all_clients = []
        self.refresh_clients()
        
        self.active_tool = None
        
        self.print_queue = queue.Queue()
        self.process_print_queue()
        
        # Startansicht
        self.show_xml_preview()

    def process_print_queue(self):
        while not self.print_queue.empty():
            try:
                msg, target_widget = self.print_queue.get_nowait()
                target_widget.configure(state="normal")
                target_widget.insert("end", msg)
                target_widget.see("end")
                target_widget.configure(state="disabled")
            except queue.Empty:
                break
        self.after(100, self.process_print_queue)

    def build_buchung_erstellen_frame(self):
        self.buchung_erstellen_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.buchung_erstellen_frame.grid(row=0, column=0, sticky="nsew")
        self.buchung_erstellen_frame.grid_columnconfigure(0, weight=1)
        self.buchung_erstellen_frame.grid_rowconfigure(0, weight=1)
        self.buchung_erstellen_frame.grid_rowconfigure(1, weight=1)

        # Drag and Drop Area
        self.drop_frame = ctk.CTkFrame(self.buchung_erstellen_frame, fg_color=("gray75", "gray25"), corner_radius=15)
        self.drop_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.drop_frame.grid_columnconfigure(0, weight=1)
        self.drop_frame.grid_rowconfigure(0, weight=1)
        self.drop_frame.grid_rowconfigure(1, weight=1)
        self.drop_frame.grid_rowconfigure(2, weight=1)
        
        self.drop_label = ctk.CTkLabel(self.drop_frame, text=TRANSLATIONS[self.lang]['drop_label'], font=ctk.CTkFont(size=16))
        self.drop_label.grid(row=0, column=0, pady=(20, 10), sticky="s")
        
        self.btn_frame = ctk.CTkFrame(self.drop_frame, fg_color="transparent")
        self.btn_frame.grid(row=1, column=0, pady=(10, 20), sticky="n")
        
        self.btn_files = ctk.CTkButton(self.btn_frame, text=TRANSLATIONS[self.lang]['btn_files'], command=self.select_files)
        self.btn_files.grid(row=0, column=0, padx=10)
        
        self.btn_folder = ctk.CTkButton(self.btn_frame, text=TRANSLATIONS[self.lang]['btn_folder'], command=self.select_folder)
        self.btn_folder.grid(row=0, column=1, padx=10)

        # Log Area
        self.log_textbox = ctk.CTkTextbox(self.buchung_erstellen_frame, height=200)
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.log_textbox.configure(state="disabled")

        # Configure Drop
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self.drop_event)
        
    def build_xml_preview_frame(self):
        if XMLPreviewFrame:
            self.xml_preview_frame = XMLPreviewFrame(self.container, fg_color="transparent")
            self.xml_preview_frame.grid(row=0, column=0, sticky="nsew")
        else:
            self.xml_preview_frame = ctk.CTkFrame(self.container)
            self.xml_preview_frame.grid(row=0, column=0, sticky="nsew")
            ctk.CTkLabel(self.xml_preview_frame, text="Fehler: XMLPreviewGUI.py nicht gefunden").pack(expand=True)

    def build_xml_to_excel_frame(self):
        self.xml_to_excel_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.xml_to_excel_frame.grid(row=0, column=0, sticky="nsew")
        self.xml_to_excel_frame.grid_columnconfigure(0, weight=1)
        self.xml_to_excel_frame.grid_rowconfigure(0, weight=1)
        self.xml_to_excel_frame.grid_rowconfigure(1, weight=1)

        # Drag and Drop Area
        self.xml2ex_drop_frame = ctk.CTkFrame(self.xml_to_excel_frame, fg_color=("gray75", "gray25"), corner_radius=15)
        self.xml2ex_drop_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.xml2ex_drop_frame.grid_columnconfigure(0, weight=1)
        self.xml2ex_drop_frame.grid_rowconfigure(0, weight=1)
        self.xml2ex_drop_frame.grid_rowconfigure(1, weight=1)
        self.xml2ex_drop_frame.grid_rowconfigure(2, weight=1)
        
        self.xml2ex_drop_label = ctk.CTkLabel(self.xml2ex_drop_frame, text=TRANSLATIONS[self.lang]['drop_label'], font=ctk.CTkFont(size=16))
        self.xml2ex_drop_label.grid(row=0, column=0, pady=(20, 10), sticky="s")
        
        self.xml2ex_btn_frame = ctk.CTkFrame(self.xml2ex_drop_frame, fg_color="transparent")
        self.xml2ex_btn_frame.grid(row=1, column=0, pady=(10, 20), sticky="n")
        
        self.xml2ex_btn_files = ctk.CTkButton(self.xml2ex_btn_frame, text=TRANSLATIONS[self.lang]['btn_files'], command=self.select_files)
        self.xml2ex_btn_files.grid(row=0, column=0, padx=10)
        
        self.xml2ex_btn_folder = ctk.CTkButton(self.xml2ex_btn_frame, text=TRANSLATIONS[self.lang]['btn_folder'], command=self.select_folder)
        self.xml2ex_btn_folder.grid(row=0, column=1, padx=10)

        # Log Area
        self.xml2ex_log_textbox = ctk.CTkTextbox(self.xml_to_excel_frame, height=200)
        self.xml2ex_log_textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.xml2ex_log_textbox.configure(state="disabled")

        # Configure Drop
        self.xml2ex_drop_frame.drop_target_register(DND_FILES)
        self.xml2ex_drop_frame.dnd_bind('<<Drop>>', self.drop_event)
        
    def build_analyse_frame(self):
        self.analyse_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.analyse_frame.grid(row=0, column=0, sticky="nsew")
        self.analyse_frame.grid_columnconfigure(0, weight=1)
        self.analyse_frame.grid_rowconfigure(0, weight=1)
        self.analyse_frame.grid_rowconfigure(1, weight=1)

        # Drag and Drop Area
        self.analyse_drop_frame = ctk.CTkFrame(self.analyse_frame, fg_color=("gray75", "gray25"), corner_radius=15)
        self.analyse_drop_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.analyse_drop_frame.grid_columnconfigure(0, weight=1)
        self.analyse_drop_frame.grid_rowconfigure(0, weight=1)
        self.analyse_drop_frame.grid_rowconfigure(1, weight=1)
        self.analyse_drop_frame.grid_rowconfigure(2, weight=1)
        
        self.analyse_drop_label = ctk.CTkLabel(self.analyse_drop_frame, text=TRANSLATIONS[self.lang]['drop_label'], font=ctk.CTkFont(size=16))
        self.analyse_drop_label.grid(row=0, column=0, pady=(20, 10), sticky="s")
        
        self.analyse_btn_frame = ctk.CTkFrame(self.analyse_drop_frame, fg_color="transparent")
        self.analyse_btn_frame.grid(row=1, column=0, pady=(10, 20), sticky="n")
        
        self.analyse_btn_files = ctk.CTkButton(self.analyse_btn_frame, text=TRANSLATIONS[self.lang]['btn_files'], command=self.select_files)
        self.analyse_btn_files.grid(row=0, column=0, padx=10)
        
        self.analyse_btn_folder = ctk.CTkButton(self.analyse_btn_frame, text=TRANSLATIONS[self.lang]['btn_folder'], command=self.select_folder)
        self.analyse_btn_folder.grid(row=0, column=1, padx=10)
        
        self.analyse_btn_setup = ctk.CTkButton(self.analyse_btn_frame, text="Kategorien-Setup öffnen", command=self.open_analyse_setup, fg_color="#c85a17", hover_color="#a84b13")
        self.analyse_btn_setup.grid(row=0, column=2, padx=10)

        # Log Area
        self.analyse_log_textbox = ctk.CTkTextbox(self.analyse_frame, height=200)
        self.analyse_log_textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.analyse_log_textbox.configure(state="disabled")

        # Configure Drop
        self.analyse_drop_frame.drop_target_register(DND_FILES)
        self.analyse_drop_frame.dnd_bind('<<Drop>>', self.drop_event)

    def open_analyse_setup(self):
        if not self.current_client or self.current_client == "Kein Kunde":
            print("\n❌ Bitte wähle zuerst einen Kunden in der Seitenleiste aus!")
            return
            
        client_dir = os.path.join(self.base_kunden_dir, self.current_client)
        nutzerdaten_dir = os.path.join(client_dir, "Nutzerdaten")
        setup_path = os.path.join(nutzerdaten_dir, "Analyse_Setup.xlsx")
        
        if Analyse_Config:
            Analyse_Config.ensure_setup_file(nutzerdaten_dir)
            
            print(f"Öffne {setup_path}...")
            if os.name == 'nt' or sys.platform == 'win32':
                os.startfile(setup_path)
            elif sys.platform == 'darwin':
                import subprocess
                subprocess.run(['open', setup_path], check=True)
            else:
                import subprocess
                subprocess.run(['xdg-open', setup_path], check=True)
        else:
            print("Analyse_Config.py konnte nicht importiert werden.")

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
        self.xml_preview_frame.grid_remove()
        self.xml_to_excel_frame.grid_remove()
        self.buchung_erstellen_frame.grid_remove()
        self.analyse_frame.grid_remove()
        self.cache_editor_frame.grid_remove()
        
    def reset_sidebar_buttons(self):
        self.sidebar_btn_1.configure(fg_color="transparent")
        self.sidebar_btn_2.configure(fg_color="transparent")
        self.sidebar_btn_3.configure(fg_color="transparent")
        self.sidebar_btn_4.configure(fg_color="transparent")
        self.sidebar_btn_5.configure(fg_color="transparent")

    def show_xml_preview(self):
        self.active_tool = 'xml_preview'
        self.hide_all_frames()
        self.xml_preview_frame.grid()
        self.reset_sidebar_buttons()
        self.sidebar_btn_1.configure(fg_color=("gray75", "gray25"))
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def show_xml_to_excel(self):
        self.active_tool = 'xml_to_excel'
        self.hide_all_frames()
        self.xml_to_excel_frame.grid()
        self.reset_sidebar_buttons()
        self.sidebar_btn_2.configure(fg_color=("gray75", "gray25"))
        sys.stdout = RedirectText(self.print_queue, self.xml2ex_log_textbox)
        sys.stderr = sys.stdout
        print(TRANSLATIONS[self.lang]['welcome_msg'])

    def show_buchung_erstellen(self):
        self.active_tool = 'buchung_erstellen'
        self.hide_all_frames()
        self.buchung_erstellen_frame.grid()
        self.reset_sidebar_buttons()
        self.sidebar_btn_3.configure(fg_color=("gray75", "gray25"))
        sys.stdout = RedirectText(self.print_queue, self.log_textbox)
        sys.stderr = sys.stdout
        print(TRANSLATIONS[self.lang]['welcome_msg'])

    def show_analyse(self):
        self.active_tool = 'analyse'
        self.hide_all_frames()
        self.analyse_frame.grid()
        self.reset_sidebar_buttons()
        self.sidebar_btn_4.configure(fg_color=("gray75", "gray25"))
        sys.stdout = RedirectText(self.print_queue, self.analyse_log_textbox)
        sys.stderr = sys.stdout
        print(TRANSLATIONS[self.lang]['welcome_msg'])

    def change_language(self, choice):
        self.lang = choice
        t = TRANSLATIONS[self.lang]
        self.sidebar_btn_1.configure(text=t['btn_xml_preview'])
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
        
        print(t['welcome_msg'])
        
        if hasattr(self, 'xml_preview_frame') and self.xml_preview_frame is not None and hasattr(self.xml_preview_frame, 'set_language'):
            self.xml_preview_frame.set_language(self.lang)


    def toggle_appearance_mode(self):
        if self.appearance_mode_switch.get() == 1:
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")

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
        filetypes = (('Rechnungen (XML/P7M)', '*.xml *.p7m'), ('Alle Dateien', '*.*'))
        initial_dir = self.get_initial_dir()
        filenames = ctk.filedialog.askopenfilenames(title='Wähle XML/P7M Dateien aus', filetypes=filetypes, initialdir=initial_dir)
        if filenames:
            self.process_paths(list(filenames))
            
    def select_folder(self):
        initial_dir = self.get_initial_dir()
        folder_path = ctk.filedialog.askdirectory(title='Wähle einen Ordner mit Rechnungen aus', initialdir=initial_dir)
        if folder_path:
            self.process_paths([folder_path])

    def process_paths(self, paths):
        if not self.current_client or self.current_client == "Kein Kunde":
            print("\n❌ Bitte wähle zuerst einen Kunden in der Seitenleiste aus!")
            return
            
        print(f"\n--- Starte Verarbeitung für Kunde: {self.current_client} ({len(paths)} Elemente erkannt) ---")
        client_dir = os.path.join(self.base_kunden_dir, self.current_client)
        output_dir = os.path.join(client_dir, "Buchhaltung")
        nutzerdaten_dir = os.path.join(client_dir, "Nutzerdaten")
        
        if self.active_tool == 'buchung_erstellen':
            if run_conversion:
                thread = threading.Thread(target=self.run_task, args=(paths, output_dir, nutzerdaten_dir, run_conversion), daemon=True)
                thread.start()
            else:
                print("Fehler: BuchungenErstellen.py konnte nicht importiert werden.")
        elif self.active_tool == 'xml_to_excel':
            if run_xml_to_excel:
                thread = threading.Thread(target=self.run_task, args=(paths, output_dir, nutzerdaten_dir, run_xml_to_excel), daemon=True)
                thread.start()
            else:
                print("Fehler: XMLzuExcel.py konnte nicht importiert werden.")
        elif self.active_tool == 'analyse':
            if run_analyse:
                base_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
                folder = paths[0] if len(paths) > 0 else client_dir
                thread = threading.Thread(target=self.run_task, args=([folder], output_dir, nutzerdaten_dir, lambda paths, output_dir, nutzerdaten_dir: run_analyse(paths[0], self.current_client, base_dir, nutzerdaten_dir)), daemon=True)
                thread.start()
            else:
                print("Fehler: Analyse_Main.py konnte nicht importiert werden.")

    def run_task(self, paths, output_dir, nutzerdaten_dir, func):
        try:
            func(paths, output_dir=output_dir, nutzerdaten_dir=nutzerdaten_dir)
            print("\n✅ Verarbeitung abgeschlossen.")
        except Exception as e:
            print(f"\n❌ Ein unerwarteter Fehler ist aufgetreten: {e}")

    def refresh_clients(self):
        self.all_clients = []
        if os.path.exists(self.base_kunden_dir):
            for d in os.listdir(self.base_kunden_dir):
                if os.path.isdir(os.path.join(self.base_kunden_dir, d)):
                    self.all_clients.append(d)
        
        self.all_clients.sort()
        
        if not self.all_clients:
            self.current_client = None
            self.search_client_var.set("Kein Kunde")
        else:
            # Versuche den letzten Kunden zu laden
            last_client_file = os.path.join(self.base_kunden_dir, "last_client.json")
            saved_client = None
            if os.path.exists(last_client_file):
                try:
                    import json
                    with open(last_client_file, "r") as f:
                        data = json.load(f)
                        saved_client = data.get("last_client")
                except Exception as e:
                    pass
            
            if saved_client and saved_client in self.all_clients:
                self.current_client = saved_client
            elif self.current_client not in self.all_clients:
                self.current_client = self.all_clients[0]
                
            self.search_client_var.set(self.current_client)
            # Preview Frame aktualisieren
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
            print(f"\nKunde gewechselt zu: {self.current_client}")
            
            # Letzten Kunden speichern
            try:
                import json
                last_client_file = os.path.join(self.base_kunden_dir, "last_client.json")
                with open(last_client_file, "w") as f:
                    json.dump({"last_client": self.current_client}, f)
            except Exception as e:
                print(f"Fehler beim Speichern des letzten Kunden: {e}")
            
            # Optional: Dem Preview-Fenster mitteilen, dass der Kunde gewechselt wurde
            # falls wir das Preview auf den Kundenordner filtern möchten
            client_dir = os.path.join(self.base_kunden_dir, self.current_client)
            if hasattr(self, 'xml_preview_frame') and self.xml_preview_frame:
                rechnungen_dir = os.path.join(client_dir, "Rechnungen")
                if os.path.exists(rechnungen_dir) and hasattr(self.xml_preview_frame, 'load_directory'):
                    # Load directory async to not block GUI
                    self.xml_preview_frame.current_folder = rechnungen_dir
                    self.xml_preview_frame.after(100, lambda: self.xml_preview_frame.load_directory(rechnungen_dir))
        else:
            self.current_client = None

    def open_new_client_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Neuer Kunde")
        dialog.geometry("400x350")
        dialog.attributes('-topmost', 'true')
        
        lbl = ctk.CTkLabel(dialog, text="Neuen Kunden anlegen", font=ctk.CTkFont(size=16, weight="bold"))
        lbl.pack(pady=15)
        
        name_entry = ctk.CTkEntry(dialog, placeholder_text="Kundenname / Ordnername", width=300)
        name_entry.pack(pady=10)
        
        info_text = ctk.CTkTextbox(dialog, width=300, height=150)
        info_text.insert("1.0", "Weitere Infos (USt-IdNr., Steuernummer, etc.)")
        info_text.pack(pady=10)
        
        def save_client():
            name_raw = name_entry.get().strip()
            if not name_raw:
                return
                
            name = re.sub(r'[<>:"/\\|?*]', '_', name_raw)
            
            client_dir = os.path.join(self.base_kunden_dir, name)
            if not os.path.exists(client_dir):
                os.makedirs(client_dir)
                os.makedirs(os.path.join(client_dir, "Rechnungen"))
                os.makedirs(os.path.join(client_dir, "Buchhaltung"))
                os.makedirs(os.path.join(client_dir, "Analyse"))
                info_nutzerdaten_dir = os.path.join(client_dir, "Nutzerdaten")
                os.makedirs(info_nutzerdaten_dir, exist_ok=True)
                
                if ensure_konten_template:
                    ensure_konten_template(info_nutzerdaten_dir)
                
                info = info_text.get("1.0", "end").strip()
                if info and info != "Weitere Infos (USt-IdNr., Steuernummer, etc.)":
                    import json
                    info_path = os.path.join(info_nutzerdaten_dir, "info.json")
                    with open(info_path, "w", encoding="utf-8") as f:
                        json.dump({"Kundenname": name, "Zusatzinfos": info}, f, ensure_ascii=False, indent=4)
                
                print(f"\n=> Kunde '{name}' erfolgreich angelegt!")
                self.refresh_clients()
                self.select_client_from_list(name)
                dialog.destroy()
            else:
                print(f"Kunde {name} existiert bereits!")
                
        btn_save = ctk.CTkButton(dialog, text="Speichern", command=save_client)
        btn_save.pack(pady=10)

if __name__ == "__main__":
    app = BuchhaltungApp()
    app.mainloop()
