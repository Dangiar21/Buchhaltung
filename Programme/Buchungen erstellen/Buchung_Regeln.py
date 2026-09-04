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
    """Erstellt oder aktualisiert die Excel-Datei mit Kontenregeln (stellt Lieferanten- und Stichwort-Reiter sicher und entfernt alte Kontenplan-Reiter)."""
    modified = False
    
    if os.path.exists(file_path):
        wb = openpyxl.load_workbook(file_path)
    else:
        wb = openpyxl.Workbook()
        if 'Sheet' in wb.sheetnames:
            del wb['Sheet']
        modified = True
        
    # Veraltete Kontenplan-Reiter entfernen (da Kontenpläne nun über .txt verwaltet werden)
    for old_sheet in ["Kontenplan", "Sheet1"]:
        if old_sheet in wb.sheetnames and len(wb.sheetnames) > 1:
            del wb[old_sheet]
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

    # Alte DataValidations entfernen, die auf den gelöschten Kontenplan verwiesen haben
    for sheet_name in ["Lieferanten-Regeln", "Stichwort-Regeln"]:
        if sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            valid_dvs = []
            for dv in ws.data_validations.dataValidation:
                if dv.formula1 and "Kontenplan" in str(dv.formula1):
                    modified = True
                else:
                    valid_dvs.append(dv)
            ws.data_validations.dataValidation = valid_dvs



    if modified:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        try:
            wb.save(file_path)
        except (PermissionError, OSError) as e:
            print(f"Warnung: Konnte {file_path} nicht aktualisieren (evtl. in Excel geöffnet): {e}")

def load_rules(global_path, client_path):
    """
    Lädt die Regeln über den DatabaseManager (CQRS). Excel dient als Frontend.
    """
    rules = {
        "client_lieferant": {},
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
                    konto = konto_raw.split(' - ')[0].strip() if konto_raw != 'nan' else ''
                    if konto.endswith('.0'): konto = konto[:-2]
                    if lief and lief != 'nan' and konto:
                        rules_list.append({"prioritaet": 3, "lieferant": lief, "konto": konto, "regel_typ": "global_lieferant"})
                        
                for _, row in df_g_stich.iterrows():
                    stich = str(row.iloc[0]).strip().lower()
                    konto_raw = str(row.iloc[1]).strip()
                    konto = konto_raw.split(' - ')[0].strip() if konto_raw != 'nan' else ''
                    if konto.endswith('.0'): konto = konto[:-2]
                    if stich and stich != 'nan' and konto:
                        rules_list.append({"prioritaet": 2, "suchbegriff": stich, "konto": konto, "regel_typ": "global_stichwort"})
                        

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
        
        # Prüfe ob Resync nötig (Zeitstempel geändert oder Lieferanten-Regeln noch nie synchronisiert)
        needs_sync = client_mtime > last_sync
        if not needs_sync:
            try:
                df_check = db.get_rules(client_id, "client_rules")
                if df_check.empty or "client_lieferant" not in df_check["regel_typ"].values:
                    needs_sync = True
            except Exception:
                needs_sync = True
        
        if needs_sync:
            print(f"Synchronisiere kunden-spezifische Regeln für {client_id} aus Excel in SQLite...")
            try:
                rules_list = []
                
                # 2.1 Kunden Lieferanten-Regeln
                try:
                    df_c_lief = pd.read_excel(client_path, sheet_name="Lieferanten-Regeln")
                    for _, row in df_c_lief.iterrows():
                        lief = str(row.iloc[0]).strip().lower()
                        konto_raw = str(row.iloc[1]).strip()
                        konto = konto_raw.split(' - ')[0].strip() if konto_raw != 'nan' else ''
                        if konto.endswith('.0'): konto = konto[:-2]
                        if lief and lief != 'nan' and konto:
                            rules_list.append({"prioritaet": 0, "lieferant": lief, "konto": konto, "regel_typ": "client_lieferant"})
                except Exception as e:
                    pass

                # 2.2 Kunden Stichwort-Regeln
                try:
                    df_c_stich = pd.read_excel(client_path, sheet_name="Stichwort-Regeln")
                    for _, row in df_c_stich.iterrows():
                        stich = str(row.iloc[0]).strip().lower()
                        konto_raw = str(row.iloc[1]).strip()
                        konto = konto_raw.split(' - ')[0].strip() if konto_raw != 'nan' else ''
                        if konto.endswith('.0'): konto = konto[:-2]
                        if stich and stich != 'nan' and konto:
                            rules_list.append({"prioritaet": 1, "suchbegriff": stich, "konto": konto, "regel_typ": "client_stichwort"})
                except Exception as e:
                    pass
                        
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
                    
        # Load Client
        if client_id:
            df_client = db.get_rules(client_id, "client_rules")
            if not df_client.empty:
                for _, row in df_client.iterrows():
                    typ = row['regel_typ']
                    if typ == "client_lieferant":
                        rules["client_lieferant"][row['lieferant']] = row['konto']
                    elif typ == "client_stichwort":
                        rules["client_stichwort"][row['suchbegriff']] = row['konto']
                        
    except Exception as e:
        print(f"Fehler beim Laden der Regeln aus SQLite: {e}")

    return rules

def assign_account(desc_norm, desc, supplier_name, supplier_vat, kunden_id, rules):
    """Weist das Konto basierend auf der Priorität zu. Gibt (Konto, is_pending) zurück."""
    desc = str(desc).lower()
    supplier_name = str(supplier_name).lower()
    norm_supplier_vat = normalize_id(supplier_vat)
    raw_supplier_vat = str(supplier_vat).strip().lower() if supplier_vat else ""
    
    # 1. Höchste Priorität: Kunden-Lieferanten-Regel
    for lief, konto in rules.get("client_lieferant", {}).items():
        norm_lief = normalize_id(lief)
        if (lief in supplier_name) or (raw_supplier_vat and lief in raw_supplier_vat) or (norm_lief and norm_lief == norm_supplier_vat):
            return str(konto), False

    # 2. Priorität: Kunden-Stichwort-Regel
    for stich, konto in rules.get("client_stichwort", {}).items():
        if stich in desc:
            return str(konto), False
            
    # 3. Priorität: Globale Stichwort-Regel
    for stich, konto in rules.get("global_stichwort", {}).items():
        if stich in desc:
            return str(konto), False
            
    # 4. Priorität: Globale Lieferanten-Regel (Suche nach Name oder VAT)
    for lief, konto in rules.get("global_lieferant", {}).items():
        norm_lief = normalize_id(lief)
        if (lief in supplier_name) or (raw_supplier_vat and lief in raw_supplier_vat) or (norm_lief and norm_lief == norm_supplier_vat):
            return str(konto), False
            
    return "???", False
