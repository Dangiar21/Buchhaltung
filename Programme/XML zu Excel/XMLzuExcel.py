import sys
import os
import traceback
import re
import io

# Utils aus dem übergeordneten Ordner laden
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import load_or_create_targa_list, append_new_targas_to_excel, ask_shorten_desc, get_text, safe_float, read_xml_or_p7m

try:
    import defusedxml.ElementTree as ET
    import pandas as pd
    from openpyxl import Workbook, load_workbook
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.styles import Font
except Exception as e:
    print(f"Fehler beim Laden der Module: {e}")
    print("Hast du 'pip install pandas openpyxl defusedxml' im Terminal ausgeführt?")
    input("\nDrücke Enter zum Beenden...")
    sys.exit(1)

def ask_shorten_desc_local_fallback():
    # Wird nun über utils.py importiert.
    pass

def parse_xml_to_list(xml_path, targa_dict, neue_targas_set, fehler_log, shorten_description=True):
    print(f"Lese: {xml_path}")
    rechnungspositionen = []
    
    try:
        source = read_xml_or_p7m(xml_path)
        if source is None:
            print(f"Fehler: Konnte XML nicht aus {xml_path} extrahieren.")
            return []

        it = ET.iterparse(source)
        for _, el in it:
            if '}' in el.tag:
                el.tag = el.tag.split('}', 1)[1]
        root = it.root

        # 1. Lieferant (CedentePrestatore)
        lieferant_node = root.find('.//CedentePrestatore//DatiAnagrafici//Anagrafica')
        lieferant = "Unbekannter Lieferant"
        if lieferant_node is not None:
            denominazione = get_text(lieferant_node, 'Denominazione')
            if denominazione:
                lieferant = denominazione
            else:
                nome = get_text(lieferant_node, 'Nome')
                cognome = get_text(lieferant_node, 'Cognome')
                if nome or cognome:
                    lieferant = f"{nome} {cognome}".strip()
                    
        liefer_id = get_text(root, './/CedentePrestatore//DatiAnagrafici//IdFiscaleIVA/IdCodice')

        # 2. Rechnungsdaten (DatiGeneraliDocumento)
        dati_generali = root.find('.//DatiGeneraliDocumento')
        rechnungs_datum = get_text(dati_generali, 'Data')
        rechnungs_nummer = get_text(dati_generali, 'Numero')
        waehrung = get_text(dati_generali, 'Divisa', 'EUR')
        
        tipo_documento = get_text(dati_generali, 'TipoDocumento', 'TD01')
        dokumenttyp = "Rechnung"
        faktor = 1.0
        if tipo_documento == 'TD04':
            dokumenttyp = "Gutschrift"
            faktor = -1.0
        elif tipo_documento == 'TD05':
            dokumenttyp = "Belastungsanzeige"
        elif tipo_documento == 'TD08':
            dokumenttyp = "Gutschrift (vereinfacht)"
            faktor = -1.0

        # 3. Kunde (CessionarioCommittente)
        kunde_node = root.find('.//CessionarioCommittente//DatiAnagrafici//Anagrafica')
        kunde = "Unbekannter Kunde"
        if kunde_node is not None:
            k_denominazione = get_text(kunde_node, 'Denominazione')
            if k_denominazione:
                kunde = k_denominazione
            else:
                k_nome = get_text(kunde_node, 'Nome')
                k_cognome = get_text(kunde_node, 'Cognome')
                if k_nome or k_cognome:
                    kunde = f"{k_nome} {k_cognome}".strip()

        kunden_id = get_text(root, './/CessionarioCommittente//DatiAnagrafici//IdFiscaleIVA/IdCodice')

        dati_linee = root.findall('.//DettaglioLinee')
        
        for linea in dati_linee:
            desc = get_text(linea, 'Descrizione', 'Keine Beschreibung')
            desc_short = desc.split(',', 1)[0].strip() if (',' in desc and shorten_description) else desc
            qty_text = get_text(linea, 'Quantita', '1.0')
            price_text = get_text(linea, 'PrezzoUnitario', '0.0')
            total_text = get_text(linea, 'PrezzoTotale', '0.0')
            iva_text = get_text(linea, 'AliquotaIVA', '0.0')
            
            qty = safe_float(qty_text, 1.0, faktor)
            price = safe_float(price_text, 0.0)
            total = safe_float(total_text, 0.0, faktor)
            iva = safe_float(iva_text, 0.0)
            
            targa_gefunden = ""
            fahrzeugtyp = ""
            altri_dati = linea.findall('.//AltriDatiGestionali')
            for dato in altri_dati:
                tipo = get_text(dato, 'TipoDato').upper()
                if 'TARGA' in tipo or 'TAR' in tipo:
                    targa_gefunden = get_text(dato, 'RiferimentoTesto')
                    break
            if not targa_gefunden and desc:
                match = re.search(r'KZ/Baust\.:\s*([A-Z0-9\s]+?)\s*(?:-|$)', desc, re.IGNORECASE)
                if match:
                    targa_gefunden = match.group(1).strip()
            
            if targa_gefunden:
                targa_norm = targa_gefunden.strip().upper().replace(' ', '')
                fahrzeugtyp = targa_dict.get(targa_norm, "UNBEKANNT")
                if targa_norm not in targa_dict and targa_norm not in neue_targas_set:
                    neue_targas_set.add(targa_norm)

            abs_path = os.path.abspath(xml_path)
            dateiname = os.path.basename(xml_path)
            hyperlink_formel = f'=HYPERLINK("{abs_path}", "{dateiname}")'
            
            rechnungspositionen.append({
                'Typ': dokumenttyp,
                'Rechnungsnummer': rechnungs_nummer,
                'Datum': rechnungs_datum,
                'Lieferant': lieferant,
                'Liefer ID': liefer_id,
                'Kunde': kunde,
                'Kunden ID': kunden_id,
                'Beschreibung': desc_short,
                'CdC': targa_gefunden if targa_gefunden else "",
                'Kennzeichen': targa_gefunden,
                'Fahrzeugtyp': fahrzeugtyp,
                'Menge': qty,
                f'Einzelpreis ({waehrung})': price,
                f'Gesamtpreis ({waehrung})': total,
                'MwSt (%)': iva / 100.0,
                'Datei': hyperlink_formel
            })
            
    except Exception as e:
        error_msg = f"Fehler beim Parsen von {os.path.basename(xml_path)}: {e}"
        print(error_msg)
        print(traceback.format_exc())
        fehler_log.append(error_msg)
        
    return rechnungspositionen

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

            for pfad in paths:
                if os.path.isfile(pfad) and (pfad.lower().endswith('.xml') or pfad.lower().endswith('.p7m')):
                    alle_positionen.extend(parse_xml_to_list(pfad, targa_dict, neue_targas_set, fehler_log, shorten_description))
                elif os.path.isdir(pfad):
                    print(f"\nDurchsuche Ordner (inkl. Unterordner): {pfad}")
                    for root_dir, _, files in os.walk(pfad):
                        for filename in files:
                            if filename.lower().endswith('.xml') or filename.lower().endswith('.p7m'):
                                alle_positionen.extend(parse_xml_to_list(os.path.join(root_dir, filename), targa_dict, neue_targas_set, fehler_log, shorten_description))
                else:
                    print(f"Überspringe: {pfad} (Keine XML/P7M oder Ordner)")
            
            if alle_positionen:
                print(f"\nErstelle Excel-Datei mit {len(alle_positionen)} Positionen...")
                df = pd.DataFrame(alle_positionen)
                
                has_targa = any(pos.get('Kennzeichen', '') for pos in alle_positionen)
                if not has_targa:
                    if 'Kennzeichen' in df.columns:
                        df = df.drop(columns=['Kennzeichen', 'Fahrzeugtyp'])
                
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
                df.to_excel(writer, index=False, sheet_name='XML_Daten')
                
                worksheet = writer.sheets['XML_Daten']
                for column_cells in worksheet.columns:
                    max_length = 0
                    column_letter = column_cells[0].column_letter
                    for cell in column_cells[:50]:
                        try:
                            if cell.value:
                                val_str = str(cell.value)
                                if val_str.startswith('=HYPERLINK'):
                                    parts = val_str.split('", "')
                                    if len(parts) > 1:
                                        val_str = parts[1].replace('")', '').strip()
                                
                                length = len(val_str)
                                if length > max_length:
                                    max_length = length
                        except:
                            pass
                    
                    adjusted_width = max_length + 6 
                    if adjusted_width > 70:
                        adjusted_width = 70
                        
                    worksheet.column_dimensions[column_letter].width = adjusted_width
                
                col_indices = {cell.value: idx for idx, cell in enumerate(worksheet[1], start=1)}
                
                einzelpreis_col = next((idx for name, idx in col_indices.items() if name and str(name).startswith('Einzelpreis')), None)
                gesamtpreis_col = next((idx for name, idx in col_indices.items() if name and str(name).startswith('Gesamtpreis')), None)
                mwst_col = col_indices.get('MwSt (%)')
                datei_col = col_indices.get('Datei')

                euro_format = '#,##0.00 €'
                percent_format = '0.00%'
                from openpyxl.styles import Font
                link_font = Font(color="0563C1", underline="single")
                
                for row in range(2, worksheet.max_row + 1):
                    if einzelpreis_col:
                        worksheet.cell(row=row, column=einzelpreis_col).number_format = euro_format
                    if gesamtpreis_col:
                        worksheet.cell(row=row, column=gesamtpreis_col).number_format = euro_format
                    if mwst_col:
                        worksheet.cell(row=row, column=mwst_col).number_format = percent_format
                    if datei_col:
                        worksheet.cell(row=row, column=datei_col).font = link_font
                
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
