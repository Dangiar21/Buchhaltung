import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD
import os
import sys
import threading
import io
import re

# Modulpfade hinzufügen, damit die Unterordner erkannt werden
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
sys.path.append(os.path.join(script_dir, 'Programme', 'XML zu Excel'))
sys.path.append(os.path.join(script_dir, 'Programme', 'XML Preview'))

# Versuche Module zu importieren
try:
    from XMLEXCEL import run_conversion
except ImportError as e:
    print("Fehler beim Import von XMLEXCEL:", e)
    run_conversion = None

try:
    from XMLPreviewGUI import XMLPreviewFrame
except ImportError as e:
    print("Fehler beim Import von XMLPreviewGUI:", e)
    XMLPreviewFrame = None

# CustomTkinter Theme
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# TkinterDnD wrapper for CustomTkinter
class TkDnD(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)

class RedirectText(io.StringIO):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def write(self, string):
        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", string)
        self.text_widget.see("end")
        self.text_widget.configure(state="disabled")
        
    def flush(self):
        pass

TRANSLATIONS = {
    'DE': {
        'btn_xml_excel': 'XML zu Excel',
        'btn_xml_preview': 'XML Preview',
        'btn_pdf_gen': 'PDF Generator',
        'drop_label': 'Ordner oder XML/P7M Dateien hier ablegen\n(Drag & Drop)',
        'btn_files': 'Dateien auswählen',
        'btn_folder': 'Ordner auswählen',
        'welcome_msg': 'Willkommen bei der Buchhaltungs Suite!\nZiehe deine Dateien oder Ordner einfach in den Bereich oben.',
        'switch_dark': 'Dark Mode'
    },
    'IT': {
        'btn_xml_excel': 'XML in Excel',
        'btn_xml_preview': 'Anteprima XML',
        'btn_pdf_gen': 'Generatore PDF',
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
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        self.sidebar_frame.grid_rowconfigure(5, weight=0)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Buchhaltung", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.sidebar_btn_1 = ctk.CTkButton(self.sidebar_frame, text=TRANSLATIONS[self.lang]['btn_xml_excel'], command=self.show_xml_excel, text_color=("black", "white"))
        self.sidebar_btn_1.grid(row=1, column=0, padx=20, pady=10)

        self.sidebar_btn_2 = ctk.CTkButton(self.sidebar_frame, text=TRANSLATIONS[self.lang]['btn_xml_preview'], command=self.show_xml_preview, text_color=("black", "white"))
        self.sidebar_btn_2.grid(row=2, column=0, padx=20, pady=10)

        self.sidebar_btn_3 = ctk.CTkButton(self.sidebar_frame, text=TRANSLATIONS[self.lang]['btn_pdf_gen'], state="disabled", text_color=("black", "white"))
        self.sidebar_btn_3.grid(row=3, column=0, padx=20, pady=10)

        self.appearance_mode_switch = ctk.CTkSwitch(self.sidebar_frame, text=TRANSLATIONS[self.lang]['switch_dark'], command=self.toggle_appearance_mode)
        self.appearance_mode_switch.grid(row=4, column=0, padx=20, pady=(20, 10), sticky="s")
        
        self.lang_switch = ctk.CTkSegmentedButton(self.sidebar_frame, values=["DE", "IT"], command=self.change_language)
        self.lang_switch.set("DE")
        self.lang_switch.grid(row=5, column=0, padx=20, pady=(10, 20), sticky="s")

        # --- Container (Right Side) ---
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        # --- Frames ---
        self.build_xml_excel_frame()
        self.build_xml_preview_frame()
        
        # Startansicht
        self.show_xml_excel()

    def build_xml_excel_frame(self):
        self.xml_excel_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.xml_excel_frame.grid(row=0, column=0, sticky="nsew")
        self.xml_excel_frame.grid_columnconfigure(0, weight=1)
        self.xml_excel_frame.grid_rowconfigure(0, weight=1)
        self.xml_excel_frame.grid_rowconfigure(1, weight=1)

        # Drag and Drop Area
        self.drop_frame = ctk.CTkFrame(self.xml_excel_frame, fg_color=("gray75", "gray25"), corner_radius=15)
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
        self.log_textbox = ctk.CTkTextbox(self.xml_excel_frame, height=200)
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

    def show_xml_excel(self):
        self.xml_preview_frame.grid_remove()
        self.xml_excel_frame.grid()
        self.sidebar_btn_1.configure(fg_color=("gray75", "gray25"))
        self.sidebar_btn_2.configure(fg_color="transparent")
        
        sys.stdout = RedirectText(self.log_textbox)
        sys.stderr = sys.stdout
        print(TRANSLATIONS[self.lang]['welcome_msg'])

    def change_language(self, choice):
        self.lang = choice
        t = TRANSLATIONS[self.lang]
        self.sidebar_btn_1.configure(text=t['btn_xml_excel'])
        self.sidebar_btn_2.configure(text=t['btn_xml_preview'])
        self.sidebar_btn_3.configure(text=t['btn_pdf_gen'])
        self.appearance_mode_switch.configure(text=t['switch_dark'])
        self.drop_label.configure(text=t['drop_label'])
        self.btn_files.configure(text=t['btn_files'])
        self.btn_folder.configure(text=t['btn_folder'])
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        print(t['welcome_msg'])
        
        if hasattr(self, 'xml_preview_frame') and self.xml_preview_frame is not None and hasattr(self.xml_preview_frame, 'set_language'):
            self.xml_preview_frame.set_language(self.lang)

    def show_xml_preview(self):
        self.xml_excel_frame.grid_remove()
        self.xml_preview_frame.grid()
        self.sidebar_btn_2.configure(fg_color=("gray75", "gray25"))
        self.sidebar_btn_1.configure(fg_color="transparent")
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

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

    def select_files(self):
        filetypes = (('Rechnungen (XML/P7M)', '*.xml *.p7m'), ('Alle Dateien', '*.*'))
        filenames = ctk.filedialog.askopenfilenames(title='Wähle XML/P7M Dateien aus', filetypes=filetypes)
        if filenames:
            self.process_paths(list(filenames))
            
    def select_folder(self):
        folder_path = ctk.filedialog.askdirectory(title='Wähle einen Ordner mit Rechnungen aus')
        if folder_path:
            self.process_paths([folder_path])

    def process_paths(self, paths):
        print(f"\n--- Starte Verarbeitung ({len(paths)} Elemente erkannt) ---")
        if run_conversion:
            thread = threading.Thread(target=self.run_task, args=(paths,), daemon=True)
            thread.start()
        else:
            print("Fehler: XMLEXCEL.py konnte nicht importiert werden.")

    def run_task(self, paths):
        try:
            run_conversion(paths)
            print("\n✅ Verarbeitung abgeschlossen.")
        except Exception as e:
            print(f"\n❌ Ein unerwarteter Fehler ist aufgetreten: {e}")

if __name__ == "__main__":
    app = BuchhaltungApp()
    app.mainloop()
