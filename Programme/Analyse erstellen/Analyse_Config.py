import os
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font

def get_setup_path(nutzerdaten_dir):
    return os.path.join(nutzerdaten_dir, "Analyse_Setup.xlsx")

def ensure_setup_file(nutzerdaten_dir):
    """Prüft, ob die Analyse_Setup.xlsx existiert, und erstellt sie bei Bedarf."""
    setup_path = get_setup_path(nutzerdaten_dir)
    
    if not os.path.exists(setup_path):
        os.makedirs(nutzerdaten_dir, exist_ok=True)
        wb = Workbook()
        ws = wb.active
        ws.title = "KI Kategorien"
        
        # Header
        ws.append(["Kategorie", "Regel für KI", "Beispiele (Optional)"])
        for cell in ws[1]:
            cell.font = Font(bold=True)
            
        # Spaltenbreiten
        ws.column_dimensions['A'].width = 20
        ws.column_dimensions['B'].width = 50
        ws.column_dimensions['C'].width = 40
        
        # Beispiel eintragen
        ws.append(["Maschinenteile", "Wähle aus: Motor, Karosserie, Elektronik, Sonstiges", "Zylinderkopf -> Motor, Scheinwerfer -> Elektronik"])
        ws.append(["Qualität", "Wähle aus: Originalteil, Nachbau, Unbekannt", ""])
        
        wb.save(setup_path)
        print(f"Neue Analyse_Setup.xlsx Vorlage in {nutzerdaten_dir} erstellt.")
        return True
    return False

def load_setup(nutzerdaten_dir):
    """Lädt die Setup-Excel und gibt eine Liste von Dicts zurück."""
    setup_path = get_setup_path(nutzerdaten_dir)
    if not os.path.exists(setup_path):
        return []
        
    try:
        df = pd.read_excel(setup_path)
        kategorien = []
        for _, row in df.iterrows():
            kategorie = str(row.iloc[0]).strip()
            regel = str(row.iloc[1]).strip()
            beispiele = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
            
            if kategorie and kategorie != 'nan':
                kategorien.append({
                    "name": kategorie,
                    "regel": regel if regel != 'nan' else "",
                    "beispiele": beispiele if beispiele != 'nan' else ""
                })
        return kategorien
    except Exception as e:
        print(f"Fehler beim Laden von Analyse_Setup.xlsx: {e}")
        return []

def build_system_instruction(kategorien, is_stage2=False):
    """Baut den KI-Prompt basierend auf den geladenen Kategorien."""
    if not kategorien:
        return "Du bist ein Buchhaltungs-Assistent. Keine Kategorien definiert."
        
    prompt = "Du bist ein intelligenter Datenanalyst für Sektorenstudien. Deine Aufgabe ist es, Rechnungspositionen zu kategorisieren.\n"
    prompt += "WICHTIG: Erfinde KEINE eigenen Kategorien. Nutze 'Sonstiges' oder 'Unbekannt', wenn etwas nicht zuordnenbar ist.\n\n"
    prompt += "Hier sind die Kategorien und Regeln:\n\n"
    
    kategorien_dict = {}
    for kat in kategorien:
        prompt += f"--- {kat['name']} ---\n"
        if kat['regel']:
            prompt += f"Regel: {kat['regel']}\n"
        if kat['beispiele']:
            prompt += f"Beispiele: {kat['beispiele']}\n"
        prompt += "\n"
        kategorien_dict[kat['name']] = "Dein_Ergebnis_Hier"
        
    prompt += "Du erhältst eine Liste von Artikeln im Format: [ID] Lieferant | Beschreibung\n"
    prompt += "Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt. Die Schlüssel auf der obersten Ebene sind die IDs (als String).\n"
    
    import json
    if not is_stage2:
        prompt += "Der Wert für jede ID MUSS ein JSON-Objekt mit exakt diesen 3 Schlüsseln sein: 'gedankengang', 'konfidenz', 'konto' (bzw. kategorien_werte).\n"
        prompt += "'gedankengang' ist ein Satz, 'konfidenz' ist eine Zahl 1-10.\n"
        prompt += "'konto' (wir nennen es intern kategorien_werte) ist ein JSON-Objekt mit den Kategorien als Schlüssel.\n"
        
        beispiel_antwort = {
            "0": {
                "gedankengang": "Erklaerung hier",
                "konfidenz": 9,
                "konto": kategorien_dict
            }
        }
    else:
        prompt += "Der Wert für jede ID ist direkt ein Objekt mit den Kategorien als Schlüssel.\n"
        prompt += "Du MUSST dich zwingend für jede Kategorie entscheiden. Lass den Wert NIEMALS leer, auch wenn du unsicher bist.\n"
        beispiel_antwort = {"0": kategorien_dict}
        
    prompt += f"\nBeispiel-Antwort:\n{json.dumps(beispiel_antwort, indent=2)}"
    
    return prompt
