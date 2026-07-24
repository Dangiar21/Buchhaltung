import sys
import os
import traceback
import re

# Utils aus dem übergeordneten Ordner laden
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import load_or_create_targa_list, append_new_targas_to_excel, ask_shorten_desc, get_text, safe_float, read_xml_or_p7m

# 1. Wir versuchen die Module zu laden. Wenn das fehlschlägt, fangen wir den Fehler ab.
import Buchung_Regeln
try:
    import defusedxml.ElementTree as ET
    import pandas as pd
except Exception as e:
    print(f"Fehler beim Laden der Module: {e}")
    print("Hast du 'pip install pandas openpyxl' im Terminal ausgeführt?")
    input("\nDrücke Enter zum Beenden...")
    sys.exit(1)

def ask_shorten_desc_local_fallback():
    # Wird nun über utils.py importiert.
    pass

from sdi_parser import parse_sdi_xml

def parse_xml_to_list(xml_path, targa_dict, neue_targas_set, fehler_log, rules_dict, shorten_description=True, client_vat_id="", db_konten_cache=None):
    if db_konten_cache is None: db_konten_cache = {}
    print(f"Lese: {xml_path}")
    
    parsed_items = parse_sdi_xml(xml_path, targa_dict, neue_targas_set, fehler_log, shorten_description, client_vat_id)
    rechnungspositionen = []
    
    for item in parsed_items:
        # Konto ermitteln
        cache_key = f"{item['Lieferant']} | {item['Beschreibung']}".strip().upper()
        if cache_key in db_konten_cache:
            conto = str(db_konten_cache[cache_key]['value'])
            is_pending = not db_konten_cache[cache_key]['confirmed']
        else:
            import Buchung_Regeln
            conto, is_pending = Buchung_Regeln.assign_account(
                item['Desc_Norm'], item['Beschreibung'], item['Lieferant'], item['Liefer ID'], item['Kunden ID'], rules_dict
            )
            
        waehrung = item.get('Waehrung', 'EUR')
        
        rechnungspositionen.append({
            'Aktiv/Passiv': item['Aktiv/Passiv'],
            'Typ': item['Typ'],
            'Rechnungsnummer': item['Rechnungsnummer'],
            'Datum': item['Datum'],
            'Lieferant': item['Lieferant'],
            'Liefer ID': item['Liefer ID'],
            'Kunde': item['Kunde'],
            'Kunden ID': item['Kunden ID'],
            'Beschreibung': item['Beschreibung'],
            'Conto': conto,
            'is_pending': is_pending,
            'CdC': item['CdC'],
            'Kennzeichen': item['Kennzeichen'],
            'Fahrzeugtyp': item['Fahrzeugtyp'],
            'Menge': item['Menge'],
            f'Einzelpreis ({waehrung})': item['Einzelpreis_Roh'],
            f'Gesamtpreis ({waehrung})': item['Gesamtpreis_Roh'],
            'MwSt (%)': item['MwSt'],
            'Datei': item['Datei_Link']
        })
        
    return rechnungspositionen

def run_conversion(paths=None, output_dir=None, nutzerdaten_dir=None):
    if paths is None:
        paths = sys.argv[1:]
        
    alle_positionen = []
    ausgabe_ordner = output_dir

    try:
        if len(paths) > 0:
            for pfad in paths:
                # Setze den Ausgabeordner auf das Verzeichnis des ersten Elements, falls keiner gegeben
                if not ausgabe_ordner:
                    if os.path.isfile(pfad):
                        ausgabe_ordner = os.path.dirname(pfad)
                    else:
                        ausgabe_ordner = pfad

            # Lade oder erstelle die Targa Liste VOR dem Parsen der XML Dateien
            targa_dict, targa_file = load_or_create_targa_list(nutzerdaten_dir)
            
            # --- Regel-System initialisieren ---
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            global_rules_path = os.path.join(base_dir, "Systemdaten", "Globale_KontenRegeln.xlsx")
            Buchung_Regeln.ensure_rule_file(global_rules_path)
            
            client_rules_path = None
            if nutzerdaten_dir:
                client_rules_path = os.path.join(nutzerdaten_dir, "Kunden_KontenRegeln.xlsx")
                Buchung_Regeln.ensure_rule_file(client_rules_path)
            else:
                client_rules_path = os.path.join(base_dir, "Kunden", "Unbekannt", "Nutzerdaten", "Kunden_KontenRegeln.xlsx")
                Buchung_Regeln.ensure_rule_file(client_rules_path)
                
            rules_dict = Buchung_Regeln.load_rules(global_rules_path, client_rules_path)
            
            neue_targas_set = set()
            fehler_log = []
            
            client_vat_id = ""
            if nutzerdaten_dir:
                info_path = os.path.join(nutzerdaten_dir, "info.json")
                if os.path.exists(info_path):
                    try:
                        import json
                        with open(info_path, "r", encoding="utf-8") as f:
                            client_data = json.load(f)
                            client_vat_id = client_data.get("Partita_IVA", "").strip()
                    except Exception as e:
                        print(f"Fehler beim Lesen von info.json: {e}")
            
            # Lade den DB Cache für den Kunden, um UI-Bestätigungen zu berücksichtigen
            kunden_id_ordner = os.path.basename(os.path.dirname(nutzerdaten_dir)) if nutzerdaten_dir else "Unbekannt"
            try:
                from DatabaseManager import get_db
                db = get_db()
                db_konten_cache = db.get_konten_cache_full(kunden_id_ordner)
            except Exception:
                db_konten_cache = {}
            
            shorten_description = ask_shorten_desc()

            for pfad in paths:
                if os.path.isfile(pfad):
                    lower_pfad = pfad.lower()
                    if lower_pfad.endswith('.xml') or lower_pfad.endswith('.p7m'):
                        alle_positionen.extend(parse_xml_to_list(pfad, targa_dict, neue_targas_set, fehler_log, rules_dict, shorten_description, client_vat_id, db_konten_cache))
                elif os.path.isdir(pfad):
                    print(f"\nDurchsuche Ordner (inkl. Unterordner): {pfad}")
                    for root_dir, _, files in os.walk(pfad):
                        for filename in files:
                            lower_file = filename.lower()
                            if lower_file.endswith('.xml') or lower_file.endswith('.p7m'):
                                alle_positionen.extend(parse_xml_to_list(os.path.join(root_dir, filename), targa_dict, neue_targas_set, fehler_log, rules_dict, shorten_description, client_vat_id, db_konten_cache))
                else:
                    print(f"Überspringe: {pfad} (Keine XML/P7M oder Ordner)")
                    
            
            if alle_positionen:
                # --- KI Fallback ---
                import Buchung_KI
                api_key = Buchung_KI.get_api_key(base_dir)
                
                ai_indices = []
                unique_unknowns = {}
                for i, pos in enumerate(alle_positionen):
                    if pos.pop('is_pending', False):
                        ai_indices.append(i + 2)
                        
                    if pos.get('Conto') == '???':
                        desc_norm = re.sub(r'\s+', ' ', pos.get('Beschreibung', '')).strip().upper()
                        key = (pos.get('Liefer ID', ''), desc_norm, pos.get('Kunden ID', ''))
                        if key not in unique_unknowns:
                            excluded_keys = {'Typ', 'Liefer ID', 'Kunden ID', 'Menge', 'MwSt Satz', 'Dateiname', 'Conto', 'is_pending'}
                            item_data = {'id': str(len(unique_unknowns))}
                            for k, v in pos.items():
                                if k not in excluded_keys and not str(k).startswith('Einzelpreis') and not str(k).startswith('Gesamtpreis'):
                                    item_data[k] = v
                                    
                            unique_unknowns[key] = {
                                'item': item_data,
                                'indices': []
                            }
                        unique_unknowns[key]['indices'].append(i)
                        
                if unique_unknowns and api_key:
                    items_to_send = [u['item'] for u in unique_unknowns.values()]
                    total_dups = sum(len(u['indices']) for u in unique_unknowns.values())
                    print(f"\nSende {len(items_to_send)} eindeutige unbekannte Artikel an die KI (Dedupliziert von {total_dups} Positionen)...")
                    ai_results = Buchung_KI.ask_gemini_batch(items_to_send, api_key, nutzerdaten_dir)
                    for key, data in unique_unknowns.items():
                        unique_id = data['item']['id']
                        if unique_id in ai_results:
                            konto = ai_results[unique_id]
                            for original_i in data['indices']:
                                alle_positionen[original_i]['Conto'] = konto
                                ai_indices.append(original_i + 2)

                # Generelle Konvertierung aller als String gespeicherten Nummern zu Integer
                for pos in alle_positionen:
                    c = pos.get('Conto')
                    if isinstance(c, str) and c.isdigit():
                        pos['Conto'] = int(c)

                print(f"\nErstelle Excel-Datei mit {len(alle_positionen)} Positionen...")
                df = pd.DataFrame(alle_positionen)
                
                # Wenn kein einziges Kennzeichen gefunden wurde, die beiden Spalten entfernen
                has_targa = any(pos.get('Kennzeichen', '') for pos in alle_positionen)
                if not has_targa:
                    if 'Kennzeichen' in df.columns:
                        df = df.drop(columns=['Kennzeichen', 'Fahrzeugtyp'])
                
                # Excel Datei generieren
                if output_dir:
                    sammlung_ordner = output_dir
                else:
                    script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
                    sammlung_ordner = os.path.join(script_dir, 'Excel_Sammlung')
                    
                if not os.path.exists(sammlung_ordner):
                    os.makedirs(sammlung_ordner)
                    
                excel_path = os.path.join(sammlung_ordner, 'Gesammelte_Buchungen.xlsx')
                
                # Falls the Datei schon existiert, einen eindeutigen Namen finden
                counter = 1
                while os.path.exists(excel_path):
                    excel_path = os.path.join(sammlung_ordner, f'Gesammelte_Buchungen_{counter}.xlsx')
                    counter += 1

                writer = pd.ExcelWriter(excel_path, engine='openpyxl')
                df.to_excel(writer, index=False, sheet_name='Buchungen')
                
                worksheet = writer.sheets['Buchungen']
                # Automatische Spaltenbreite (Performance-optimiert: nur erste 50 Zeilen prüfen)
                for column_cells in worksheet.columns:
                    max_length = 0
                    column_letter = column_cells[0].column_letter
                    for cell in column_cells[:50]:
                        try:
                            if cell.value:
                                val_str = str(cell.value)
                                # Bei Hyperlink-Formeln den angezeigten Text für die Länge verwenden
                                if val_str.startswith('=HYPERLINK'):
                                    parts = val_str.split('", "')
                                    if len(parts) > 1:
                                        val_str = parts[1].replace('")', '').strip()
                                
                                length = len(val_str)
                                if length > max_length:
                                    max_length = length
                        except Exception as e:
                            print(f'Fehler: {e}')
                            pass
                    
                    # Breite = maximale Textlänge + Puffer (ca. 1cm)
                    adjusted_width = max_length + 6 
                    if adjusted_width > 70:  # Spalten nicht unendlich groß machen
                        adjusted_width = 70
                        
                    worksheet.column_dimensions[column_letter].width = adjusted_width
                
                # Dynamische Spaltenindizes finden (1-basiert für openpyxl)
                col_indices = {cell.value: idx for idx, cell in enumerate(worksheet[1], start=1)}
                
                einzelpreis_col = next((idx for name, idx in col_indices.items() if name and str(name).startswith('Einzelpreis')), None)
                gesamtpreis_col = next((idx for name, idx in col_indices.items() if name and str(name).startswith('Gesamtpreis')), None)
                mwst_col = col_indices.get('MwSt (%)')
                datei_col = col_indices.get('Datei')

                euro_format = '#,##0.00 €'
                percent_format = '0.00%'
                from openpyxl.styles import Font
                link_font = Font(color="0563C1", underline="single")
                red_font = Font(color="FF0000", bold=True)
                conto_col = col_indices.get('Conto')
                
                for row in range(2, worksheet.max_row + 1):
                    if einzelpreis_col:
                        worksheet.cell(row=row, column=einzelpreis_col).number_format = euro_format
                    if gesamtpreis_col:
                        worksheet.cell(row=row, column=gesamtpreis_col).number_format = euro_format
                    if mwst_col:
                        worksheet.cell(row=row, column=mwst_col).number_format = percent_format
                    if datei_col:
                        worksheet.cell(row=row, column=datei_col).font = link_font
                    
                    if conto_col and row in ai_indices:
                        worksheet.cell(row=row, column=conto_col).font = red_font
                

                
                writer.close()
                
                print(f"Erfolgreich gespeichert unter: {excel_path}")
                
                # --- B Point CSV Export ---
                try:
                    import BPoint_Export
                    csv_path = excel_path.replace('.xlsx', '_PrimaNota.csv')
                    BPoint_Export.export_to_bpoint_csv(df, csv_path)
                except Exception as e:
                    print(f"Fehler beim B Point CSV-Export: {e}")
                
                append_new_targas_to_excel(targa_file, neue_targas_set)
                
                if fehler_log:
                    log_pfad = os.path.join(sammlung_ordner, 'Fehlgeschlagen.txt')
                    with open(log_pfad, 'w', encoding='utf-8') as f:
                        f.write("Folgende Fehler traten beim Verarbeiten auf:\n\n")
                        for err in fehler_log:
                            f.write(f"- {err}\n")
                    print(f"\nAchtung: Es gab Fehler. Details siehe: {log_pfad}")
                
                if os.name == 'nt' or sys.platform == 'win32':
                    os.startfile(excel_path)
                elif sys.platform == 'darwin':
                    import subprocess
                    subprocess.run(['open', excel_path], check=True)
                else:
                    import subprocess
                    subprocess.run(['xdg-open', excel_path], check=True)
            else:
                print("\nEs wurden keine gültigen Rechnungspositionen gefunden.")
        else:
            print("Ziehe eine oder mehrere XML- oder P7M-Dateien (Drag & Drop) auf dieses Skript-Icon, um sie zu konvertieren.")
            print("Oder ziehe einen ganzen Ordner mit XML/P7M-Dateien auf das Icon.")
    except Exception as e:
        print("\nEin unerwarteter Fehler ist aufgetreten:")
        print(traceback.format_exc())
        
        # Dieser Befehl hält das Fenster ganz am Schluss offen, egal was passiert ist
        if paths is None or paths == sys.argv[1:]:
            if sys.stdout.isatty():
                input("\nDrücke Enter zum Beenden...")

if __name__ == "__main__":
    run_conversion()