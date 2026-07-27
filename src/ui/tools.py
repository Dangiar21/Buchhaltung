import customtkinter as ctk
from tkinterdnd2 import DND_FILES
from src.core.translations import translator
import sys
import os
import subprocess
import logging

logger = logging.getLogger(__name__)

def build_tool_frame(parent_frame, app, tool_id, has_setup=False):
    parent_frame.grid_columnconfigure(0, weight=1)
    parent_frame.grid_rowconfigure(0, weight=1)
    parent_frame.grid_rowconfigure(1, weight=1)

    drop_frame = ctk.CTkFrame(parent_frame, fg_color=("gray75", "gray25"), corner_radius=15)
    drop_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
    drop_frame.grid_columnconfigure(0, weight=1)
    drop_frame.grid_rowconfigure(0, weight=1)
    drop_frame.grid_rowconfigure(1, weight=1)
    drop_frame.grid_rowconfigure(2, weight=1)
    
    lbl_key = 'drop_label_csv' if tool_id == 'csv_to_excel' else 'drop_label'
    drop_label = ctk.CTkLabel(drop_frame, text=translator.get(app.lang, lbl_key), font=ctk.CTkFont(size=16))
    drop_label.grid(row=0, column=0, pady=(20, 10), sticky="s")
    
    btn_frame = ctk.CTkFrame(drop_frame, fg_color="transparent")
    btn_frame.grid(row=1, column=0, pady=(10, 20), sticky="n")
    
    btn_files = ctk.CTkButton(btn_frame, text=translator.get(app.lang, 'btn_files'), command=lambda: app.select_files(tool_id))
    btn_files.grid(row=0, column=0, padx=10)
    
    btn_folder = ctk.CTkButton(btn_frame, text=translator.get(app.lang, 'btn_folder'), command=lambda: app.select_folder(tool_id))
    btn_folder.grid(row=0, column=1, padx=10)
    
    btn_setup = None
    if has_setup:
        def open_setup():
            if not app.current_client or app.current_client == "Kein Kunde":
                logger.error("\n❌ Bitte wähle zuerst einen Kunden in der Seitenleiste aus!")
                return
            client_dir = os.path.join(app.controller.base_kunden_dir, app.current_client)
            nutzerdaten_dir = os.path.join(client_dir, "Nutzerdaten")
            setup_path = os.path.join(nutzerdaten_dir, "Analyse_Setup.xlsx")
            
            try:
                import Analyse_Config
                Analyse_Config.ensure_setup_file(nutzerdaten_dir)
            except ImportError:
                pass
                
            logger.info(f"Öffne {setup_path}...")
            if os.name == 'nt' or sys.platform == 'win32':
                os.startfile(setup_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', setup_path], check=True)
            else:
                subprocess.run(['xdg-open', setup_path], check=True)
                
        btn_setup = ctk.CTkButton(btn_frame, text="Kategorien-Setup öffnen", command=open_setup, fg_color="#c85a17", hover_color="#a84b13")
        btn_setup.grid(row=0, column=2, padx=10)
        
    btn_cancel = ctk.CTkButton(btn_frame, text="Abbrechen & Speichern", command=app.controller.cancel_task, fg_color="red", hover_color="darkred")
    btn_cancel.grid(row=0, column=3 if has_setup else 2, padx=10)
    btn_cancel.grid_remove()

    log_textbox = ctk.CTkTextbox(parent_frame, height=200)
    log_textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 5))
    log_textbox.configure(state="disabled")

    progress_bar = ctk.CTkProgressBar(parent_frame, height=10)
    progress_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
    progress_bar.set(0)

    drop_frame.drop_target_register(DND_FILES)
    drop_frame.dnd_bind('<<Drop>>', app.drop_event)
    
    return drop_label, btn_files, btn_folder, btn_cancel, log_textbox, progress_bar
