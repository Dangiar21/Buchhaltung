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

def save_ai_assignments_to_excel(global_rules_path, new_assignments):
    if not new_assignments:
        return
    
    try:
        from openpyxl import load_workbook
        wb = load_workbook(global_rules_path)
        
        if "KI-Zuweisungen" not in wb.sheetnames:
            print("Blatt 'KI-Zuweisungen' nicht gefunden. Speichern übersprungen.")
            return
            
        ws = wb["KI-Zuweisungen"]
        
        start_row = ws.max_row + 1
            
        for assignment in new_assignments:
            lief_id = assignment['Lieferant ID']
            kunden_id = assignment['Kunden ID']
            konto = int(assignment['Konto']) if str(assignment['Konto']).isdigit() else assignment['Konto']
            
            ws.cell(row=start_row, column=1, value=lief_id)
            ws.cell(row=start_row, column=2, value=assignment['Lieferant Name'])
            ws.cell(row=start_row, column=3, value=kunden_id)
            ws.cell(row=start_row, column=4, value=assignment['Kunden Name'])
            ws.cell(row=start_row, column=5, value=assignment['Beschreibung'])
            ws.cell(row=start_row, column=6, value=konto)
            ws.cell(row=start_row, column=7, value=assignment['Status'])
            start_row += 1
            
        while True:
            try:
                wb.save(global_rules_path)
                print(f"\n=> {len(new_assignments)} neue KI-Zuweisungen in {os.path.basename(global_rules_path)} gespeichert!")
                break
            except PermissionError:
                print("\n" + "="*60)
                print("FEHLER BEIM SPEICHERN DER KI-REGELN!")
                print(f"Die Datei {os.path.basename(global_rules_path)} ist in Excel geöffnet.")
                print("Bitte schließe die Datei in Excel und drücke ENTER, um es erneut zu versuchen.")
                print("="*60 + "\n")
                input("Drücke Enter, sobald die Datei geschlossen ist...")
                
    except Exception as e:
        print(f"Fehler beim Anhängen der KI-Zuweisungen: {e}")

def parse_xml_to_list(xml_path, targa_dict, neue_targas_set, fehler_log, rules_dict, shorten_description=True, client_vat_id=""):
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
            desc_norm = re.sub(r'\s+', ' ', desc_short).strip().upper()
            qty_text = get_text(linea, 'Quantita', '1.0')
            price_text = get_text(linea, 'PrezzoUnitario', '0.0')
            total_text = get_text(linea, 'PrezzoTotale', '0.0')
            iva_text = get_text(linea, 'AliquotaIVA', '0.0')
            
            # Sichere Konvertierung in Float
            qty = safe_float(qty_text, 1.0, faktor)
            price = safe_float(price_text, 0.0)
            total = safe_float(total_text, 0.0, faktor)
            iva = safe_float(iva_text, 0.0)
            
            # Extrahiere Targa (Kennzeichen)
            targa_gefunden = ""
            fahrzeugtyp = ""
            altri_dati = linea.findall('.//AltriDatiGestionali')
            for dato in altri_dati:
                tipo = get_text(dato, 'TipoDato').upper()
                if 'TARGA' in tipo or 'TAR' in tipo:
                    targa_gefunden = get_text(dato, 'RiferimentoTesto')
                    break
            if not targa_gefunden and desc:
                # Fallback: Suche in der Beschreibung (z.B. "DIESEL, KZ/Baust.: FL 700 BA - Datum: ...")
                match = re.search(r'KZ/Baust\.:\s*([A-Z0-9\s]+?)\s*(?:-|$)', desc, re.IGNORECASE)
                if match:
                    targa_gefunden = match.group(1).strip()
            
            if targa_gefunden:
                # Normalisiere Kennzeichen für die Suche
                targa_norm = targa_gefunden.strip().upper().replace(' ', '')
                fahrzeugtyp = targa_dict.get(targa_norm, "UNBEKANNT")
                if targa_norm not in targa_dict and targa_norm not in neue_targas_set:
                    neue_targas_set.add(targa_norm)

            abs_path = os.path.abspath(xml_path)
            dateiname = os.path.basename(xml_path)
            hyperlink_formel = f'=HYPERLINK("{abs_path}", "{dateiname}")'

            # Konto ermitteln
            conto, is_pending = Buchung_Regeln.assign_account(desc_norm, desc_short, lieferant, liefer_id, kunden_id, rules_dict)
            
            aktiv_passiv = ""
            if client_vat_id:
                if liefer_id == client_vat_id:
                    aktiv_passiv = "Attiva"
                elif kunden_id == client_vat_id:
                    aktiv_passiv = "Passiva"
            
            rechnungspositionen.append({
                'Aktiv/Passiv': aktiv_passiv,
                'Typ': dokumenttyp,
                'Rechnungsnummer': rechnungs_nummer,
                'Datum': rechnungs_datum,
                'Lieferant': lieferant,
                'Liefer ID': liefer_id,
                'Kunde': kunde,
                'Kunden ID': kunden_id,
                'Beschreibung': desc_short,
                'Conto': conto,
                'is_pending': is_pending,
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
            
            shorten_description = ask_shorten_desc()

            pdf_paths = []
            for pfad in paths:
                if os.path.isfile(pfad):
                    lower_pfad = pfad.lower()
                    if lower_pfad.endswith('.xml') or lower_pfad.endswith('.p7m'):
                        alle_positionen.extend(parse_xml_to_list(pfad, targa_dict, neue_targas_set, fehler_log, rules_dict, shorten_description, client_vat_id))
                    elif lower_pfad.endswith('.pdf'):
                        pdf_paths.append(pfad)
                elif os.path.isdir(pfad):
                    print(f"\nDurchsuche Ordner (inkl. Unterordner): {pfad}")
                    for root_dir, _, files in os.walk(pfad):
                        for filename in files:
                            lower_file = filename.lower()
                            if lower_file.endswith('.xml') or lower_file.endswith('.p7m'):
                                alle_positionen.extend(parse_xml_to_list(os.path.join(root_dir, filename), targa_dict, neue_targas_set, fehler_log, rules_dict, shorten_description, client_vat_id))
                            elif lower_file.endswith('.pdf'):
                                pdf_paths.append(os.path.join(root_dir, filename))
                else:
                    print(f"Überspringe: {pfad} (Keine XML/P7M/PDF oder Ordner)")
                    
            if pdf_paths:
                import Buchung_KI
                import PDF_Parser
                api_key = Buchung_KI.get_api_key(base_dir)
                if not api_key:
                    print("\nWarnung: Kein Gemini API Key gefunden. PDFs können nicht verarbeitet werden.")
                else:
                    print(f"\nVerarbeite {len(pdf_paths)} PDF-Rechnungen mit Gemini OCR...")
                    pdf_results = PDF_Parser.parse_pdfs(pdf_paths, api_key)
                    
                    for p_path, items in pdf_results.items():
                        if not items:
                            fehler_log.append(f"{os.path.basename(p_path)}: Konnte nicht per OCR ausgelesen werden.")
                            continue
                            
                        abs_path = os.path.abspath(p_path)
                        dateiname = os.path.basename(p_path)
                        hyperlink_formel = f'=HYPERLINK("{abs_path}", "{dateiname}")'
                        
                        for pos in items:
                            typ = pos.get('Typ', 'Rechnung')
                            faktor = -1.0 if 'gutschrift' in typ.lower() else 1.0
                            
                            desc = pos.get('Beschreibung', 'Keine Beschreibung')
                            desc_short = desc.split(',', 1)[0].strip() if (',' in desc and shorten_description) else desc
                            desc_norm = re.sub(r'\s+', ' ', desc_short).strip().upper()
                            
                            lieferant = pos.get('Lieferant', 'Unbekannter Lieferant')
                            liefer_id = str(pos.get('Liefer ID', '')).strip().replace(' ', '')
                            kunde = pos.get('Kunde', 'Unbekannter Kunde')
                            kunden_id = str(pos.get('Kunden ID', '')).strip().replace(' ', '')
                            
                            targa_gefunden = str(pos.get('Kennzeichen', '')).strip().upper().replace(' ', '')
                            fahrzeugtyp = ""
                            if targa_gefunden:
                                fahrzeugtyp = targa_dict.get(targa_gefunden, "UNBEKANNT")
                                if targa_gefunden not in targa_dict and targa_gefunden not in neue_targas_set:
                                    neue_targas_set.add(targa_gefunden)
                                    
                            conto, is_pending = Buchung_Regeln.assign_account(desc_norm, desc_short, lieferant, liefer_id, kunden_id, rules_dict)
                            
                            qty = safe_float(pos.get('Menge', 1.0), 1.0, faktor)
                            price = safe_float(pos.get('Einzelpreis', 0.0), 0.0)
                            
                            aktiv_passiv = ""
                            if client_vat_id:
                                if liefer_id == client_vat_id:
                                    aktiv_passiv = "Attiva"
                                elif kunden_id == client_vat_id:
                                    aktiv_passiv = "Passiva"
                            
                            alle_positionen.append({
                                'Aktiv/Passiv': aktiv_passiv,
                                'Typ': typ,
                                'Rechnungsnummer': pos.get('Rechnungsnummer', ''),
                                'Datum': pos.get('Datum', ''),
                                'Lieferant': lieferant,
                                'Liefer ID': liefer_id,
                                'Kunde': kunde,
                                'Kunden ID': kunden_id,
                                'Beschreibung': desc_short,
                                'Conto': conto,
                                'is_pending': is_pending,
                                'CdC': targa_gefunden,
                                'Kennzeichen': targa_gefunden,
                                'Fahrzeugtyp': fahrzeugtyp,
                                'Menge': qty,
                                f'Einzelpreis ({pos.get("Waehrung", "EUR")})': price,
                                'Gesamtpreis': safe_float(pos.get('Gesamtpreis', 0.0), 0.0, faktor),
                                'MwSt Satz': safe_float(pos.get('MwSt_Satz', 0.0), 0.0),
                                'Dateiname': hyperlink_formel
                            })
            
            
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
                    
                    new_ai_assignments = []
                    
                    for key, data in unique_unknowns.items():
                        unique_id = data['item']['id']
                        if unique_id in ai_results:
                            konto = ai_results[unique_id]
                            
                            new_ai_assignments.append({
                                'Lieferant ID': key[0],
                                'Lieferant Name': data['item'].get('Lieferant', ''),
                                'Kunden ID': key[2],
                                'Kunden Name': data['item'].get('Kunde', ''),
                                'Beschreibung': key[1],
                                'Konto': konto,
                                'Status': 'AUSSTEHEND'
                            })
                            
                            for original_i in data['indices']:
                                alle_positionen[original_i]['Conto'] = konto
                                ai_indices.append(original_i + 2) # +2 weil Excel bei 1 startet und Zeile 1 der Header ist
                                
                    if new_ai_assignments:
                        save_ai_assignments_to_excel(global_rules_path, new_ai_assignments)

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