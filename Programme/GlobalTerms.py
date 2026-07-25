import os
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font

def get_global_terms_path(base_dir):
    # base_dir is usually the project root folder. Let's place it in Systemdaten.
    return os.path.join(base_dir, "Systemdaten", "Globale_Begriffe.xlsx")

def ensure_global_terms_file(base_dir):
    """Prüft, ob die Globale_Begriffe.xlsx existiert, und erstellt sie bei Bedarf."""
    setup_path = get_global_terms_path(base_dir)
    os.makedirs(os.path.dirname(setup_path), exist_ok=True)
    
    if not os.path.exists(setup_path):
        wb = Workbook()
        ws = wb.active
        ws.title = "Globale Begriffe"
        
        # Header
        ws.append(["Suchbegriff (Wird priorisiert)"])
        for cell in ws[1]:
            cell.font = Font(bold=True)
            
        # Spaltenbreiten
        ws.column_dimensions['A'].width = 50
        
        # Beispiele eintragen
        ws.append(["Gewürzmischung"])
        ws.append(["Schraube"])
        ws.append(["Kabel"])
        
        wb.save(setup_path)
        print("Neue Globale_Begriffe.xlsx Vorlage in Systemdaten erstellt.")
        return True
    return False

def load_global_terms(base_dir):
    """Lädt die Globale Begriffe-Excel und gibt eine sortierte Liste zurück (längste Begriffe zuerst)."""
    setup_path = get_global_terms_path(base_dir)
    if not os.path.exists(setup_path):
        return []
        
    try:
        df = pd.read_excel(setup_path)
        begriffe = set()
        for _, row in df.iterrows():
            begriff = str(row.iloc[0]).strip()
            if begriff and begriff.lower() != 'nan':
                begriffe.add(begriff.upper())
        # Sortiere absteigend nach Länge, damit "Spezialschraube" vor "Schraube" gefunden wird!
        return sorted(list(begriffe), key=len, reverse=True)
    except Exception as e:
        print(f"Fehler beim Laden von Globale_Begriffe.xlsx: {e}")
        return []

def apply_global_terms(desc, global_terms):
    """Prüft, ob ein Begriff aus der globalen Liste im Text ist. Wenn ja, wird dieser Begriff zurückgegeben."""
    if not desc or not global_terms:
        return desc
    desc_upper = desc.upper()
    for term in global_terms:
        if term in desc_upper:
            # Wenn der Begriff gefunden wird, ersetze die ganze Beschreibung durch diesen Begriff!
            return term
    return desc
