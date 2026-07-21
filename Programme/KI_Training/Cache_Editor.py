import os
import json
import shutil
import customtkinter as ctk

class CacheEditorFrame(ctk.CTkFrame):
    def __init__(self, master, current_client_callback):
        super().__init__(master)
        self.current_client_callback = current_client_callback
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # Header
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        
        self.title_label = ctk.CTkLabel(self.header_frame, text="KI-Training (Gedächtnis-Editor)", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.pack(side="left", padx=10, pady=10)
        
        # Controls
        self.controls_frame = ctk.CTkFrame(self)
        self.controls_frame.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        
        self.cache_type_var = ctk.StringVar(value="Sektorenanalyse")
        self.cache_type_dropdown = ctk.CTkOptionMenu(
            self.controls_frame, 
            values=["Sektorenanalyse", "FIBU Kontierung"],
            variable=self.cache_type_var,
            command=self.load_data
        )
        self.cache_type_dropdown.pack(side="left", padx=10, pady=10)
        
        self.refresh_btn = ctk.CTkButton(self.controls_frame, text="Neu laden", command=self.load_data)
        self.refresh_btn.pack(side="left", padx=10, pady=10)
        
        self.save_btn = ctk.CTkButton(self.controls_frame, text="Änderungen Speichern", command=self.save_data, fg_color="green", hover_color="darkgreen")
        self.save_btn.pack(side="right", padx=10, pady=10)
        
        self.status_label = ctk.CTkLabel(self.controls_frame, text="")
        self.status_label.pack(side="right", padx=10, pady=10)
        
        # Data Area
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=3)
        self.scroll_frame.grid_columnconfigure(1, weight=1)
        
        self.entries = {}
        self.current_filepath = ""
        self.current_data = {}
        
    def show_status(self, text, color="text"):
        self.status_label.configure(text=text, text_color=color)
        self.after(3000, lambda: self.status_label.configure(text=""))
        
    def get_file_path(self):
        client = self.current_client_callback()
        if not client:
            return None
            
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        nutzerdaten_dir = os.path.join(base_dir, "Kunden", client, "Nutzerdaten")
        
        if self.cache_type_var.get() == "Sektorenanalyse":
            return os.path.join(nutzerdaten_dir, "Analyse_Memory.json")
        else:
            return os.path.join(nutzerdaten_dir, "Konten_Memory.json")
            
    def load_data(self, *args):
        # Clear current UI
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.entries.clear()
        
        self.current_filepath = self.get_file_path()
        if not self.current_filepath:
            ctk.CTkLabel(self.scroll_frame, text="Bitte zuerst einen Kunden auswählen!").grid(row=0, column=0, pady=20)
            return
            
        if not os.path.exists(self.current_filepath):
            ctk.CTkLabel(self.scroll_frame, text="Noch keine KI-Daten (Cache) für diesen Kunden vorhanden.").grid(row=0, column=0, pady=20)
            return
            
        try:
            with open(self.current_filepath, 'r', encoding='utf-8') as f:
                self.current_data = json.load(f)
        except Exception as e:
            ctk.CTkLabel(self.scroll_frame, text=f"Fehler beim Laden: {e}").grid(row=0, column=0, pady=20)
            return
            
        if not self.current_data:
            ctk.CTkLabel(self.scroll_frame, text="Das Gedächtnis ist leer.").grid(row=0, column=0, pady=20)
            return
            
        # Headers
        ctk.CTkLabel(self.scroll_frame, text="Artikel (Lieferant | Beschreibung)", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.scroll_frame, text="Kategorie / Konto", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        row = 1
        for key, value in self.current_data.items():
            # Key label
            key_label = ctk.CTkLabel(self.scroll_frame, text=key, wraplength=400, justify="left")
            key_label.grid(row=row, column=0, padx=5, pady=2, sticky="w")
            
            # Value entry
            val_str = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
            entry = ctk.CTkEntry(self.scroll_frame, width=250)
            entry.insert(0, val_str)
            entry.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
            
            # Delete btn
            del_btn = ctk.CTkButton(self.scroll_frame, text="Löschen", width=60, fg_color="#cc0000", hover_color="#990000", 
                                    command=lambda k=key, r=row: self.mark_delete(k, r))
            del_btn.grid(row=row, column=2, padx=5, pady=2)
            
            self.entries[key] = {"entry": entry, "widget_row": row, "deleted": False, "del_btn": del_btn}
            row += 1
            
    def mark_delete(self, key, row):
        data = self.entries[key]
        if data["deleted"]:
            data["deleted"] = False
            data["entry"].configure(state="normal")
            data["del_btn"].configure(text="Löschen", fg_color="#cc0000", hover_color="#990000")
        else:
            data["deleted"] = True
            data["entry"].configure(state="disabled")
            data["del_btn"].configure(text="Rückgängig", fg_color="gray", hover_color="darkgray")
            
    def save_data(self):
        if not self.current_filepath or not os.path.exists(self.current_filepath):
            return
            
        new_data = {}
        for key, data in self.entries.items():
            if not data["deleted"]:
                val_str = data["entry"].get()
                try:
                    # Versuche als dict zu parsen, falls es Sektorenanalyse ist
                    if self.cache_type_var.get() == "Sektorenanalyse":
                        parsed = json.loads(val_str)
                    else:
                        parsed = val_str
                    new_data[key] = parsed
                except:
                    # Fallback auf reinen String
                    new_data[key] = val_str
                    
        # Backup erstellen
        backup_path = self.current_filepath.replace(".json", "_backup.json")
        try:
            shutil.copy2(self.current_filepath, backup_path)
        except Exception as e:
            print("Backup Fehler:", e)
            
        try:
            with open(self.current_filepath, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, indent=4, ensure_ascii=False)
            self.show_status("Erfolgreich gespeichert!", "green")
            self.current_data = new_data
        except Exception as e:
            self.show_status(f"Fehler: {e}", "red")
            # Rollback
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, self.current_filepath)
