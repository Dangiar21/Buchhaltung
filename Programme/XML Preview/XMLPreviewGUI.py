import customtkinter as ctk
import os

import base64
from tkinter import filedialog
from InvoiceParser import parse_invoice
from InvoicePDF import generate_invoice_pdf

# Helper für Monatsnamen

TRANSLATIONS_PREVIEW = {
    'IT': {
        'cedente': 'Cedente/prestatore (fornitore)',
        'cessionario': 'Cessionario/committente (cliente)',
        'id_fiscale': 'Identificativo fiscale ai fini IVA:',
        'cod_fiscale': 'Codice fiscale:',
        'denom': 'Denominazione:',
        'regime': 'Regime fiscale:',
        'ind': 'Indirizzo:',
        'comune': 'Comune:',
        'prov': 'Provincia:',
        'cap': 'Cap:',
        'naz': 'Nazione:',
        'tel': 'Telefono:',
        'email': 'Email:',
        'pec': 'Pec:',
        'terzo': 'Terzo Intermediario',
        'rif_amm': 'Riferimento Amministrazione:',
        'tipo_doc': 'Tipologia documento',
        'art73': 'Art. 73',
        'num_doc': 'Numero documento',
        'data_doc': 'Data documento',
        'cod_dest': 'Codice destinatario',
        'cod_art': 'Cod. articolo',
        'desc': 'Descrizione',
        'qta': 'Quantità',
        'prz_unit': 'Prezzo unitario',
        'um': 'UM',
        'sconto': 'Sconto o magg.',
        'iva': '%IVA',
        'prz_tot': 'Prezzo totale',
        'riepilogo': 'RIEPILOGHI IVA E TOTALI',
        'esig': 'esigibilità iva / riferimenti normativi',
        'spese': 'Spese accessorie',
        'arr': 'Arr.',
        'tot_imp': 'Totale imponibile',
        'tot_imposta': 'Totale imposta',
        'bollo': 'Importo bollo',
        'sconto_magg': 'Sconto/Maggiorazione',
        'tot_doc': 'Totale documento',
        'mod_pag': 'Modalità pagamento',
        'dettagli': 'Dettagli',
        'scadenze': 'Scadenze',
        'importo': 'Importo',
        'data_scad': 'Data scadenza',
        'data_term': 'Data termine',
        'gg': 'gg',
        'iban': 'IBAN',
        'cod_pag': 'Codice pagamento',
        'esig_i': 'I (esigibilità immediata)',
        'esig_s': 'S (scissione pagamenti)',
        'esig_d': 'D (esigibilità differita)',
        'natura': 'Natura',
        'view_sempl': 'Semplificata',
        'view_comp': 'Completa',
        'view_min': 'Ministeriale',
        'all_cedenti': 'Tutti i Fornitori',
        'all_cessionari': 'Tutti i Clienti',
        'search': 'Cerca...',
        'file_not_found': 'File XMLPreviewGUI.py non trovato',
        'dati_gen_doc': 'Dati Generali Documento',
        'cedente_prest': 'Cedente / Prestatore',
        'cessionario_comm': 'Cessionario / Committente',
        'dettaglio_linee': 'Dettaglio Linee',
        'num_linea': 'Numero linea:',
        'codice_art': 'Codice articolo:',
        'unita_mis': 'Unità di misura:',
        'aliquota_iva': 'Aliquota IVA:',
        'altri_dati': 'Altri Dati Gestionali:',
        'dati_riep': 'Dati Riepilogo',
        'dati_pag': 'Dati Pagamento',
        'data_scad_pag': 'Data scadenza pagamento:',
        'importo_pag': 'Importo pagamento:',
        'pec_dest': 'PEC Destinatario:',
        'cod_dest2': 'Codice Destinatario:'
    },
    'DE': {
        'cedente': 'Lieferant / Dienstleister',
        'cessionario': 'Kunde / Auftraggeber',
        'id_fiscale': 'USt-IdNr.:',
        'cod_fiscale': 'Steuernummer:',
        'denom': 'Firmenname / Name:',
        'regime': 'Steuerregime:',
        'ind': 'Adresse:',
        'comune': 'Gemeinde:',
        'prov': 'Provinz:',
        'cap': 'PLZ:',
        'naz': 'Land:',
        'tel': 'Telefon:',
        'email': 'E-Mail:',
        'pec': 'PEC-Mail:',
        'terzo': 'Dritter Vermittler',
        'rif_amm': 'Verwaltungsreferenz:',
        'tipo_doc': 'Dokumenttyp',
        'art73': 'Art. 73',
        'num_doc': 'Dokumentnummer',
        'data_doc': 'Belegdatum',
        'cod_dest': 'Empfängercode',
        'cod_art': 'Art.-Nr.',
        'desc': 'Beschreibung',
        'qta': 'Menge',
        'prz_unit': 'Einzelpreis',
        'um': 'ME',
        'sconto': 'Rabatt / Aufschlag',
        'iva': '%MwSt',
        'prz_tot': 'Gesamtpreis',
        'riepilogo': 'MWST-ZUSAMMENFASSUNG & GESAMTBETRÄGE',
        'esig': 'Fälligkeit / Gesetzliche Referenzen',
        'spese': 'Nebenkosten',
        'arr': 'Rundung',
        'tot_imp': 'Steuergrundlage',
        'tot_imposta': 'Steuerbetrag',
        'bollo': 'Stempelsteuer',
        'sconto_magg': 'Rabatt / Aufschlag',
        'tot_doc': 'Gesamtbetrag',
        'mod_pag': 'Zahlungsart',
        'dettagli': 'Details',
        'scadenze': 'Fälligkeiten',
        'importo': 'Betrag',
        'data_scad': 'Fälligkeitsdatum',
        'data_term': 'Zahlungsziel',
        'gg': 'Tage',
        'iban': 'IBAN',
        'cod_pag': 'Zahlungscode',
        'esig_i': 'I (Sofort fällig)',
        'esig_s': 'S (Split Payment)',
        'esig_d': 'D (Aufgeschobene Fälligkeit)',
        'natura': 'Natur',
        'view_sempl': 'Vereinfacht',
        'view_comp': 'Vollständig',
        'view_min': 'Ministeriell',
        'all_cedenti': 'Alle Lieferanten',
        'all_cessionari': 'Alle Empfänger',
        'search': 'Suchen...',
        'file_not_found': 'Fehler: XMLPreviewGUI.py nicht gefunden',
        'dati_gen_doc': 'Allgemeine Dokumentendaten',
        'cedente_prest': 'Lieferant / Dienstleister',
        'cessionario_comm': 'Kunde / Auftraggeber',
        'dettaglio_linee': 'Zeilendetails',
        'num_linea': 'Zeilennummer:',
        'codice_art': 'Artikelcode:',
        'unita_mis': 'Maßeinheit:',
        'aliquota_iva': 'MwSt-Satz:',
        'altri_dati': 'Sonstige Verwaltungsdaten:',
        'dati_riep': 'Zusammenfassung',
        'dati_pag': 'Zahlungsdaten',
        'data_scad_pag': 'Fälligkeitsdatum Zahlung:',
        'importo_pag': 'Zahlungsbetrag:',
        'pec_dest': 'PEC-Mail Empfänger:',
        'cod_dest2': 'Empfängercode:'
    }
}

def get_iso_date(d):
    if d and len(d) == 10 and d[2] == '.' and d[5] == '.':
        return f"{d[6:]}-{d[3:5]}-{d[:2]}"
    return d

MONTH_NAMES = {
    "01": "Januar", "02": "Februar", "03": "März", "04": "April",
    "05": "Mai", "06": "Juni", "07": "Juli", "08": "August",
    "09": "September", "10": "Oktober", "11": "November", "12": "Dezember"
}

class XMLPreviewFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        # Grid Layout
        self.grid_rowconfigure(0, weight=0) # Top Bar
        self.grid_rowconfigure(1, weight=1) # Content
        
        self.grid_columnconfigure(0, weight=0, minsize=250) # Left Filters
        self.grid_columnconfigure(1, weight=0, minsize=350) # Middle List
        self.grid_columnconfigure(2, weight=1)              # Right Preview
        
        self.lang = "DE"
        self.all_invoices = []
        self.filtered_invoices = []
        
        # Filter States
        self.selected_year = None
        self.selected_months = set()
        self.selected_cedente = None
        self.selected_cessionario = None
        
        # Initialize UI elements to avoid AttributeError
        self.settings_popup = None
        self.month_popup = None
        self.lbl_path = None
        self.paper = None
        self.current_view = None
        
        # --- Top Bar (Years and Months) ---
        self.top_bar = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray85", "gray17"))
        self.top_bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.top_bar.grid_columnconfigure(1, weight=1)
        
        self.btn_settings = ctk.CTkButton(self.top_bar, text="⋮", width=40, fg_color="transparent", text_color=("black", "white"), font=ctk.CTkFont(size=28, weight="bold"), command=self.open_settings)
        self.btn_settings.grid(row=0, column=0, rowspan=2, padx=10, pady=10)
        
        self.year_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.year_frame.grid(row=0, column=1, sticky="w", padx=10, pady=(10, 2))
        
        self.month_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.month_frame.grid(row=1, column=1, sticky="w", padx=10, pady=(2, 10))
        
        # --- Left Column (Person Filters) ---
        self.left_sidebar = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray90", "gray13"))
        self.left_sidebar.grid(row=1, column=0, sticky="nsew")
        self.left_sidebar.grid_rowconfigure(1, weight=1) # Cedente List
        self.left_sidebar.grid_rowconfigure(3, weight=1) # Cessionario List
        self.left_sidebar.grid_columnconfigure(0, weight=1)
        
        # Cedente (Absender)
        self.search_cedente = ctk.CTkEntry(self.left_sidebar, placeholder_text="Absender suchen...")
        self.search_cedente.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.search_cedente.bind("<KeyRelease>", lambda e: self.render_cedenti())
        
        self.list_cedenti = ctk.CTkScrollableFrame(self.left_sidebar, fg_color="transparent")
        self.list_cedenti.grid(row=1, column=0, sticky="nsew", padx=5)
        
        # Divider
        ctk.CTkFrame(self.left_sidebar, height=2, fg_color=("gray70", "gray30")).grid(row=2, column=0, sticky="ew", pady=5)
        
        # Cessionario (Empfänger)
        self.search_cessionario = ctk.CTkEntry(self.left_sidebar, placeholder_text="Empfänger suchen...")
        self.search_cessionario.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        self.search_cessionario.bind("<KeyRelease>", lambda e: self.render_cessionari())
        
        self.list_cessionari = ctk.CTkScrollableFrame(self.left_sidebar, fg_color="transparent")
        self.list_cessionari.grid(row=5, column=0, sticky="nsew", padx=5, pady=(0, 10))
        
        # --- Middle Column (Invoice List) ---
        self.middle_list = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray85", "gray17"))
        self.middle_list.grid(row=1, column=1, sticky="nsew")
        self.middle_list.grid_rowconfigure(1, weight=1)
        self.middle_list.grid_columnconfigure(0, weight=1)
        
        lbl_list = ctk.CTkLabel(self.middle_list, text="Rechnungen", font=ctk.CTkFont(weight="bold"))
        lbl_list.grid(row=0, column=0, pady=10)
        
        self.list_invoices = ctk.CTkScrollableFrame(self.middle_list)
        self.list_invoices.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.list_invoices.grid_columnconfigure(0, weight=1)
        
        # --- Right Column (Preview) ---
        self.right_frame = ctk.CTkScrollableFrame(self)
        self.right_frame.grid(row=1, column=2, sticky="nsew", padx=10, pady=10)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(1, weight=1)
        
        self.placeholder = ctk.CTkLabel(self.right_frame, text="Wähle eine Rechnung aus der Liste", font=ctk.CTkFont(size=18))
        self.placeholder.grid(row=0, column=0, columnspan=2, pady=50)
        
        self.current_invoice = None
        
        self.unique_years = []
        self.unique_months = []
        self.cedenti_counts = {}
        self.cessionari_counts = {}
        self.current_folder = ""
        
        # Config logic removed to avoid conflict with main GUI.
        
        # Populate initial empty state for top bar
        self.render_top_bar()

    def open_folder(self):
        if hasattr(self, 'settings_popup') and self.settings_popup is not None and self.settings_popup.winfo_exists():
            self.settings_popup.destroy()
            
        folder = filedialog.askdirectory(title="Wähle einen Ordner mit Rechnungen")
        if folder:
            self.current_folder = folder
            if hasattr(self, 'lbl_path') and self.lbl_path.winfo_exists():
                self.lbl_path.configure(text=folder)
            self.load_directory(folder)
            
    def open_settings(self):
        if hasattr(self, 'settings_popup') and self.settings_popup is not None and self.settings_popup.winfo_exists():
            self.settings_popup.destroy()
            return
            
        self.settings_popup = ctk.CTkToplevel(self)
        self.settings_popup.title("Einstellungen")
        self.settings_popup.geometry("500x200")
        self.settings_popup.attributes('-topmost', 'true')
        
        lbl_title = ctk.CTkLabel(self.settings_popup, text="EINSTELLUNGEN:", font=ctk.CTkFont(size=16, weight="bold"), text_color="#3a7ebf")
        lbl_title.pack(anchor="w", padx=20, pady=(20, 10))
        
        lbl_desc = ctk.CTkLabel(self.settings_popup, text="Arbeitsverzeichnis auswählen:")
        lbl_desc.pack(anchor="w", padx=20)
        
        row_frame = ctk.CTkFrame(self.settings_popup, fg_color="transparent")
        row_frame.pack(fill="x", padx=20, pady=10)
        
        btn_refresh = ctk.CTkButton(row_frame, text="↻", width=40, font=ctk.CTkFont(size=18), command=lambda: self.load_directory(self.current_folder) if self.current_folder else None)
        btn_refresh.pack(side="left", padx=(0, 5))
        
        btn_folder = ctk.CTkButton(row_frame, text="📁", width=40, font=ctk.CTkFont(size=18), command=self.open_folder)
        btn_folder.pack(side="left", padx=5)
        
        path_text = self.current_folder if self.current_folder else "Kein Ordner ausgewählt"
        self.lbl_path = ctk.CTkLabel(row_frame, text=path_text, text_color="#3a7ebf", font=ctk.CTkFont(weight="bold"), wraplength=350, justify="left")
        self.lbl_path.pack(side="left", padx=10)
            
    def load_directory(self, folder):
        self.lang = "DE"
        self.all_invoices = []
        try:
            for root_dir, dirs, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith('.xml') or f.lower().endswith('.p7m'):
                        filepath = os.path.join(root_dir, f)
                        inv = parse_invoice(filepath)
                        if inv:
                            self.all_invoices.append(inv)
        except Exception as e:
            print("Fehler beim Lesen des Ordners:", e)
            return

        def sort_key(x):
            return get_iso_date(x.get('dati_generali', {}).get('Data', ''))
        self.all_invoices = sorted(self.all_invoices, key=sort_key, reverse=True)
        
        # Reset filters
        self.selected_year = None
        self.selected_months = set()
        self.selected_cedente = None
        self.selected_cessionario = None
        
        self.extract_filter_data()
        self.render_top_bar()
        self.render_cedenti()
        self.render_cessionari()
        self.apply_filters()
        
        # Save to config removed
        
    def extract_filter_data(self):
        years = set()
        for inv in self.all_invoices:
            data = get_iso_date(inv.get('dati_generali', {}).get('Data', ''))
            if data and len(data) >= 4:
                years.add(data[:4])
        self.unique_years = sorted(list(years))
        
        # Cedenti and Cessionari are extracted dynamically based on time filters in apply_filters
        
    def render_top_bar(self):
        for w in self.year_frame.winfo_children(): w.destroy()
        for w in self.month_frame.winfo_children(): w.destroy()
        
        # Years
        color = ("#3a7ebf", "#1f538d") if self.selected_year is None else "transparent"
        t_color = "white" if self.selected_year is None else ("black", "white")
        btn_all_y = ctk.CTkButton(self.year_frame, text="Alle Jahre", fg_color=color, text_color=t_color, command=lambda: self.set_year(None))
        btn_all_y.pack(side="left", padx=5)
        
        for y in self.unique_years:
            color = ("#3a7ebf", "#1f538d") if self.selected_year == y else "transparent"
            t_color = "white" if self.selected_year == y else ("black", "white")
            btn = ctk.CTkButton(self.year_frame, text=y, fg_color=color, text_color=t_color, command=lambda y=y: self.set_year(y))
            btn.pack(side="left", padx=5)
            
        # Months
        color = ("#3a7ebf", "#1f538d") if not self.selected_months else "transparent"
        t_color = "white" if not self.selected_months else ("black", "white")
        btn_all_m = ctk.CTkButton(self.month_frame, text="Alle Monate", fg_color=color, text_color=t_color, command=lambda: self.set_month(None), width=80)
        btn_all_m.pack(side="left", padx=2)
        
        for m_num, m_name in MONTH_NAMES.items():
            color = ("#3a7ebf", "#1f538d") if m_num in self.selected_months else "transparent"
            t_color = "white" if m_num in self.selected_months else ("black", "white")
            btn = ctk.CTkButton(self.month_frame, text=m_name, fg_color=color, text_color=t_color, command=lambda m=m_num: self.set_month(m), width=50)
            btn.pack(side="left", padx=2)
            
        btn_multi = ctk.CTkButton(self.month_frame, text="▼", width=30, fg_color="transparent", text_color=("black", "white"), command=self.open_month_multiselect)
        btn_multi.pack(side="left", padx=2)
            
    def set_year(self, y):
        self.selected_year = y
        self.render_top_bar()
        self.apply_filters()
        
    def set_month(self, m):
        if m is None:
            self.selected_months = set()
        else:
            self.selected_months = {m}
        self.render_top_bar()
        self.apply_filters()

    def toggle_month(self, m, var):
        if var.get() == "on":
            self.selected_months.add(m)
        else:
            if m in self.selected_months:
                self.selected_months.remove(m)
        self.render_top_bar()
        self.apply_filters()
        
    def open_month_multiselect(self):
        if hasattr(self, 'month_popup') and self.month_popup is not None and self.month_popup.winfo_exists():
            self.month_popup.destroy()
            return
            
        self.month_popup = ctk.CTkToplevel(self)
        self.month_popup.title("Monate")
        self.month_popup.geometry("200x420")
        self.month_popup.attributes('-topmost', 'true')
        
        for m_num, m_name in MONTH_NAMES.items():
            is_on = True if not self.selected_months or m_num in self.selected_months else False
            var = ctk.StringVar(value="on" if is_on else "off")
            cb = ctk.CTkCheckBox(self.month_popup, text=m_name, variable=var, onvalue="on", offvalue="off", command=lambda m=m_num, v=var: self.toggle_month(m, v))
            cb.pack(anchor="w", padx=15, pady=5)
        
    def set_cedente(self, c):
        self.selected_cedente = c
        self.render_cedenti()
        self.apply_filters()
        
    def set_cessionario(self, c):
        self.selected_cessionario = c
        self.render_cessionari()
        self.apply_filters()

    def update_counts_based_on_time(self):
        # Filter invoices only by time to calculate person counts
        time_filtered = []
        for inv in self.all_invoices:
            data = get_iso_date(inv.get('dati_generali', {}).get('Data', ''))
            if self.selected_year and not data.startswith(self.selected_year):
                continue
            if self.selected_months and len(data) >= 7 and data[5:7] not in self.selected_months:
                continue
            time_filtered.append(inv)
            
        self.cedenti_counts = {}
        self.cessionari_counts = {}
        
        for inv in time_filtered:
            mit = inv.get('mittente', {}).get('Denominazione', 'Unbekannt')
            dest = inv.get('destinatario', {}).get('Denominazione', 'Unbekannt')
            
            self.cedenti_counts[mit] = self.cedenti_counts.get(mit, 0) + 1
            self.cessionari_counts[dest] = self.cessionari_counts.get(dest, 0) + 1

    def render_cedenti(self):
        for w in self.list_cedenti.winfo_children(): w.destroy()
        
        q = self.search_cedente.get().lower()
        
        # All Button
        color = ("#3a7ebf", "#1f538d") if self.selected_cedente is None else "transparent"
        total = sum(self.cedenti_counts.values())
        btn = ctk.CTkButton(self.list_cedenti, text=f"({total}) Alle Absender", anchor="w", fg_color=color, text_color=("black", "white"), command=lambda: self.set_cedente(None))
        btn.pack(fill="x", pady=2)
        
        for name, count in sorted(self.cedenti_counts.items()):
            if q and q not in name.lower(): continue
            
            color = ("#3a7ebf", "#1f538d") if self.selected_cedente == name else "transparent"
            disp_name = name if len(name) < 25 else name[:22] + "..."
            btn = ctk.CTkButton(self.list_cedenti, text=f"({count}) {disp_name}", anchor="w", fg_color=color, text_color=("black", "white"), command=lambda n=name: self.set_cedente(n))
            btn.pack(fill="x", pady=2)
            
    def render_cessionari(self):
        for w in self.list_cessionari.winfo_children(): w.destroy()
        
        q = self.search_cessionario.get().lower()
        
        # All Button
        color = ("#3a7ebf", "#1f538d") if self.selected_cessionario is None else "transparent"
        total = sum(self.cessionari_counts.values())
        btn = ctk.CTkButton(self.list_cessionari, text=f"({total}) Alle Empfänger", anchor="w", fg_color=color, text_color=("black", "white"), command=lambda: self.set_cessionario(None))
        btn.pack(fill="x", pady=2)
        
        for name, count in sorted(self.cessionari_counts.items()):
            if q and q not in name.lower(): continue
            
            color = ("#3a7ebf", "#1f538d") if self.selected_cessionario == name else "transparent"
            disp_name = name if len(name) < 25 else name[:22] + "..."
            btn = ctk.CTkButton(self.list_cessionari, text=f"({count}) {disp_name}", anchor="w", fg_color=color, text_color=("black", "white"), command=lambda n=name: self.set_cessionario(n))
            btn.pack(fill="x", pady=2)

    def apply_filters(self):
        # First update counts based on time selection only
        self.update_counts_based_on_time()
        self.render_cedenti()
        self.render_cessionari()
        
        self.filtered_invoices = []
        for inv in self.all_invoices:
            data = get_iso_date(inv.get('dati_generali', {}).get('Data', ''))
            mit = inv.get('mittente', {}).get('Denominazione', 'Unbekannt')
            dest = inv.get('destinatario', {}).get('Denominazione', 'Unbekannt')
            
            if self.selected_year and not data.startswith(self.selected_year):
                continue
            if self.selected_months and len(data) >= 7 and data[5:7] not in self.selected_months:
                continue
            if self.selected_cedente and mit != self.selected_cedente:
                continue
            if self.selected_cessionario and dest != self.selected_cessionario:
                continue
                
            self.filtered_invoices.append(inv)
            
        self.render_invoice_list()
        
    def render_invoice_list(self):
        for widget in self.list_invoices.winfo_children():
            widget.destroy()
            
        for row_idx, inv in enumerate(self.filtered_invoices):
            mit = inv.get('mittente', {}).get('Denominazione', 'Unbekannt')
            if len(mit) > 25: mit = mit[:25] + "..."
            num = inv.get('dati_generali', {}).get('Numero', '?')
            data = inv.get('dati_generali', {}).get('Data', '?')
            tot = inv.get('dati_generali', {}).get('ImportoTotaleDocumento', '?')
            
            btn = ctk.CTkButton(self.list_invoices, text=f"📄 {mit}\n#{num} | {data} | {tot}€", 
                                anchor="w", height=50, fg_color="transparent", 
                                text_color=("gray10", "gray90"), border_width=1,
                                command=lambda i=inv: self.show_invoice(i))
            btn.grid(row=row_idx, column=0, pady=2, sticky="ew")

    def set_language(self, lang):
        self.lang = lang
        if hasattr(self, 'current_invoice') and self.current_invoice:
            self.show_invoice(self.current_invoice)

    def show_invoice(self, inv):
        self.current_invoice = inv
        for widget in self.right_frame.winfo_children():
            widget.destroy()
            
        self.render_toolbar(inv)
        
        self.paper = ctk.CTkFrame(self.right_frame, fg_color=("white", "gray10"), corner_radius=5, border_width=1, border_color=("gray70", "gray30"))
        self.paper.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=20, pady=10)
        self.paper.grid_columnconfigure(0, weight=1)
        
        self.update_view()
        
    def render_toolbar(self, inv):
        t = TRANSLATIONS_PREVIEW[self.lang]
        toolbar = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        toolbar.grid_columnconfigure(1, weight=1)
        
        if not hasattr(self, 'current_view'):
            self.current_view = ctk.StringVar(value=t["view_comp"])
            
        def on_view_change(choice):
            self.update_view()
            
        view_menu = ctk.CTkOptionMenu(toolbar, values=[t["view_comp"], t["view_sempl"], t["view_min"]], variable=self.current_view, command=on_view_change)
        view_menu.grid(row=0, column=0, padx=(10, 20), sticky="w")
        
        mit = inv.get('mittente', {})
        den = mit.get('Denominazione', '')
        piva = mit.get('PartitaIVA', '')
        pec = inv.get('destinatario', {}).get('PECDestinatario', '') 
        
        mit_text = f"👤 {den}"
        if piva:
            mit_text += f" ({piva}"
            if pec:
                mit_text += f" - {pec}"
            mit_text += ")"
            
        lbl_supplier = ctk.CTkLabel(toolbar, text=mit_text, font=ctk.CTkFont(size=14, weight="bold"))
        lbl_supplier.grid(row=0, column=1, sticky="w")
        
        btn_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_frame.grid(row=0, column=2, sticky="e", padx=(20, 10))
        
        btn_folder = ctk.CTkButton(btn_frame, text="📁", width=36, height=36, font=ctk.CTkFont(size=18), corner_radius=18, fg_color="transparent", border_width=2, text_color=("black", "white"), command=self.open_current_folder)
        btn_folder.pack(side="left", padx=3)
        
        btn_download = ctk.CTkButton(btn_frame, text="📥", width=36, height=36, font=ctk.CTkFont(size=18), corner_radius=18, fg_color="transparent", border_width=2, text_color=("black", "white"), command=self.export_pdf)
        btn_download.pack(side="left", padx=3)
        
        btn_print = ctk.CTkButton(btn_frame, text="🖨", width=36, height=36, font=ctk.CTkFont(size=18), corner_radius=18, fg_color="transparent", border_width=2, text_color=("black", "white"), command=self.print_invoice)
        btn_print.pack(side="left", padx=3)
        
        btn_sign = ctk.CTkButton(btn_frame, text="✏", width=36, height=36, font=ctk.CTkFont(size=18), corner_radius=18, fg_color="transparent", border_width=2, text_color=("black", "white"), command=self.show_signature)
        if not inv.get('signature_info'):
            btn_sign.configure(state="disabled")
        btn_sign.pack(side="left", padx=3)
        
        btn_attach = ctk.CTkButton(btn_frame, text="📎", width=36, height=36, font=ctk.CTkFont(size=18), corner_radius=18, fg_color="transparent", border_width=2, text_color=("black", "white"), command=self.open_attachments)
        if not inv.get('allegati'):
            btn_attach.configure(state="disabled")
        btn_attach.pack(side="left", padx=3)
        
    def update_view(self):
        t = TRANSLATIONS_PREVIEW[self.lang]
        for widget in self.paper.winfo_children():
            widget.destroy()
            
        view = self.current_view.get()
        if view == t["view_min"]:
            self.render_ministeriale(self.paper, self.current_invoice)
        else:
            is_completa = (view == t["view_comp"])
            self.render_semplificata_completa(self.paper, self.current_invoice, is_completa)
            
    def render_semplificata_completa(self, paper, inv, is_completa):
        t = TRANSLATIONS_PREVIEW[self.lang]
        pad_x = 10
        
        lbl_filename = ctk.CTkLabel(paper, text=inv.get('filename', ''), font=ctk.CTkFont(size=14, weight="bold"))
        lbl_filename.grid(row=0, column=0, pady=(15, 15))
        
        box_container = ctk.CTkFrame(paper, fg_color="transparent")
        box_container.grid(row=1, column=0, sticky="ew", padx=pad_x)
        box_container.grid_columnconfigure(0, weight=1)
        box_container.grid_columnconfigure(1, weight=1)
        
        def create_border_frame(parent):
            return ctk.CTkFrame(parent, fg_color="transparent", border_width=2, border_color=("black", "gray60"), corner_radius=0)
            
        def create_info_line(parent, label, value):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(anchor="w", padx=10, pady=1, fill="x")
            ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkLabel(f, text=value, font=ctk.CTkFont(size=12, weight="bold")).pack(side="right", padx=5)
            
        mit = inv.get('mittente', {})
        dest = inv.get('destinatario', {})
        
        cedente_frame = create_border_frame(box_container)
        cedente_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        ctk.CTkLabel(cedente_frame, text=t['cedente'], font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=10, pady=(5, 5))
        create_info_line(cedente_frame, t['id_fiscale'], mit.get('PartitaIVA', ''))
        create_info_line(cedente_frame, t['cod_fiscale'], mit.get('CodiceFiscale', ''))
        create_info_line(cedente_frame, t['denom'], mit.get('Denominazione', ''))
        if is_completa and mit.get('RegimeFiscale'):
            create_info_line(cedente_frame, t['regime'], mit.get('RegimeFiscale'))
        create_info_line(cedente_frame, t['ind'], mit.get('Indirizzo', ''))
        create_info_line(cedente_frame, t['comune'], f"{mit.get('Comune', '')} Provincia: {mit.get('Provincia', '')}")
        create_info_line(cedente_frame, t['cap'], f"{mit.get('CAP', '')} Nazione: {mit.get('Nazione', '')}")
        if is_completa and mit.get('Telefono'):
            create_info_line(cedente_frame, t['tel'], mit.get('Telefono'))
        if is_completa and mit.get('Email'):
            create_info_line(cedente_frame, t['email'], mit.get('Email'))
            
        terzo = inv.get('terzo_intermediario', {})
        if is_completa and terzo:
            ctk.CTkLabel(cedente_frame, text=t['terzo'], font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
            create_info_line(cedente_frame, t['id_fiscale'], terzo.get('PartitaIVA', ''))
            create_info_line(cedente_frame, t['denom'], terzo.get('Denominazione', ''))
            
        rif_amm = mit.get('RiferimentoAmministrazione', '')
        if rif_amm: create_info_line(cedente_frame, t['rif_amm'], rif_amm)
        ctk.CTkFrame(cedente_frame, width=0, height=0, fg_color="transparent").pack(pady=(0, 15))
        
        cess_frame = create_border_frame(box_container)
        cess_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        ctk.CTkLabel(cess_frame, text=t['cessionario'], font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=10, pady=(5, 5))
        create_info_line(cess_frame, t['id_fiscale'], dest.get('PartitaIVA', ''))
        create_info_line(cess_frame, t['cod_fiscale'], dest.get('CodiceFiscale', ''))
        create_info_line(cess_frame, t['denom'], dest.get('Denominazione', ''))
        create_info_line(cess_frame, t['ind'], dest.get('Indirizzo', ''))
        create_info_line(cess_frame, t['comune'], f"{dest.get('Comune', '')} Provincia: {dest.get('Provincia', '')}")
        create_info_line(cess_frame, t['cap'], f"{dest.get('CAP', '')} Nazione: {dest.get('Nazione', '')}")
        pec = dest.get('PECDestinatario', '')
        if pec: create_info_line(cess_frame, t['pec'], pec)
        ctk.CTkFrame(cess_frame, width=0, height=0, fg_color="transparent").pack(pady=(0, 15))

        gen = inv.get('dati_generali', {})
        gen_headers = [t['tipo_doc'], t['art73'], t['num_doc'], t['data_doc'], t['cod_dest']]
        gen_values = [gen.get('TipoDocumento', ''), gen.get('Art73', ''), gen.get('Numero', ''), gen.get('Data', ''), dest.get('CodiceDestinatario', '')]
        
        gen_table = create_border_frame(paper)
        gen_table.grid(row=2, column=0, sticky="ew", padx=pad_x, pady=(15, 0))
        
        for i, h in enumerate(gen_headers):
            gen_table.grid_columnconfigure(i, weight=1, uniform="gen")
            cell = ctk.CTkFrame(gen_table, fg_color=("gray90", "gray25"), border_width=1, border_color=("black", "gray60"), corner_radius=0)
            cell.grid(row=0, column=i, sticky="nsew")
            ctk.CTkLabel(cell, text=h, font=ctk.CTkFont(size=12, weight="bold")).pack(pady=2, padx=5)
            
            cell_v = ctk.CTkFrame(gen_table, fg_color="transparent", border_width=1, border_color=("black", "gray60"), corner_radius=0)
            cell_v.grid(row=1, column=i, sticky="nsew")
            ctk.CTkLabel(cell_v, text=gen_values[i], font=ctk.CTkFont(size=12)).pack(pady=2, padx=5)
            
        lin_table = create_border_frame(paper)
        lin_table.grid(row=3, column=0, sticky="ew", padx=pad_x, pady=(15, 0))
        lin_headers = [t['cod_art'], t['desc'], t['qta'], t['prz_unit'], t['um'], t['sconto'], t['iva'], t['prz_tot']]
        lin_weights = [1, 4, 1, 1, 1, 1, 1, 1]
        
        for i, h in enumerate(lin_headers):
            lin_table.grid_columnconfigure(i, weight=lin_weights[i])
            cell = ctk.CTkFrame(lin_table, fg_color=("gray90", "gray25"), border_width=1, border_color=("black", "gray60"), corner_radius=0)
            cell.grid(row=0, column=i, sticky="nsew")
            ctk.CTkLabel(cell, text=h, font=ctk.CTkFont(size=12, weight="bold")).pack(pady=2, padx=5)
            
        for r_idx, l in enumerate(inv.get('linee', [])):
            desc = l.get('Descrizione', '')
            if is_completa:
                adg_list = l.get('AltriDatiGestionali', [])
                for adg in adg_list:
                    parts = []
                    if adg.get('TipoDato'): parts.append(adg['TipoDato'])
                    if adg.get('RiferimentoTesto'): parts.append(adg['RiferimentoTesto'])
                    if adg.get('RiferimentoNumero'): parts.append(adg['RiferimentoNumero'])
                    if adg.get('RiferimentoData'): parts.append(adg['RiferimentoData'])
                    if parts:
                        desc += f"\n[{' - '.join(parts)}]"
                        
            vals = [
                l.get('CodiceArticolo', ''),
                desc,
                l.get('Quantita', ''),
                l.get('PrezzoUnitario', ''),
                l.get('UnitaMisura', ''),
                l.get('ScontoMaggiorazione', ''),
                l.get('AliquotaIVA', ''),
                l.get('PrezzoTotale', '')
            ]
            for c_idx, v in enumerate(vals):
                cell = ctk.CTkFrame(lin_table, fg_color="transparent", border_width=1, border_color=("black", "gray60"), corner_radius=0)
                cell.grid(row=r_idx+1, column=c_idx, sticky="nsew")
                
                wraplen = 250 if c_idx == 1 else 0
                justify = "left" if c_idx == 1 else "right"
                anchor = "w" if c_idx == 1 else "e"
                
                lbl = ctk.CTkLabel(cell, text=v, font=ctk.CTkFont(size=12), wraplength=wraplen, justify=justify)
                lbl.pack(pady=2, padx=5, anchor=anchor)
                
        riep_title = ctk.CTkFrame(paper, fg_color="#b2dfdb", border_width=1, border_color=("black", "gray60"), corner_radius=0)
        riep_title.grid(row=4, column=0, sticky="ew", padx=pad_x, pady=(15, 0))
        ctk.CTkLabel(riep_title, text=t['riepilogo'], text_color="black", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=2)
        
        riep_table = create_border_frame(paper)
        riep_table.grid(row=5, column=0, sticky="ew", padx=pad_x)
        
        r_headers = [t['esig'], t['iva'], t['spese'], t['arr'], t['tot_imp'], t['tot_imposta']]
        r_weights = [3, 1, 1, 1, 2, 2]
        
        for i, h in enumerate(r_headers):
            riep_table.grid_columnconfigure(i, weight=r_weights[i])
            cell = ctk.CTkFrame(riep_table, fg_color=("gray90", "gray25"), border_width=1, border_color=("black", "gray60"), corner_radius=0)
            cell.grid(row=0, column=i, sticky="nsew")
            ctk.CTkLabel(cell, text=h, font=ctk.CTkFont(size=12, weight="bold")).pack(pady=2, padx=5)
            
        riep_items = inv.get('riepilogo', [])
        for r_idx, r in enumerate(riep_items):
            nat = r.get('Natura', '')
            esig = r.get('EsigibilitaIVA', '')
            rif = r.get('RiferimentoNormativo', '')
            desc_str = ""
            if esig == "I": desc_str = t['esig_i']
            elif esig == "S": desc_str = t['esig_s']
            elif esig == "D": desc_str = t['esig_d']
            if nat: desc_str = f"Natura {nat} " + desc_str
            if rif: desc_str += f" - {rif}"
            
            vals = [
                desc_str,
                r.get('AliquotaIVA', ''),
                r.get('SpeseAccessorie', ''),
                "", 
                r.get('ImponibileImporto', ''),
                r.get('Imposta', '')
            ]
            for c_idx, v in enumerate(vals):
                cell = ctk.CTkFrame(riep_table, fg_color="transparent", border_width=1, border_color=("black", "gray60"), corner_radius=0)
                cell.grid(row=r_idx+1, column=c_idx, sticky="nsew")
                anchor = "w" if c_idx == 0 else "e"
                ctk.CTkLabel(cell, text=v, font=ctk.CTkFont(size=12)).pack(pady=2, padx=5, anchor=anchor)
                
        tot_headers = [t['bollo'], t['sconto_magg'], t['arr'], t['tot_doc']]
        tot_weights = [3, 2, 1, 4]
        
        tot_table = create_border_frame(paper)
        tot_table.grid(row=6, column=0, sticky="ew", padx=pad_x, pady=(0, 0))
        
        for i, h in enumerate(tot_headers):
            tot_table.grid_columnconfigure(i, weight=tot_weights[i])
            cell = ctk.CTkFrame(tot_table, fg_color=("gray90", "gray25"), border_width=1, border_color=("black", "gray60"), corner_radius=0)
            cell.grid(row=0, column=i, sticky="nsew")
            ctk.CTkLabel(cell, text=h, font=ctk.CTkFont(size=12, weight="bold")).pack(pady=2, padx=5)
            
            cell_v = ctk.CTkFrame(tot_table, fg_color="transparent", border_width=1, border_color=("black", "gray60"), corner_radius=0)
            cell_v.grid(row=1, column=i, sticky="nsew")
            val = gen.get('ImportoTotaleDocumento', '') if i == 3 else ""
            anchor = "e" if i == 3 else "center"
            ctk.CTkLabel(cell_v, text=val, font=ctk.CTkFont(size=12)).pack(pady=2, padx=5, anchor=anchor)

        def format_currency(val_str):
            if not val_str: return ""
            try:
                v = float(val_str)
                parts = f"{v:,.2f}".split('.')
                return f"{parts[0].replace(',', '.')},{parts[1]}"
            except Exception as e:
                print(f'Fehler: {e}')
                return val_str
                
        mp_map = {
            'MP01': 'MP01 Contanti', 'MP02': 'MP02 Assegno', 'MP05': 'MP05 Bonifico',
            'MP12': 'MP12 Ri.BA.', 'MP21': 'MP21 SEPA Direct Debit B2B',
            'MP22': 'MP22 Trattenuta su somme già riscosse', 'MP23': 'MP23 PagoPA'
        }

        pag_items = inv.get('pagamenti', [])
        if pag_items:
            pag_table = create_border_frame(paper)
            pag_table.grid(row=7, column=0, sticky="ew", padx=pad_x, pady=(15, 30))
            p_headers = [t['mod_pag'], t['dettagli'], t['scadenze'], t['importo']]
            p_weights = [2, 3, 2, 1]
            
            for i, h in enumerate(p_headers):
                pag_table.grid_columnconfigure(i, weight=p_weights[i])
                cell = ctk.CTkFrame(pag_table, fg_color=("gray90", "gray25"), border_width=1, border_color=("black", "gray60"), corner_radius=0)
                cell.grid(row=0, column=i, sticky="nsew")
                ctk.CTkLabel(cell, text=h, font=ctk.CTkFont(size=12, weight="bold")).pack(pady=2, padx=5)
                
            for p_idx, p in enumerate(pag_items):
                mp_code = p.get('ModalitaPagamento', '')
                mp_text = mp_map.get(mp_code, mp_code)
                
                dettagli_parts = []
                if p.get('IBAN'): dettagli_parts.append(f"IBAN {p['IBAN']}")
                abi_cab = []
                if p.get('ABI'): abi_cab.append(f"ABI {p['ABI']}")
                if p.get('CAB'): abi_cab.append(f"CAB {p['CAB']}")
                if abi_cab: dettagli_parts.append(" ".join(abi_cab))
                if p.get('IstitutoFinanziario'): dettagli_parts.append(p['IstitutoFinanziario'])
                if p.get('CodicePagamento'): dettagli_parts.append(f"Codice pagamento {p['CodicePagamento']}")
                dettagli = "\n".join(dettagli_parts)
                
                scad_parts = []
                if p.get('DataTerminePagamento'):
                    gg = p.get('GiorniTerminiPagamento', '')
                    gg_str = f" {gg}gg" if gg else ""
                    scad_parts.append(f"Data termine {p['DataTerminePagamento']}{gg_str}")
                if p.get('DataScadenzaPagamento'):
                    scad_parts.append(f"Data scadenza {p['DataScadenzaPagamento']}")
                scad = "\n".join(scad_parts)
                
                importo = format_currency(p.get('ImportoPagamento', ''))
                
                vals = [mp_text, dettagli, scad, importo]
                for c_idx, v in enumerate(vals):
                    cell = ctk.CTkFrame(pag_table, fg_color="transparent", border_width=1, border_color=("black", "gray60"), corner_radius=0)
                    cell.grid(row=p_idx+1, column=c_idx, sticky="nsew")
                    anchor = "w" if c_idx < 3 else "e"
                    ctk.CTkLabel(cell, text=v, font=ctk.CTkFont(size=12)).pack(pady=2, padx=5, anchor=anchor)
        else:
            ctk.CTkFrame(paper, fg_color="transparent", height=30).grid(row=7, column=0)

    def render_ministeriale(self, paper, inv):
        t = TRANSLATIONS_PREVIEW[self.lang]
        pad_x = 20
        
        lbl_filename = ctk.CTkLabel(paper, text=inv.get('filename', ''), font=ctk.CTkFont(size=14, weight="bold"))
        lbl_filename.grid(row=0, column=0, pady=(15, 15), sticky="w", padx=pad_x)
        
        row_idx = 1
        def add_header(title):
            nonlocal row_idx
            f = ctk.CTkFrame(paper, fg_color=("gray85", "gray30"), corner_radius=0)
            f.grid(row=row_idx, column=0, sticky="ew", padx=pad_x, pady=(15, 5))
            ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=5)
            row_idx += 1
            
        def add_kv(key, value):
            nonlocal row_idx
            if not value: return
            f = ctk.CTkFrame(paper, fg_color="transparent")
            f.grid(row=row_idx, column=0, sticky="ew", padx=pad_x, pady=1)
            f.grid_columnconfigure(0, weight=1)
            f.grid_columnconfigure(1, weight=2)
            ctk.CTkLabel(f, text=key, font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w", padx=10)
            ctk.CTkLabel(f, text=str(value), font=ctk.CTkFont(size=12), justify="left", wraplength=400).grid(row=0, column=1, sticky="w", padx=10)
            row_idx += 1
            
        gen = inv.get('dati_generali', {})
        add_header(t['dati_gen_doc'])
        add_kv(t['tipo_doc'] + ':', gen.get('TipoDocumento'))
        add_kv(t['num_doc'] + ':', gen.get('Numero'))
        add_kv(t['data_doc'] + ':', gen.get('Data'))
        add_kv(t['tot_doc'] + ':', gen.get('ImportoTotaleDocumento'))
        add_kv(t['art73'] + ':', gen.get('Art73'))
        
        mit = inv.get('mittente', {})
        add_header(t['cedente_prest'])
        add_kv(t['denom'], mit.get('Denominazione'))
        add_kv(t['cod_fiscale'], mit.get('CodiceFiscale'))
        add_kv("Partita IVA:", mit.get('PartitaIVA'))
        add_kv(t['ind'], mit.get('Indirizzo'))
        add_kv(t['comune'], mit.get('Comune'))
        add_kv(t['prov'], mit.get('Provincia'))
        add_kv("CAP:", mit.get('CAP'))
        add_kv(t['naz'], mit.get('Nazione'))
        add_kv(t['rif_amm'], mit.get('RiferimentoAmministrazione'))
        
        dest = inv.get('destinatario', {})
        add_header(t['cessionario_comm'])
        add_kv(t['denom'], dest.get('Denominazione'))
        add_kv(t['cod_fiscale'], dest.get('CodiceFiscale'))
        add_kv("Partita IVA:", dest.get('PartitaIVA'))
        add_kv(t['ind'], dest.get('Indirizzo'))
        add_kv(t['comune'], dest.get('Comune'))
        add_kv(t['prov'], dest.get('Provincia'))
        add_kv("CAP:", dest.get('CAP'))
        add_kv(t['naz'], dest.get('Nazione'))
        add_kv(t['pec_dest'], dest.get('PECDestinatario'))
        add_kv(t['cod_dest2'], dest.get('CodiceDestinatario'))
        
        linee = inv.get('linee', [])
        add_header(f"{t['dettaglio_linee']} ({len(linee)})")
        for l in linee:
            f = ctk.CTkFrame(paper, fg_color=("gray95", "gray20"), corner_radius=0, border_width=1, border_color=("gray80", "gray40"))
            f.grid(row=row_idx, column=0, sticky="ew", padx=pad_x, pady=5)
            row_idx += 1
            
            f.grid_columnconfigure(1, weight=1)
            
            def add_line_kv(parent, r, k, v):
                if not v: return r
                ctk.CTkLabel(parent, text=k, font=ctk.CTkFont(size=12, weight="bold")).grid(row=r, column=0, sticky="w", padx=10, pady=1)
                ctk.CTkLabel(parent, text=str(v), font=ctk.CTkFont(size=12), justify="left", wraplength=400).grid(row=r, column=1, sticky="w", padx=10, pady=1)
                return r + 1
                
            lr = 0
            lr = add_line_kv(f, lr, t['num_linea'], l.get('NumeroLinea'))
            lr = add_line_kv(f, lr, t['codice_art'], l.get('CodiceArticolo'))
            lr = add_line_kv(f, lr, "Descrizione:", l.get('Descrizione'))
            lr = add_line_kv(f, lr, "Quantità:", l.get('Quantita'))
            lr = add_line_kv(f, lr, t['unita_mis'], l.get('UnitaMisura'))
            lr = add_line_kv(f, lr, "Prezzo unitario:", l.get('PrezzoUnitario'))
            lr = add_line_kv(f, lr, "Sconto/Maggiorazione:", l.get('ScontoMaggiorazione'))
            lr = add_line_kv(f, lr, "Prezzo totale:", l.get('PrezzoTotale'))
            lr = add_line_kv(f, lr, t['aliquota_iva'], l.get('AliquotaIVA'))
            
            adg_list = l.get('AltriDatiGestionali', [])
            if adg_list:
                for adg in adg_list:
                    parts = []
                    if adg.get('TipoDato'): parts.append(adg['TipoDato'])
                    if adg.get('RiferimentoTesto'): parts.append(adg['RiferimentoTesto'])
                    if adg.get('RiferimentoNumero'): parts.append(adg['RiferimentoNumero'])
                    if adg.get('RiferimentoData'): parts.append(adg['RiferimentoData'])
                    if parts:
                        lr = add_line_kv(f, lr, t['altri_dati'], " - ".join(parts))
                        
        riep = inv.get('riepilogo', [])
        if riep:
            add_header(t['dati_riep'])
            for r in riep:
                f = ctk.CTkFrame(paper, fg_color=("gray95", "gray20"), corner_radius=0, border_width=1, border_color=("gray80", "gray40"))
                f.grid(row=row_idx, column=0, sticky="ew", padx=pad_x, pady=5)
                row_idx += 1
                f.grid_columnconfigure(1, weight=1)
                
                lr = 0
                lr = add_line_kv(f, lr, t['aliquota_iva'], r.get('AliquotaIVA'))
                lr = add_line_kv(f, lr, "Natura:", r.get('Natura'))
                lr = add_line_kv(f, lr, "Spese accessorie:", r.get('SpeseAccessorie'))
                lr = add_line_kv(f, lr, "Imponibile importo:", r.get('ImponibileImporto'))
                lr = add_line_kv(f, lr, "Imposta:", r.get('Imposta'))
                lr = add_line_kv(f, lr, "Esigibilità IVA:", r.get('EsigibilitaIVA'))
                lr = add_line_kv(f, lr, "Riferimento normativo:", r.get('RiferimentoNormativo'))
                
        pag = inv.get('pagamenti', [])
        if pag:
            add_header(t['dati_pag'])
            for p in pag:
                f = ctk.CTkFrame(paper, fg_color=("gray95", "gray20"), corner_radius=0, border_width=1, border_color=("gray80", "gray40"))
                f.grid(row=row_idx, column=0, sticky="ew", padx=pad_x, pady=5)
                row_idx += 1
                f.grid_columnconfigure(1, weight=1)
                
                lr = 0
                lr = add_line_kv(f, lr, "Modalità pagamento:", p.get('ModalitaPagamento'))
                lr = add_line_kv(f, lr, t['data_scad_pag'], p.get('DataScadenzaPagamento'))
                lr = add_line_kv(f, lr, t['importo_pag'], p.get('ImportoPagamento'))
                lr = add_line_kv(f, lr, t['iban'] + ':', p.get('IBAN'))
                
        ctk.CTkFrame(paper, fg_color="transparent", height=30).grid(row=row_idx, column=0)
            
    def export_pdf(self):
        if not self.current_invoice: return
        filename = f"Rechnung_{self.current_invoice.get('dati_generali', {}).get('Numero', 'X')}.pdf".replace("/", "_")
        filepath = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=filename, title="PDF speichern unter")
        if filepath:
            try:
                generate_invoice_pdf(self.current_invoice, filepath)
                print(f"PDF erfolgreich gespeichert: {filepath}")
            except Exception as e:
                print(f"Fehler beim PDF Export: {e}")
                
    def open_attachments(self):
        if not self.current_invoice or not self.current_invoice.get('allegati'): return
        
        import tempfile
        folder = tempfile.gettempdir()
        
        for a in self.current_invoice['allegati']:
            name = a.get('NomeAttachment', 'Anhang.bin')
            b64 = a.get('Attachment', '')
            if b64:
                try:
                    data = base64.b64decode(b64)
                    path = os.path.join(folder, name)
                    with open(path, 'wb') as f:
                        f.write(data)
                    os.startfile(path)
                except Exception as e:
                    print(f"Fehler beim Öffnen von Anhang {name}: {e}")

    def open_current_folder(self):
        if not self.current_invoice: return
        folder = os.path.dirname(self.current_invoice['filepath'])
        if os.path.exists(folder):
            try:
                os.startfile(folder)
            except Exception as e:
                print(f"Fehler beim Öffnen des Ordners: {e}")

    def print_invoice(self):
        if not self.current_invoice: return
        import tempfile
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".pdf", prefix="Druck_Rechnung_")
            os.close(fd)
            generate_invoice_pdf(self.current_invoice, temp_path)
            os.startfile(temp_path)
        except Exception as e:
            print(f"Fehler beim Drucken: {e}")

    def show_signature(self):
        if not self.current_invoice: return
        sig = self.current_invoice.get('signature_info')
        if not sig: return
        
        popup = ctk.CTkToplevel(self)
        popup.title("Digitale Unterschrift (Firma)")
        popup.geometry("450x550")
        popup.attributes('-topmost', 'true')
        
        frame = ctk.CTkScrollableFrame(popup, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        hdr = ctk.CTkFrame(frame, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(hdr, text="▼ FIRMA", font=ctk.CTkFont(size=18, weight="bold"), text_color="#3a7ebf").pack(anchor="w")
        
        status = sig.get('Stato della firma', 'Firma valida')
        status_color = "green" if "valida" in status.lower() else "red"
        
        row1 = ctk.CTkFrame(frame, fg_color="transparent")
        row1.pack(fill="x", pady=2)
        ctk.CTkLabel(row1, text="Stato della firma: ").pack(side="left")
        ctk.CTkLabel(row1, text=status, text_color=status_color, font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        ctk.CTkLabel(frame, text=f"Data di firma: {sig.get('Data di firma', '')}", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10, 20))
        
        ctk.CTkLabel(frame, text="Soggetto", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        for item in sig.get('Soggetto', []):
            ctk.CTkLabel(frame, text=f"• {item}", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=2)
            
        ctk.CTkFrame(frame, height=1, fg_color="gray80").pack(fill="x", pady=15)
            
        ctk.CTkLabel(frame, text="Certificato emesso da:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        for item in sig.get('Certificato emesso da', []):
            ctk.CTkLabel(frame, text=f"• {item}", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=2)
