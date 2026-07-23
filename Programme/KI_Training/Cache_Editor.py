import os
import json

import customtkinter as ctk
import sys
script_dir = os.path.dirname(os.path.abspath(__file__))
prog_dir = os.path.dirname(script_dir)
if prog_dir not in sys.path:
    sys.path.append(prog_dir)

try:
    from DatabaseManager import get_db
except ImportError:
    pass

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
        
        self.filter_var = ctk.StringVar(value="Alle")
        self.filter_dropdown = ctk.CTkOptionMenu(
            self.controls_frame,
            values=["Alle", "Bestätigt", "Unbestätigt"],
            variable=self.filter_var,
            command=self.load_data
        )
        self.filter_dropdown.pack(side="left", padx=10, pady=10)
        
        self.refresh_btn = ctk.CTkButton(self.controls_frame, text="Neu laden", command=self.load_data)
        self.refresh_btn.pack(side="left", padx=10, pady=10)
        
        self.delete_all_btn = ctk.CTkButton(self.controls_frame, text="Alle Löschen", command=self.delete_all, fg_color="#cc0000", hover_color="#990000")
        self.delete_all_btn.pack(side="left", padx=10, pady=10)
        
        self.save_btn = ctk.CTkButton(self.controls_frame, text="Änderungen Speichern", command=self.save_data, fg_color="green", hover_color="darkgreen")
        self.save_btn.pack(side="right", padx=10, pady=10)
        
        self.status_label = ctk.CTkLabel(self.controls_frame, text="")
        self.status_label.pack(side="right", padx=10, pady=10)
        
        # Pagination Controls
        self.pagination_frame = ctk.CTkFrame(self)
        self.pagination_frame.grid(row=2, column=0, padx=20, pady=(0, 5), sticky="ew")
        
        self.prev_btn = ctk.CTkButton(self.pagination_frame, text="< Zurück", command=self.prev_page, width=80)
        self.prev_btn.pack(side="left", padx=10, pady=5)
        
        self.page_label = ctk.CTkLabel(self.pagination_frame, text="Seite 1 / 1")
        self.page_label.pack(side="left", expand=True)
        
        self.next_btn = ctk.CTkButton(self.pagination_frame, text="Weiter >", command=self.next_page, width=80)
        self.next_btn.pack(side="right", padx=10, pady=5)
        
        # Data Area
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.grid_rowconfigure(3, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.scroll_frame.grid_columnconfigure(0, weight=1)
        self.scroll_frame.grid_columnconfigure(1, weight=1)
        self.scroll_frame.grid_columnconfigure(2, weight=2)
        
        self.entries = {}
        self.current_filepath = ""
        self.current_data = {}
        self.filtered_keys = []
        self.current_page = 0
        self.items_per_page = 50
        
    def show_status(self, text, color="text"):
        self.status_label.configure(text=text, text_color=color)
        self.after(3000, lambda: self.status_label.configure(text=""))
        
    def get_client(self):
        client = self.current_client_callback()
        if not client or client == "Kein Kunde":
            return None
        return client
        
    def load_data(self, *args):
        self.current_page = 0
        self.entries.clear()
        
        client = self.get_client()
        if not client:
            for widget in self.scroll_frame.winfo_children(): widget.destroy()
            ctk.CTkLabel(self.scroll_frame, text="Bitte zuerst einen Kunden auswählen!").grid(row=0, column=0, pady=20)
            return
            
        try:
            db = get_db()
            cache_type = self.cache_type_var.get()
            if cache_type == "Sektorenanalyse":
                self.current_data = db.get_analyse_cache_full(client)
            else:
                self.current_data = db.get_konten_cache_full(client)
        except Exception as e:
            for widget in self.scroll_frame.winfo_children(): widget.destroy()
            ctk.CTkLabel(self.scroll_frame, text=f"Fehler beim Laden aus der Datenbank: {e}").grid(row=0, column=0, pady=20)
            return
            
        self.filter_data()
        self.render_page()

    def filter_data(self):
        current_filter = self.filter_var.get()
        self.filtered_keys = []
        for key, data_obj in self.current_data.items():
            confirmed = data_obj['confirmed']
            if current_filter == "Bestätigt" and not confirmed: continue
            if current_filter == "Unbestätigt" and confirmed: continue
            self.filtered_keys.append(key)
            
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.render_page()
            
    def next_page(self):
        max_page = max(0, (len(self.filtered_keys) - 1) // self.items_per_page)
        if self.current_page < max_page:
            self.current_page += 1
            self.render_page()
            
    def render_page(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
        if not self.filtered_keys:
            ctk.CTkLabel(self.scroll_frame, text="Keine Einträge gefunden.").grid(row=0, column=0, pady=20)
            self.page_label.configure(text="Seite 1 / 1")
            return
            
        max_page = max(0, (len(self.filtered_keys) - 1) // self.items_per_page)
        self.page_label.configure(text=f"Seite {self.current_page + 1} / {max_page + 1} ({len(self.filtered_keys)} Einträge)")
        
        # Headers
        ctk.CTkLabel(self.scroll_frame, text="Kunde", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.scroll_frame, text="Lieferant", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.scroll_frame, text="Beschreibung", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.scroll_frame, text="Konto / Kategorie", font=ctk.CTkFont(weight="bold")).grid(row=0, column=3, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.scroll_frame, text="Bestätigt", font=ctk.CTkFont(weight="bold")).grid(row=0, column=4, padx=5, pady=5)
        ctk.CTkLabel(self.scroll_frame, text="Aktion", font=ctk.CTkFont(weight="bold")).grid(row=0, column=5, padx=5, pady=5)
        
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_keys = self.filtered_keys[start_idx:end_idx]
        
        row = 1
        client_name = self.get_client()
        
        for key in page_keys:
            data_obj = self.current_data[key]
            value = data_obj['value']
            confirmed = data_obj['confirmed']
            
            lieferant = key
            beschreibung = ""
            if " | " in key:
                parts = key.split(" | ", 1)
                lieferant = parts[0]
                beschreibung = parts[1]
                
            # Labels
            ctk.CTkLabel(self.scroll_frame, text=client_name, wraplength=120, justify="left").grid(row=row, column=0, padx=5, pady=2, sticky="w")
            ctk.CTkLabel(self.scroll_frame, text=lieferant, wraplength=150, justify="left").grid(row=row, column=1, padx=5, pady=2, sticky="w")
            ctk.CTkLabel(self.scroll_frame, text=beschreibung, wraplength=200, justify="left").grid(row=row, column=2, padx=5, pady=2, sticky="w")
            
            # Value entry
            val_str = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
            entry = ctk.CTkEntry(self.scroll_frame, width=150)
            entry.insert(0, val_str)
            entry.grid(row=row, column=3, padx=5, pady=2, sticky="ew")
            
            # Confirmed Checkbox
            confirmed_var = ctk.BooleanVar(value=confirmed)
            checkbox = ctk.CTkCheckBox(self.scroll_frame, text="", variable=confirmed_var, width=20)
            checkbox.grid(row=row, column=4, padx=5, pady=2)
            
            # Delete btn
            del_btn = ctk.CTkButton(self.scroll_frame, text="Löschen", width=60, fg_color="#cc0000", hover_color="#990000", 
                                    command=lambda k=key, r=row: self.mark_delete(k, r))
            del_btn.grid(row=row, column=5, padx=5, pady=2)
            
            if key not in self.entries:
                self.entries[key] = {"deleted": False}
            self.entries[key].update({"entry": entry, "widget_row": row, "del_btn": del_btn, "confirmed_var": confirmed_var})
            
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
            
    def delete_all(self):
        client = self.get_client()
        if not client:
            return
            
        try:
            from tkinter import messagebox
            if not messagebox.askyesno("Alle löschen", f"Möchtest du wirklich alle Einträge für {self.cache_type_var.get()} löschen?\nDies kann nicht rückgängig gemacht werden."):
                return
        except ImportError:
            pass
            
        try:
            db = get_db()
            db.delete_all_cache(self.cache_type_var.get(), client)
            self.show_status("Alle Einträge wurden gelöscht!", "green")
            self.load_data()
        except Exception as e:
            self.show_status(f"Fehler beim Löschen: {e}", "red")
            
    def save_data(self):
        client = self.get_client()
        if not client:
            return
            
        db = get_db()
        cache_type = self.cache_type_var.get()
        new_entries = {}
        
        try:
            for key, data in self.entries.items():
                if data.get("deleted"):
                    db.delete_cache_entry(cache_type, client, key)
                elif "entry" in data and data["entry"].winfo_exists():
                    val_str = data["entry"].get()
                    confirmed = data["confirmed_var"].get()
                    try:
                        if cache_type == "Sektorenanalyse":
                            parsed = json.loads(val_str)
                        else:
                            parsed = val_str
                        new_entries[key] = {'value': parsed, 'confirmed': confirmed}
                    except Exception as e:
                        print(f'Fehler: {e}')
                        new_entries[key] = {'value': val_str, 'confirmed': confirmed}
                        
            if new_entries:
                if cache_type == "Sektorenanalyse":
                    db.save_analyse_cache_batch(client, new_entries)
                else:
                    db.save_konten_cache_batch(client, new_entries)
                    
            self.show_status("Erfolgreich in der Datenbank gespeichert!", "green")
            self.load_data()
        except Exception as e:
            self.show_status(f"Fehler beim Speichern in DB: {e}", "red")
