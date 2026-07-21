import os
import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import Font
import pandas as pd

def ensure_rule_file(file_path):
    """Erstellt die Excel-Datei mit Kontenregeln und Data Validation, falls sie nicht existiert."""
    if os.path.exists(file_path):
        return

    wb = openpyxl.Workbook()
    
    # 1. Kontenplan
    ws_konten = wb.active
    ws_konten.title = "Kontenplan"
    headers = ["Konto-Nummer", "Bezeichnung", "Klasse"]
    ws_konten.append(headers)
    
    # Ein paar Beispiel-Konten hinzufügen
    default_accounts = [
        ("0100000", "Anlagevermögen", "0"),
        ("4000000", "Umsatzerlöse", "4"),
        ("5000000", "Materialaufwand / Wareneinkauf", "5"),
        ("7000000", "Dienstleistungen", "7"),
        ("7010000", "Telefon und Internet", "7"),
        ("7020000", "Strom", "7"),
    ]
    for acc in default_accounts:
        ws_konten.append(acc)
        
    for cell in ws_konten[1]:
        cell.font = Font(bold=True)
        
    # 2. Lieferanten-Regeln
    ws_lief = wb.create_sheet("Lieferanten-Regeln")
    ws_lief.append(["Lieferant (Name oder MwSt-Nr)", "Konto"])
    
    # 3. Stichwort-Regeln
    ws_stich = wb.create_sheet("Stichwort-Regeln")
    ws_stich.append(["Stichwort in Beschreibung", "Konto"])
    
    # --- Data Validation für Konto-Spalten ---
    # Die Validierung zwingt den Nutzer, nur Einträge aus 'Kontenplan' zu nehmen
    dv_formula = "'Kontenplan'!$A$2:$A$1000"
    
    dv_lief = DataValidation(type="list", formula1=dv_formula, allow_blank=True)
    dv_lief.error = 'Das eingegebene Konto existiert nicht im Kontenplan!'
    dv_lief.errorTitle = 'Ungültiges Konto'
    dv_lief.prompt = 'Bitte ein Konto aus der Dropdown-Liste wählen'
    dv_lief.promptTitle = 'Konto auswählen'
    
    ws_lief.add_data_validation(dv_lief)
    dv_lief.add("B2:B1000")
    
    dv_stich = DataValidation(type="list", formula1=dv_formula, allow_blank=True)
    dv_stich.error = 'Das eingegebene Konto existiert nicht im Kontenplan!'
    dv_stich.errorTitle = 'Ungültiges Konto'
    dv_stich.prompt = 'Bitte ein Konto aus der Dropdown-Liste wählen'
    dv_stich.promptTitle = 'Konto auswählen'
    
    ws_stich.add_data_validation(dv_stich)
    dv_stich.add("B2:B1000")
    
    for cell in ws_lief[1]: cell.font = Font(bold=True)
    for cell in ws_stich[1]: cell.font = Font(bold=True)
    
    # Spaltenbreiten etwas anpassen
    ws_lief.column_dimensions['A'].width = 30
    ws_lief.column_dimensions['B'].width = 15
    ws_stich.column_dimensions['A'].width = 30
    ws_stich.column_dimensions['B'].width = 15
    ws_konten.column_dimensions['A'].width = 15
    ws_konten.column_dimensions['B'].width = 30
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    wb.save(file_path)

def load_rules(global_path, client_path):
    """
    Lädt die Regeln aus beiden Dateien und gibt ein Regel-Dictionary zurück.
    Priorität:
    1. Kunde Stichwort
    2. Global Stichwort
    3. Global Lieferant
    """
    rules = {
        "client_stichwort": {},
        "global_stichwort": {},
        "global_lieferant": {}
    }
    
    # Globale Regeln laden
    if os.path.exists(global_path):
        try:
            df_g_lief = pd.read_excel(global_path, sheet_name="Lieferanten-Regeln")
            df_g_stich = pd.read_excel(global_path, sheet_name="Stichwort-Regeln")
            
            for _, row in df_g_lief.iterrows():
                lief = str(row.iloc[0]).strip().lower()
                konto = str(row.iloc[1]).strip()
                if lief and lief != 'nan' and konto and konto != 'nan':
                    rules["global_lieferant"][lief] = konto
                    
            for _, row in df_g_stich.iterrows():
                stich = str(row.iloc[0]).strip().lower()
                konto = str(row.iloc[1]).strip()
                if stich and stich != 'nan' and konto and konto != 'nan':
                    rules["global_stichwort"][stich] = konto
        except Exception as e:
            print(f"Fehler beim Laden globaler Regeln: {e}")
            
    # Kunden-Regeln laden
    if os.path.exists(client_path):
        try:
            df_c_stich = pd.read_excel(client_path, sheet_name="Stichwort-Regeln")
            
            for _, row in df_c_stich.iterrows():
                stich = str(row.iloc[0]).strip().lower()
                konto = str(row.iloc[1]).strip()
                if stich and stich != 'nan' and konto and konto != 'nan':
                    rules["client_stichwort"][stich] = konto
        except Exception as e:
            print(f"Fehler beim Laden kunden-spezifischer Regeln: {e}")
            
    return rules

def assign_account(desc, supplier_name, supplier_vat, rules):
    """Weist das Konto basierend auf der 3-stufigen Priorität zu."""
    desc = str(desc).lower()
    supplier_name = str(supplier_name).lower()
    supplier_vat = str(supplier_vat).lower()
    
    # 1. Priorität: Kunde Stichwort
    for stich, konto in rules["client_stichwort"].items():
        if stich in desc:
            return str(konto)
            
    # 2. Priorität: Global Stichwort
    for stich, konto in rules["global_stichwort"].items():
        if stich in desc:
            return str(konto)
            
    # 3. Priorität: Global Lieferant (Suche nach Name oder VAT)
    for lief, konto in rules["global_lieferant"].items():
        if lief in supplier_name or lief in supplier_vat:
            return str(konto)
            
    return "???"
