import os
import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import Font, PatternFill
from openpyxl.formatting.rule import CellIsRule
import pandas as pd
import sys
script_dir = os.path.dirname(os.path.abspath(__file__))
prog_dir = os.path.dirname(script_dir)
if prog_dir not in sys.path:
    sys.path.append(prog_dir)

def normalize_id(val):
    """Bulletproof ID normalizer: handles NaN, float casts (.0), casing, and leading zeros."""
    if pd.isna(val): return ""
    s = str(val).strip().lower()
    if s in ('nan', ''): return ""
    if s.endswith('.0'): s = s[:-2]
    stripped = s.lstrip('0')
    return '0' if not stripped else stripped

def ensure_rule_file(file_path):
    """Erstellt oder aktualisiert die Excel-Datei mit Kontenregeln (Fügt fehlende Reiter und Dropdowns hinzu)."""
    modified = False
    
    if os.path.exists(file_path):
        wb = openpyxl.load_workbook(file_path)
    else:
        wb = openpyxl.Workbook()
        if 'Sheet' in wb.sheetnames:
            del wb['Sheet']
        modified = True
        
    if "Kontenplan" not in wb.sheetnames:
        ws_konten = wb.create_sheet("Kontenplan")
        ws_konten.append(["Konto-Nummer", "Bezeichnung", "Dropdown (Wird automatisch erstellt)"])
        default_accounts = [
            ("0100", "Anlagevermögen"),
            ("4000", "Umsatzerlöse"),
            ("5000", "Materialaufwand / Wareneinkauf"),
            ("7000", "Dienstleistungen"),
            ("7010", "Telefon und Internet"),
            ("7020", "Strom"),
        ]
        for idx, acc in enumerate(default_accounts, start=2):
            ws_konten.append([acc[0], acc[1], f'=IF(A{idx}<>"", A{idx} & " - " & B{idx}, "")'])
            
        # Formeln für den Rest der Spalte C auffüllen
        for i in range(len(default_accounts) + 2, 1001):
            ws_konten[f'C{i}'] = f'=IF(A{i}<>"", A{i} & " - " & B{i}, "")'
            
        for cell in ws_konten[1]: cell.font = Font(bold=True)
        ws_konten.column_dimensions['A'].width = 15
        ws_konten.column_dimensions['B'].width = 30
        ws_konten.column_dimensions['C'].width = 40
    else:
        ws_konten = wb["Kontenplan"]
        if ws_konten['C1'].value != "Dropdown (Wird automatisch erstellt)":
            ws_konten['C1'] = "Dropdown (Wird automatisch erstellt)"
            for i in range(2, 1001):
                ws_konten[f'C{i}'] = f'=IF(A{i}<>"", A{i} & " - " & B{i}, "")'
            ws_konten.column_dimensions['C'].width = 40
            modified = True

    if "Lieferanten-Regeln" not in wb.sheetnames:
        ws_lief = wb.create_sheet("Lieferanten-Regeln")
        ws_lief.append(["Lieferant (Name oder MwSt-Nr)", "Konto"])
        for cell in ws_lief[1]: cell.font = Font(bold=True)
        ws_lief.column_dimensions['A'].width = 30
        ws_lief.column_dimensions['B'].width = 15
        modified = True

    if "Stichwort-Regeln" not in wb.sheetnames:
        ws_stich = wb.create_sheet("Stichwort-Regeln")
        ws_stich.append(["Stichwort in Beschreibung", "Konto"])
        for cell in ws_stich[1]: cell.font = Font(bold=True)
        ws_stich.column_dimensions['A'].width = 30
        ws_stich.column_dimensions['B'].width = 15
        modified = True

    if "KI-Zuweisungen" not in wb.sheetnames:
        ws_ki = wb.create_sheet("KI-Zuweisungen")
        ws_ki.append(["Lieferant ID", "Lieferant Name", "Kunden ID", "Kunden Name", "Beschreibung", "Konto", "Status"])
        for cell in ws_ki[1]: cell.font = Font(bold=True)
        ws_ki.column_dimensions['A'].width = 15
        ws_ki.column_dimensions['B'].width = 25
        ws_ki.column_dimensions['C'].width = 15
        ws_ki.column_dimensions['D'].width = 25
        ws_ki.column_dimensions['E'].width = 40
        ws_ki.column_dimensions['F'].width = 15
        ws_ki.column_dimensions['G'].width = 20
        modified = True

    # Check and add Data Validations
    dv_formula = "'Kontenplan'!$C$2:$C$1000"
    
    ws_lief = wb["Lieferanten-Regeln"]
    has_dv = any(dv.formula1 == dv_formula for dv in ws_lief.data_validations.dataValidation)
    if not has_dv:
        dv_lief = DataValidation(type="list", formula1=dv_formula, allow_blank=True)
        dv_lief.error = 'Das eingegebene Konto existiert nicht im Kontenplan!'
        dv_lief.errorTitle = 'Ungültiges Konto'
        dv_lief.prompt = 'Bitte ein Konto aus der Dropdown-Liste wählen'
        dv_lief.promptTitle = 'Konto auswählen'
        ws_lief.add_data_validation(dv_lief)
        dv_lief.add("B2:B1000")
        modified = True

    ws_stich = wb["Stichwort-Regeln"]
    has_dv_stich = any(dv.formula1 == dv_formula for dv in ws_stich.data_validations.dataValidation)
    if not has_dv_stich:
        dv_stich = DataValidation(type="list", formula1=dv_formula, allow_blank=True)
        dv_stich.error = 'Das eingegebene Konto existiert nicht im Kontenplan!'
        dv_stich.errorTitle = 'Ungültiges Konto'
        dv_stich.prompt = 'Bitte ein Konto aus der Dropdown-Liste wählen'
        dv_stich.promptTitle = 'Konto auswählen'
        ws_stich.add_data_validation(dv_stich)
        dv_stich.add("B2:B1000")
        modified = True

    ws_ki = wb["KI-Zuweisungen"]
    has_dv_status = any(dv.formula1 == '"AUSSTEHEND,BESTÄTIGT"' for dv in ws_ki.data_validations.dataValidation)
    if not has_dv_status:
        dv_status = DataValidation(type="list", formula1='"AUSSTEHEND,BESTÄTIGT"', allow_blank=True)
        dv_status.error = 'Bitte wähle einen gültigen Status!'
        dv_status.errorTitle = 'Ungültiger Status'
        ws_ki.add_data_validation(dv_status)
        dv_status.add("G2:G1000")
        
        red_fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
        green_fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
        ws_ki.conditional_formatting.add('G2:G1000', CellIsRule(operator='equal', formula=['"AUSSTEHEND"'], fill=red_fill))
        ws_ki.conditional_formatting.add('G2:G1000', CellIsRule(operator='equal', formula=['"BESTÄTIGT"'], fill=green_fill))
        
        for col in ['A', 'C']:
            for row_idx in range(2, 1001):
                ws_ki[f'{col}{row_idx}'].number_format = '@'
        for row_idx in range(2, 1001):
            ws_ki[f'F{row_idx}'].number_format = '0'
            
        modified = True

    if modified:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        wb.save(file_path)

def load_rules(global_path, client_path):
    """
    Lädt die Regeln über den DatabaseManager (CQRS). Excel dient als Frontend.
    """
    rules = {
        "ai_confirmed": {},
        "ai_pending": {},
        "client_stichwort": {},
        "global_stichwort": {},
        "global_lieferant": {}
    }
    
    try:
        from DatabaseManager import get_db
        db = get_db()
    except ImportError:
        print("Fehler: DatabaseManager nicht gefunden.")
        return rules

    # 1. Global Sync
    if os.path.exists(global_path):
        global_mtime = os.path.getmtime(global_path)
        last_sync = db.get_sync_status("GLOBAL", "global_rules")
        
        if global_mtime > last_sync:
            print("Synchronisiere globale Regeln aus Excel in die SQLite-Datenbank...")
            try:
                df_g_lief = pd.read_excel(global_path, sheet_name="Lieferanten-Regeln")
                df_g_stich = pd.read_excel(global_path, sheet_name="Stichwort-Regeln")
                
                rules_list = []
                for _, row in df_g_lief.iterrows():
                    lief = str(row.iloc[0]).strip().lower()
                    konto_raw = str(row.iloc[1]).strip()
                    konto = konto_raw.split(' ')[0] if konto_raw != 'nan' else ''
                    if lief and lief != 'nan' and konto:
                        rules_list.append({"prioritaet": 3, "lieferant": lief, "konto": konto, "regel_typ": "global_lieferant"})
                        
                for _, row in df_g_stich.iterrows():
                    stich = str(row.iloc[0]).strip().lower()
                    konto_raw = str(row.iloc[1]).strip()
                    konto = konto_raw.split(' ')[0] if konto_raw != 'nan' else ''
                    if stich and stich != 'nan' and konto:
                        rules_list.append({"prioritaet": 2, "suchbegriff": stich, "konto": konto, "regel_typ": "global_stichwort"})
                        
                if "KI-Zuweisungen" in pd.ExcelFile(global_path).sheet_names:
                    df_g_ki = pd.read_excel(global_path, sheet_name="KI-Zuweisungen")
                    for _, row in df_g_ki.iterrows():
                        lief_id = normalize_id(row.get("Lieferant ID", ""))
                        k_id = normalize_id(row.get("Kunden ID", ""))
                        desc_raw = row.get("Beschreibung", "")
                        desc = "" if (pd.isna(desc_raw) or str(desc_raw).strip().lower() == 'nan') else str(desc_raw).strip().upper()
                        konto_raw = row.get("Konto", "")
                        konto = "" if (pd.isna(konto_raw) or str(konto_raw).strip().lower() == 'nan') else str(konto_raw).strip().split(' ')[0]
                        status = str(row.get("Status", "")).strip().upper()
                        
                        if konto:
                            is_pending = not (status == "BESTÄTIGT" or status == "OK" or status == "X")
                            typ = "ai_pending" if is_pending else "ai_confirmed"
                            rules_list.append({
                                "prioritaet": 0, "regel_typ": typ, "lieferant_id": lief_id, "suchbegriff": desc, 
                                "konto": konto, "target_kunden_id": k_id, "status": status
                            })
                            
                df_sync = pd.DataFrame(rules_list)
                db.sync_rules("GLOBAL", "global_rules", df_sync)
                db.set_sync_status("GLOBAL", "global_rules", global_mtime)
            except Exception as e:
                print(f"Fehler beim Sync der globalen Regeln: {e}")

    # 2. Client Sync
    client_id = ""
    if client_path and os.path.exists(client_path):
        client_id = os.path.basename(os.path.dirname(client_path))
        if client_id == "Nutzerdaten":
             client_id = os.path.basename(os.path.dirname(os.path.dirname(client_path)))
             
        client_mtime = os.path.getmtime(client_path)
        last_sync = db.get_sync_status(client_id, "client_rules")
        
        if client_mtime > last_sync:
            print(f"Synchronisiere kunden-spezifische Regeln für {client_id} aus Excel in SQLite...")
            try:
                df_c_stich = pd.read_excel(client_path, sheet_name="Stichwort-Regeln")
                rules_list = []
                for _, row in df_c_stich.iterrows():
                    stich = str(row.iloc[0]).strip().lower()
                    konto_raw = str(row.iloc[1]).strip()
                    konto = konto_raw.split(' ')[0] if konto_raw != 'nan' else ''
                    if stich and stich != 'nan' and konto:
                        rules_list.append({"prioritaet": 1, "suchbegriff": stich, "konto": konto, "regel_typ": "client_stichwort"})
                        
                df_sync = pd.DataFrame(rules_list)
                db.sync_rules(client_id, "client_rules", df_sync)
                db.set_sync_status(client_id, "client_rules", client_mtime)
            except Exception as e:
                print(f"Fehler beim Sync der kunden-spezifischen Regeln: {e}")
                
    # 3. Load from SQLite into memory dict
    try:
        # Load Global
        df_global = db.get_rules("GLOBAL", "global_rules")
        if not df_global.empty:
            for _, row in df_global.iterrows():
                typ = row['regel_typ']
                if typ == "global_lieferant":
                    rules["global_lieferant"][row['lieferant']] = row['konto']
                elif typ == "global_stichwort":
                    rules["global_stichwort"][row['suchbegriff']] = row['konto']
                elif typ in ["ai_confirmed", "ai_pending"]:
                    key = (row.get('lieferant_id', ''), row.get('suchbegriff', ''), row.get('target_kunden_id', ''))
                    rules[typ][key] = row['konto']
                    
        # Load Client
        if client_id:
            df_client = db.get_rules(client_id, "client_rules")
            if not df_client.empty:
                for _, row in df_client.iterrows():
                    if row['regel_typ'] == "client_stichwort":
                        rules["client_stichwort"][row['suchbegriff']] = row['konto']
                        
    except Exception as e:
        print(f"Fehler beim Laden der Regeln aus SQLite: {e}")

    return rules

def assign_account(desc_norm, desc, supplier_name, supplier_vat, kunden_id, rules):
    """Weist das Konto basierend auf der 4-stufigen Priorität zu. Gibt (Konto, is_pending) zurück."""
    desc = str(desc).lower()
    supplier_name = str(supplier_name).lower()
    supplier_vat = normalize_id(supplier_vat)
    kunden_id = normalize_id(kunden_id)
    
    # 0. Priorität (Allerhöchste): Bestätigte KI-Regel (exakte Übereinstimmung)
    ai_key = (supplier_vat, desc_norm, kunden_id)
    if ai_key in rules["ai_confirmed"]:
        return str(rules["ai_confirmed"][ai_key]), False
        
    # 0.5 Priorität: Ausstehende KI-Regel
    if ai_key in rules["ai_pending"]:
        return str(rules["ai_pending"][ai_key]), True
    
    # 1. Priorität: Kunde Stichwort
    for stich, konto in rules["client_stichwort"].items():
        if stich in desc:
            return str(konto), False
            
    # 2. Priorität: Global Stichwort
    for stich, konto in rules["global_stichwort"].items():
        if stich in desc:
            return str(konto), False
            
    # 3. Priorität: Global Lieferant (Suche nach Name oder VAT)
    for lief, konto in rules["global_lieferant"].items():
        if lief in supplier_name or lief in supplier_vat:
            return str(konto), False
            
    return "???", False
