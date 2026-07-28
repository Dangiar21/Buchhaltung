import sys
import os
import traceback
import re

# Utils aus dem übergeordneten Ordner laden
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import load_or_create_targa_list, append_new_targas_to_excel, ask_shorten_desc, get_text, safe_float, read_xml_or_p7m

try:
    import defusedxml.ElementTree as ET
    import pandas as pd
except Exception as e:
    print(f"Fehler beim Laden der Module: {e}")
    print("Hast du 'pip install pandas openpyxl defusedxml' im Terminal ausgeführt?")
    input("\nDrücke Enter zum Beenden...")
    sys.exit(1)


from sdi_parser import parse_sdi_xml

def parse_xml_to_list(xml_path, targa_dict=None, neue_targas_set=None, fehler_log=None, shorten_description=True, client_vat_id=""):
    if targa_dict is None: targa_dict = {}
    if neue_targas_set is None: neue_targas_set = set()
    if fehler_log is None: fehler_log = []
    
    print(f"Lese: {xml_path}")
    
    try:
        parsed_items = parse_sdi_xml(xml_path, targa_dict, neue_targas_set, fehler_log, shorten_description, client_vat_id)
        rechnungspositionen = []
        
        for item in parsed_items:
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
                'CdC': item['CdC'],
                'Kennzeichen': item['Kennzeichen'],
                'Fahrzeugtyp': item['Fahrzeugtyp'],
                'Menge': item['Menge'],
                f'Einzelpreis ({waehrung})': item['Einzelpreis_Roh'],
                f'Gesamtpreis ({waehrung})': item['Gesamtpreis_Roh'],
                'MwSt (%)': item['MwSt']
            })
            
        return rechnungspositionen

    except Exception as e:
        error_msg = f"Fehler beim Parsen von {os.path.basename(xml_path)}: {e}"
        print(error_msg)
        print(traceback.format_exc())
        fehler_log.append(error_msg)
        return []

def run_conversion(paths=None, output_dir=None, nutzerdaten_dir=None):
    if paths is None:
        paths = sys.argv[1:]
        
    alle_positionen = []
    ausgabe_ordner = output_dir

    try:
        if len(paths) > 0:
            for pfad in paths:
                if not ausgabe_ordner:
                    if os.path.isfile(pfad):
                        ausgabe_ordner = os.path.dirname(pfad)
                    else:
                        ausgabe_ordner = pfad

            targa_dict, targa_file = load_or_create_targa_list(nutzerdaten_dir)
            neue_targas_set = set()
            fehler_log = []
            
            shorten_description = ask_shorten_desc()

            client_vat_id = ""
            client_name = os.path.basename(os.path.dirname(nutzerdaten_dir)) if nutzerdaten_dir else "Unbekannt"
            if client_name != "Unbekannt":
                try:
                    from src.db.database import init_db, Kunde
                    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    db_path = os.path.join(base_dir, "Kunden", "kunden.db")
                    session = init_db(db_path)
                    kunde = session.query(Kunde).filter_by(name=client_name).first()
                    if kunde:
                        client_vat_id = (kunde.partita_iva or "").strip()
                        if not client_vat_id:
                            client_vat_id = (kunde.codice_fiscale or "").strip()
                except Exception as e:
                    print(f"Fehler beim Lesen der Datenbank: {e}")

            xml_files_to_process = []
            for pfad in paths:
                if os.path.isfile(pfad) and (pfad.lower().endswith('.xml') or pfad.lower().endswith('.p7m')):
                    xml_files_to_process.append(pfad)
                elif os.path.isdir(pfad):
                    print(f"\nDurchsuche Ordner (inkl. Unterordner): {pfad}")
                    for root_dir, _, files in os.walk(pfad):
                        for filename in files:
                            if filename.lower().endswith('.xml') or filename.lower().endswith('.p7m'):
                                xml_files_to_process.append(os.path.join(root_dir, filename))
                else:
                    print(f"Überspringe: {pfad} (Keine XML/P7M oder Ordner)")
            
            total_files = len(xml_files_to_process)
            for i, xml_file in enumerate(xml_files_to_process):
                alle_positionen.extend(parse_xml_to_list(xml_file, targa_dict, neue_targas_set, fehler_log, shorten_description, client_vat_id))
                percent = int(((i + 1) / total_files) * 100) if total_files > 0 else 100
                print(f"[PROGRESS:{percent}]")
            
            if alle_positionen:
                # Heuristik: Falls Aktiv/Passiv fehlt, anhand der häufigsten VAT raten
                all_vats = []
                for pos in alle_positionen:
                    if pos.get('Liefer ID'): all_vats.append(pos['Liefer ID'])
                    if pos.get('Kunden ID'): all_vats.append(pos['Kunden ID'])
                if all_vats:
                    from collections import Counter
                    guessed_vat = Counter(all_vats).most_common(1)[0][0]
                    for pos in alle_positionen:
                        if not pos.get('Aktiv/Passiv'):
                            if pos.get('Liefer ID') == guessed_vat:
                                pos['Aktiv/Passiv'] = 'Attiva'
                            elif pos.get('Kunden ID') == guessed_vat:
                                pos['Aktiv/Passiv'] = 'Passiva'
                            else:
                                pos['Aktiv/Passiv'] = 'Passiva'
                                
                print(f"\nErstelle Excel-Datei mit {len(alle_positionen)} Positionen...")
                df = pd.DataFrame(alle_positionen)
                
                has_targa = any(pos.get('Kennzeichen', '') for pos in alle_positionen)
                if not has_targa:
                    if 'Kennzeichen' in df.columns:
                        df = df.drop(columns=['Kennzeichen', 'Fahrzeugtyp'])
                
                # Split dataframe by Aktiv/Passiv
                if 'Aktiv/Passiv' in df.columns:
                    df_eingang = df[df['Aktiv/Passiv'] == 'Passiva'].copy().reset_index(drop=True)
                    df_ausgang = df[df['Aktiv/Passiv'] == 'Attiva'].copy().reset_index(drop=True)
                    df_eingang = df_eingang.drop(columns=['Aktiv/Passiv'])
                    df_ausgang = df_ausgang.drop(columns=['Aktiv/Passiv'])
                else:
                    df_eingang = df.copy().reset_index(drop=True)
                    df_ausgang = pd.DataFrame(columns=df.columns)
                
                if output_dir:
                    sammlung_ordner = output_dir
                else:
                    script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
                    sammlung_ordner = os.path.join(script_dir, 'Excel_Sammlung')
                    
                if not os.path.exists(sammlung_ordner):
                    os.makedirs(sammlung_ordner)
                    
                excel_path = os.path.join(sammlung_ordner, 'Gesammelte_XML_Daten.xlsx')
                
                counter = 1
                while os.path.exists(excel_path):
                    excel_path = os.path.join(sammlung_ordner, f'Gesammelte_XML_Daten_{counter}.xlsx')
                    counter += 1

                writer = pd.ExcelWriter(excel_path, engine='openpyxl')
                
                sheets_to_process = []
                if not df_eingang.empty or df_ausgang.empty:
                    df_eingang.to_excel(writer, index=False, sheet_name='Eingangsrechnungen')
                    sheets_to_process.append('Eingangsrechnungen')
                if not df_ausgang.empty:
                    df_ausgang.to_excel(writer, index=False, sheet_name='Ausgangsrechnungen')
                    sheets_to_process.append('Ausgangsrechnungen')

                euro_format = '#,##0.00 €'
                percent_format = '0.00%'

                for sheet_name in sheets_to_process:
                    worksheet = writer.sheets[sheet_name]
                    
                    for column_cells in worksheet.columns:
                        max_length = 0
                        column_letter = column_cells[0].column_letter
                        for cell in column_cells[:50]:
                            try:
                                if cell.value:
                                    val_str = str(cell.value)
                                    length = len(val_str)
                                    if length > max_length:
                                        max_length = length
                            except Exception as e:
                                pass
                        
                        adjusted_width = max_length + 6 
                        if adjusted_width > 70:
                            adjusted_width = 70
                            
                        worksheet.column_dimensions[column_letter].width = adjusted_width
                    
                    col_indices = {cell.value: idx for idx, cell in enumerate(worksheet[1], start=1)}
                    
                    einzelpreis_col = next((idx for name, idx in col_indices.items() if name and str(name).startswith('Einzelpreis')), None)
                    gesamtpreis_col = next((idx for name, idx in col_indices.items() if name and str(name).startswith('Gesamtpreis')), None)
                    mwst_col = col_indices.get('MwSt (%)')
                    
                    for row in range(2, worksheet.max_row + 1):
                        if einzelpreis_col:
                            worksheet.cell(row=row, column=einzelpreis_col).number_format = euro_format
                        if gesamtpreis_col:
                            worksheet.cell(row=row, column=gesamtpreis_col).number_format = euro_format
                        if mwst_col:
                            worksheet.cell(row=row, column=mwst_col).number_format = percent_format
                
                writer.close()
                
                print(f"\n✅ Erfolgreich gespeichert unter: {excel_path}")
                
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
        
        if paths is None or paths == sys.argv[1:]:
            if sys.stdout.isatty():
                input("\nDrücke Enter zum Beenden...")

if __name__ == "__main__":
    run_conversion()
