import sys
import os
import traceback

# 1. Wir versuchen die Module zu laden. Wenn das fehlschlägt, fangen wir den Fehler ab.
import io
try:
    import xml.etree.ElementTree as ET
    import pandas as pd
except ImportError as e:
    print(f"Fehler beim Laden der Module: {e}")
    print("Hast du 'pip install pandas openpyxl' im Terminal ausgeführt?")
    input("\nDrücke Enter zum Beenden...")
    sys.exit(1)

def get_text(node, xpath, default=""):
    if node is None:
        return default
    child = node.find(xpath)
    return child.text if child is not None and child.text else default

def parse_xml_to_list(xml_path):
    print(f"Lese: {xml_path}")
    rechnungspositionen = []
    
    try:
        source = xml_path
        if xml_path.lower().endswith('.p7m'):
            with open(xml_path, 'rb') as f:
                data = f.read()
            
            # Suche nach dem Start des XML (verschiedene Tags möglich)
            start_tags = [b'<?xml', b'<p:FatturaElettronica', b'<FatturaElettronica', b'<ns2:FatturaElettronica', b'<ns3:FatturaElettronica']
            start = -1
            for tag in start_tags:
                start = data.find(tag)
                if start != -1:
                    break
            
            if start == -1:
                print(f"Fehler: Konnte keinen XML-Anfang in {xml_path} finden.")
                return []
                
            # Suche nach dem Ende des XML
            end = data.rfind(b'FatturaElettronica>')
            if end == -1:
                print(f"Fehler: Konnte kein XML-Ende in {xml_path} finden.")
                return []
                
            end += len(b'FatturaElettronica>')
            xml_data = data[start:end]
            source = io.BytesIO(xml_data)

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
            qty_text = get_text(linea, 'Quantita', '1.0')
            price_text = get_text(linea, 'PrezzoUnitario', '0.0')
            total_text = get_text(linea, 'PrezzoTotale', '0.0')
            iva_text = get_text(linea, 'AliquotaIVA', '0.0')
            
            # Sichere Konvertierung in Float
            try: qty = float(qty_text)
            except ValueError: qty = 1.0
                
            try: price = float(price_text)
            except ValueError: price = 0.0
                
            try: total = float(total_text)
            except ValueError: total = 0.0

            try: iva = float(iva_text)
            except ValueError: iva = 0.0
            
            rechnungspositionen.append({
                'Rechnungsnummer': rechnungs_nummer,
                'Datum': rechnungs_datum,
                'Lieferant': lieferant,
                'Liefer ID': liefer_id,
                'Kunde': kunde,
                'Kunden ID': kunden_id,
                'Beschreibung': desc,
                'Menge': qty,
                f'Einzelpreis ({waehrung})': price,
                f'Gesamtpreis ({waehrung})': total,
                'MwSt (%)': iva
            })
            
    except Exception as e:
        print(f"Fehler beim Parsen von {xml_path}:")
        print(traceback.format_exc())
        
    return rechnungspositionen

if __name__ == "__main__":
    alle_positionen = []
    ausgabe_ordner = ""

    try:
        if len(sys.argv) > 1:
            for pfad in sys.argv[1:]:
                # Setze den Ausgabeordner auf das Verzeichnis des ersten Elements
                if not ausgabe_ordner:
                    if os.path.isfile(pfad):
                        ausgabe_ordner = os.path.dirname(pfad)
                    else:
                        ausgabe_ordner = pfad

                if os.path.isfile(pfad) and (pfad.lower().endswith('.xml') or pfad.lower().endswith('.p7m')):
                    alle_positionen.extend(parse_xml_to_list(pfad))
                elif os.path.isdir(pfad):
                    print(f"\nDurchsuche Ordner: {pfad}")
                    for filename in os.listdir(pfad):
                        if filename.lower().endswith('.xml') or filename.lower().endswith('.p7m'):
                            alle_positionen.extend(parse_xml_to_list(os.path.join(pfad, filename)))
                else:
                    print(f"Überspringe: {pfad} (Keine XML/P7M oder Ordner)")
            
            if alle_positionen:
                print(f"\nErstelle Excel-Datei mit {len(alle_positionen)} Positionen...")
                df = pd.DataFrame(alle_positionen)
                
                # Excel Datei generieren
                excel_path = os.path.join(ausgabe_ordner, 'Gesammelte_Rechnungen.xlsx')
                
                # Falls die Datei schon existiert, einen eindeutigen Namen finden
                counter = 1
                while os.path.exists(excel_path):
                    excel_path = os.path.join(ausgabe_ordner, f'Gesammelte_Rechnungen_{counter}.xlsx')
                    counter += 1

                writer = pd.ExcelWriter(excel_path, engine='openpyxl')
                df.to_excel(writer, index=False, sheet_name='Rechnungen')
                
                worksheet = writer.sheets['Rechnungen']
                worksheet.column_dimensions['A'].width = 15 # Rechnungsnummer
                worksheet.column_dimensions['B'].width = 12 # Datum
                worksheet.column_dimensions['C'].width = 25 # Lieferant
                worksheet.column_dimensions['D'].width = 15 # Liefer ID
                worksheet.column_dimensions['E'].width = 25 # Kunde
                worksheet.column_dimensions['F'].width = 15 # Kunden ID
                worksheet.column_dimensions['G'].width = 40 # Beschreibung
                worksheet.column_dimensions['H'].width = 10 # Menge
                worksheet.column_dimensions['I'].width = 18 # Einzelpreis
                worksheet.column_dimensions['J'].width = 18 # Gesamtpreis
                worksheet.column_dimensions['K'].width = 10 # MwSt
                
                writer.close()
                
                print(f"Erfolgreich gespeichert unter: {excel_path}")
                
                if os.name == 'nt':
                    os.startfile(excel_path)
                elif sys.platform == 'darwin':
                    os.system(f'open "{excel_path}"')
                else:
                    os.system(f'xdg-open "{excel_path}"')
            else:
                print("\nEs wurden keine gültigen Rechnungspositionen gefunden.")
        else:
            print("Ziehe eine oder mehrere XML- oder P7M-Dateien (Drag & Drop) auf dieses Skript-Icon, um sie zu konvertieren.")
            print("Oder ziehe einen ganzen Ordner mit XML/P7M-Dateien auf das Icon.")
    except Exception as e:
        print("\nEin unerwarteter Fehler ist aufgetreten:")
        print(traceback.format_exc())
        
    # Dieser Befehl hält das Fenster ganz am Schluss offen, egal was passiert ist
    input("\nDrücke Enter zum Beenden...")