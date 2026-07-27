import os
import customtkinter as ctk

class ClientManager:
    def __init__(self, parent, controller, config_manager, on_client_selected):
        self.parent = parent
        self.controller = controller
        self.config_manager = config_manager
        self.on_client_selected = on_client_selected
        
        self.all_clients = []
        self.current_client = None

    def open_new_client_dialog(self, edit_client_name=None):
        is_edit = edit_client_name is not None
        dialog = ctk.CTkToplevel(self.parent)
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
                editor.transient(dialog)
                editor.grab_set()
                
                txt = ctk.CTkTextbox(editor, width=550, height=400)
                txt.pack(padx=20, pady=20)
                
                file_path = os.path.join(self.controller.base_kunden_dir, edit_client_name, "Nutzerdaten", f"{typ}_Kontenplan.txt")
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        txt.insert("1.0", f.read())
                        
                def save_txt():
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(txt.get("1.0", "end-1c"))
                    editor.destroy()
                    
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
                self.on_client_selected(final_name)
                dialog.destroy()
            else:
                error_label.configure(text=f"Fehler: {final_name}")

        btn_save = ctk.CTkButton(dialog, text="Speichern", command=save_client)
        btn_save.pack(pady=10)
