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
        super().__init__(master, fg_color="transparent")
        self.current_client_callback = current_client_callback
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # --- 1. Header (Title) ---
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        
        self.title_label = ctk.CTkLabel(self.header_frame, text="🧠 KI-Training (Gedächtnis-Editor)", font=ctk.CTkFont(size=22, weight="bold"))
        self.title_label.pack(side="left")
        
        self.status_label = ctk.CTkLabel(self.header_frame, text="", font=ctk.CTkFont(weight="bold"))
        self.status_label.pack(side="right", padx=10)
        
        # --- 2. Controls Card ---
        self.controls_card = ctk.CTkFrame(self, fg_color=("white", "gray20"), corner_radius=10, border_width=1, border_color=("gray85", "gray15"))
        self.controls_card.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="ew")
        self.controls_card.grid_columnconfigure(5, weight=1)
        
        # Row 1: Such & Filter
        self.cache_type_var = ctk.StringVar(value="Sektorenanalyse")
        ctk.CTkOptionMenu(self.controls_card, values=["Sektorenanalyse", "FIBU Kontierung"], variable=self.cache_type_var, command=self.load_data, width=150).grid(row=0, column=0, padx=10, pady=10)
        
        self.filter_var = ctk.StringVar(value="Alle")
        ctk.CTkOptionMenu(self.controls_card, values=["Alle", "Bestätigt", "Unbestätigt"], variable=self.filter_var, command=self.apply_filters_and_render, width=120).grid(row=0, column=1, padx=10, pady=10)
        
        self.sort_var = ctk.StringVar(value="A-Z (Lieferant)")
        ctk.CTkOptionMenu(self.controls_card, values=["A-Z (Lieferant)", "Z-A (Lieferant)", "A-Z (Konto)"], variable=self.sort_var, command=self.apply_filters_and_render, width=140).grid(row=0, column=2, padx=10, pady=10)
        
        self.search_var = ctk.StringVar(value="")
        self.search_entry = ctk.CTkEntry(self.controls_card, placeholder_text="Suchen...", textvariable=self.search_var, width=200)
        self.search_entry.grid(row=0, column=3, padx=10, pady=10)
        self.search_entry.bind("<KeyRelease>", self.apply_filters_and_render)
        
        ctk.CTkButton(self.controls_card, text="↻", width=40, command=self.load_data).grid(row=0, column=4, padx=5, pady=10)
        
        # Row 2: Batch Actions
        batch_frame = ctk.CTkFrame(self.controls_card, fg_color="transparent")
        batch_frame.grid(row=1, column=0, columnspan=6, sticky="ew", padx=10, pady=(0, 10))
        
        self.master_check_var = ctk.BooleanVar(value=False)
        self.master_checkbox = ctk.CTkCheckBox(batch_frame, text="Alle gefilterten auswählen", variable=self.master_check_var, command=self.toggle_select_all, font=ctk.CTkFont(weight="bold"))
        self.master_checkbox.pack(side="left", padx=5)
        
        self.batch_confirm_btn = ctk.CTkButton(batch_frame, text="[✓] Ausgewählte bestätigen", command=self.batch_confirm, fg_color="#2b9e4a", hover_color="#217a39")
        self.batch_confirm_btn.pack(side="left", padx=15)
        
        self.batch_delete_btn = ctk.CTkButton(batch_frame, text="[✗] Ausgewählte löschen", command=self.batch_delete, fg_color="#cc0000", hover_color="#990000")
        self.batch_delete_btn.pack(side="left", padx=5)
        
        self.save_btn = ctk.CTkButton(batch_frame, text="💾 Manuelle Änderungen Speichern", command=self.save_data, fg_color="#e58e26", hover_color="#b36916")
        self.save_btn.pack(side="right", padx=5)
        
        # --- 3. Data Area ---
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color=("gray90", "gray15"), corner_radius=10)
        self.scroll_frame.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="nsew")
        self.scroll_frame.grid_columnconfigure(3, weight=1)
        
        # --- 4. Pagination ---
        self.pagination_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.pagination_frame.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")
        
        self.prev_btn = ctk.CTkButton(self.pagination_frame, text="< Zurück", command=self.prev_page, width=100)
        self.prev_btn.pack(side="left")
        
        self.page_label = ctk.CTkLabel(self.pagination_frame, text="Seite 1 / 1", font=ctk.CTkFont(weight="bold"))
        self.page_label.pack(side="left", expand=True)
        
        self.next_btn = ctk.CTkButton(self.pagination_frame, text="Weiter >", command=self.next_page, width=100)
        self.next_btn.pack(side="right")
        
        # State Variables
        self.entries = {}
        self.current_data = {}
        self.filtered_keys = []
        self.selected_keys = set()
        self.current_page = 0
        self.items_per_page = 50
        self.row_vars = {}

    def show_status(self, text, color="text"):
        self.status_label.configure(text=text, text_color=color)
        self.after(4000, lambda: self.status_label.configure(text=""))
        
    def get_client(self):
        client = self.current_client_callback()
        if not client or client == "Kein Kunde":
            return None
        return client
        
    def load_data(self, *args):
        client = self.get_client()
        if not client:
            for widget in self.scroll_frame.winfo_children(): widget.destroy()
            ctk.CTkLabel(self.scroll_frame, text="Bitte zuerst einen Kunden in der Seitenleiste auswählen!", font=ctk.CTkFont(size=16)).grid(row=0, column=0, pady=40, padx=20)
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
            ctk.CTkLabel(self.scroll_frame, text=f"Fehler beim Laden: {e}", text_color="red").grid(row=0, column=0, pady=20)
            return
            
        self.apply_filters_and_render()
        self.show_status("Daten geladen", "green")

    def apply_filters_and_render(self, *args):
        self.current_page = 0
        self.master_check_var.set(False)
        self.selected_keys.clear()
        
        current_filter = self.filter_var.get()
        search_text = self.search_var.get().lower().strip()
        sort_order = self.sort_var.get()
        
        temp_keys = []
        
        for key, data_obj in self.current_data.items():
            confirmed = data_obj['confirmed']
            val_str = str(data_obj['value']).lower()
            key_lower = key.lower()
            
            # Status Filter
            if current_filter == "Bestätigt" and not confirmed: continue
            if current_filter == "Unbestätigt" and confirmed: continue
            
            # Search Filter
            if search_text:
                if search_text not in key_lower and search_text not in val_str:
                    continue
                    
            temp_keys.append(key)
            
        # Sorting
        if sort_order == "A-Z (Lieferant)":
            temp_keys.sort(key=lambda x: x.split(" | ")[0] if " | " in x else x)
        elif sort_order == "Z-A (Lieferant)":
            temp_keys.sort(key=lambda x: x.split(" | ")[0] if " | " in x else x, reverse=True)
        elif sort_order == "A-Z (Konto)":
            temp_keys.sort(key=lambda x: str(self.current_data[x]['value']))
            
        self.filtered_keys = temp_keys
        self.render_page()

    def toggle_select_all(self):
        is_checked = self.master_check_var.get()
        if is_checked:
            self.selected_keys = set(self.filtered_keys)
        else:
            self.selected_keys.clear()
        self.render_page()
        
    def toggle_single_select(self, key, var):
        if var.get():
            self.selected_keys.add(key)
        else:
            self.selected_keys.discard(key)
            self.master_check_var.set(False)

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
        # Clear
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.row_vars.clear()
        self.entries.clear()
            
        if not self.filtered_keys:
            ctk.CTkLabel(self.scroll_frame, text="Keine Einträge gefunden.", font=ctk.CTkFont(size=14)).grid(row=0, column=0, pady=40, padx=20)
            self.page_label.configure(text="Seite 1 / 1 (0 Einträge)")
            return
            
        max_page = max(0, (len(self.filtered_keys) - 1) // self.items_per_page)
        self.page_label.configure(text=f"Seite {self.current_page + 1} von {max_page + 1}  ({len(self.filtered_keys)} gefiltert)")
        
        # Update Master Checkbox text based on count
        self.master_checkbox.configure(text=f"Alle {len(self.filtered_keys)} sichtbaren auswählen")
        
        # Headers
        headers = ["Status", "Lieferant", "Beschreibung", "Konto / Kategorie", "Auswahl"]
        for col, text in enumerate(headers):
            ctk.CTkLabel(self.scroll_frame, text=text, font=ctk.CTkFont(weight="bold", size=13), text_color="gray50").grid(row=0, column=col, padx=10, pady=(10, 5), sticky="w")
            
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_keys = self.filtered_keys[start_idx:end_idx]
        
        row = 1
        for key in page_keys:
            data_obj = self.current_data[key]
            value = data_obj['value']
            confirmed = data_obj['confirmed']
            
            lieferant = key
            beschreibung = "-"
            if " | " in key:
                parts = key.split(" | ", 1)
                lieferant = parts[0]
                beschreibung = parts[1]
                
            # Background styling for row (alternate colors maybe, but transparent is fine)
            
            # Status Indicator
            if confirmed:
                status_lbl = ctk.CTkLabel(self.scroll_frame, text="✅", text_color="green", width=30)
            else:
                status_lbl = ctk.CTkLabel(self.scroll_frame, text="⚠️", text_color="orange", width=30)
            status_lbl.grid(row=row, column=0, padx=5, pady=8)
            
            # Texts
            ctk.CTkLabel(self.scroll_frame, text=lieferant, wraplength=180, justify="left").grid(row=row, column=1, padx=10, pady=8, sticky="w")
            ctk.CTkLabel(self.scroll_frame, text=beschreibung, wraplength=250, justify="left").grid(row=row, column=2, padx=10, pady=8, sticky="w")
            
            # Value Entry (Editable)
            val_str = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
            entry = ctk.CTkEntry(self.scroll_frame, width=180)
            entry.insert(0, val_str)
            entry.grid(row=row, column=3, padx=10, pady=8, sticky="w")
            
            # Checkbox
            var = ctk.BooleanVar(value=(key in self.selected_keys))
            chk = ctk.CTkCheckBox(self.scroll_frame, text="", variable=var, width=20, command=lambda k=key, v=var: self.toggle_single_select(k, v))
            chk.grid(row=row, column=4, padx=10, pady=8)
            self.row_vars[key] = var
            
            self.entries[key] = {"entry": entry, "confirmed": confirmed}
            row += 1

    def batch_confirm(self):
        if not self.selected_keys:
            self.show_status("Nichts ausgewählt!", "orange")
            return
            
        client = self.get_client()
        db = get_db()
        cache_type = self.cache_type_var.get()
        new_entries = {}
        
        for key in self.selected_keys:
            if key in self.current_data:
                val = self.current_data[key]['value']
                # If they edited the entry on screen, we should grab the newest value, but batch confirm is bulk.
                # Let's check if it's on screen to grab the entry value:
                if key in self.entries:
                    val_str = self.entries[key]['entry'].get()
                    try:
                        val = json.loads(val_str) if cache_type == "Sektorenanalyse" else val_str
                    except:
                        val = val_str
                
                new_entries[key] = {'value': val, 'confirmed': True}
                self.current_data[key]['confirmed'] = True
                self.current_data[key]['value'] = val
                
        if cache_type == "Sektorenanalyse":
            db.save_analyse_cache_batch(client, new_entries)
        else:
            db.save_konten_cache_batch(client, new_entries)
            
        self.selected_keys.clear()
        self.master_check_var.set(False)
        self.apply_filters_and_render()
        self.show_status(f"{len(new_entries)} Einträge bestätigt!", "green")

    def batch_delete(self):
        if not self.selected_keys:
            self.show_status("Nichts ausgewählt!", "orange")
            return
            
        try:
            from tkinter import messagebox
            if not messagebox.askyesno("Löschen bestätigen", f"Möchtest du wirklich {len(self.selected_keys)} Einträge löschen?"):
                return
        except ImportError:
            pass
            
        client = self.get_client()
        db = get_db()
        cache_type = self.cache_type_var.get()
        
        for key in self.selected_keys:
            db.delete_cache_entry(cache_type, client, key)
            if key in self.current_data:
                del self.current_data[key]
                
        count = len(self.selected_keys)
        self.selected_keys.clear()
        self.master_check_var.set(False)
        self.apply_filters_and_render()
        self.show_status(f"{count} Einträge gelöscht!", "green")

    def save_data(self):
        # Saves manual edits of the visible entries
        client = self.get_client()
        db = get_db()
        cache_type = self.cache_type_var.get()
        new_entries = {}
        
        for key, data in self.entries.items():
            val_str = data["entry"].get()
            confirmed = data["confirmed"]
            try:
                if cache_type == "Sektorenanalyse":
                    parsed = json.loads(val_str)
                else:
                    parsed = val_str
                new_entries[key] = {'value': parsed, 'confirmed': confirmed}
                self.current_data[key]['value'] = parsed
            except Exception as e:
                new_entries[key] = {'value': val_str, 'confirmed': confirmed}
                self.current_data[key]['value'] = val_str
                
        if new_entries:
            if cache_type == "Sektorenanalyse":
                db.save_analyse_cache_batch(client, new_entries)
            else:
                db.save_konten_cache_batch(client, new_entries)
                
        self.show_status("Manuelle Änderungen gespeichert!", "green")
        self.render_page()
