import os
import re
import traceback

try:
    import defusedxml.ElementTree as ET
except ImportError:
    pass

# utils.py is in the same directory
from utils import get_text, safe_float, read_xml_or_p7m

def parse_sdi_xml(xml_path, targa_dict, neue_targas_set, fehler_log, shorten_description=True, client_vat_id=""):
    """
    Parst eine SDI XML- oder P7M-Datei und gibt eine Liste von Positionen (Dicts) zurück.
    Wendet robuste Vorzeichenlogik (Gutschriften, Rabatte, Bollo) und Targa-Extraktion an.
    """
    rechnungspositionen = []
    
    try:
        source = read_xml_or_p7m(xml_path)
        if source is None:
            msg = f"Fehler: Konnte XML nicht aus {xml_path} extrahieren."
            print(msg)
            fehler_log.append(msg)
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
        is_gutschrift = False
        
        if tipo_documento in ('TD04', 'TD08'):
            dokumenttyp = "Gutschrift" if tipo_documento == 'TD04' else "Gutschrift (vereinfacht)"
            is_gutschrift = True
        elif tipo_documento == 'TD05':
            dokumenttyp = "Belastungsanzeige"

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

        # Aktiv/Passiv ermitteln
        aktiv_passiv = ""
        if client_vat_id:
            if liefer_id == client_vat_id:
                aktiv_passiv = "Attiva"
            elif kunden_id == client_vat_id:
                aktiv_passiv = "Passiva"

        # --- DettaglioLinee (Rechnungszeilen) ---
        dati_linee = root.findall('.//DettaglioLinee')
        bollo_in_zeilen = False
        
        for linea in dati_linee:
            desc = get_text(linea, 'Descrizione', 'Keine Beschreibung')
            desc_short = desc.split(',', 1)[0].strip() if (',' in desc and shorten_description) else desc
            desc_norm = re.sub(r'\s+', ' ', desc_short).strip().upper()
            qty_text = get_text(linea, 'Quantita', '1.0')
            price_text = get_text(linea, 'PrezzoUnitario', '0.0')
            total_text = get_text(linea, 'PrezzoTotale', '0.0')
            iva_text = get_text(linea, 'AliquotaIVA', '0.0')
            
            # Rohwerte einlesen (PrezzoTotale enthält bereits eventuelle inline ScontoMaggiorazione)
            qty_raw = safe_float(qty_text, 1.0)
            price_raw = safe_float(price_text, 0.0)
            total_raw = safe_float(total_text, 0.0)
            iva = safe_float(iva_text, 0.0)
            
            if total_raw == 0.0:
                continue
                
            # --- Intelligente Vorzeichen-Logik ---
            desc_lower = desc.lower()
            tipo_cessione = get_text(linea, 'TipoCessionePrestazione', '')
            
            is_bollo = "bollo" in desc_lower or "stempel" in desc_lower or "marca da bollo" in desc_lower
            if is_bollo:
                bollo_in_zeilen = True
                
            is_rabatt = "sconto" in desc_lower or "rabatt" in desc_lower or tipo_cessione == 'SC'
            
            # Absolutwerte für die Bestimmung
            abs_total = abs(total_raw)
            
            if is_gutschrift:
                if is_bollo:
                    total = abs_total       # Bollo auf Gutschrift ist positiv
                    price = -abs(price_raw) # Einzelpreis negativ
                    qty = -abs(qty_raw)     # Menge negativ (-1 * -2 = +2)
                elif is_rabatt:
                    total = abs_total       # Rabatt-Storno auf Gutschrift ist positiv
                    price = abs(price_raw)
                    qty = abs(qty_raw)
                else:
                    total = -abs_total      # Normaler Artikel ist immer negativ
                    price = abs(price_raw)
                    qty = -abs(qty_raw)
            else: # TD01, TD02, TD05, etc.
                if is_rabatt:
                    total = -abs_total      # Rabatt ist auf Rechnungen immer negativ
                    price = abs(price_raw)
                    qty = -abs(qty_raw)
                elif is_bollo:
                    total = abs_total       # Bollo ist auf Rechnungen positiv
                    price = abs(price_raw)
                    qty = abs(qty_raw)
                else:
                    total = total_raw       # Standard-Verhalten
                    price = abs(price_raw)
                    qty = abs(qty_raw) if total > 0 else -abs(qty_raw)
            
            # --- Targa (Kennzeichen) ---
            targa_gefunden = ""
            fahrzeugtyp = ""
            altri_dati = linea.findall('.//AltriDatiGestionali')
            for dato in altri_dati:
                tipo = get_text(dato, 'TipoDato').upper()
                if 'TARGA' in tipo or 'TAR' in tipo:
                    targa_gefunden = get_text(dato, 'RiferimentoTesto')
                    break
            if not targa_gefunden and desc:
                # Fallback in der Beschreibung
                match = re.search(r'KZ/Baust\.:\s*([A-Z0-9\s]+?)\s*(?:-|$)', desc, re.IGNORECASE)
                if match:
                    targa_gefunden = match.group(1).strip()
            
            if targa_gefunden and targa_dict is not None and neue_targas_set is not None:
                targa_norm = targa_gefunden.strip().upper().replace(' ', '')
                fahrzeugtyp = targa_dict.get(targa_norm, "UNBEKANNT")
                if targa_norm not in targa_dict and targa_norm not in neue_targas_set:
                    neue_targas_set.add(targa_norm)

            abs_path = os.path.abspath(xml_path)
            dateiname = os.path.basename(xml_path)
            hyperlink_formel = f'=HYPERLINK("{abs_path}", "{dateiname}")'
            
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
                'Beschreibung_Full': desc, # Nützlich für Analyse
                'Desc_Norm': desc_norm,
                'CdC': targa_gefunden if targa_gefunden else "",
                'Kennzeichen': targa_gefunden,
                'Fahrzeugtyp': fahrzeugtyp,
                'Menge': qty,
                'Einzelpreis_Roh': price, 
                'Gesamtpreis_Roh': total, 
                'Waehrung': waehrung,
                'MwSt': iva / 100.0 if iva > 0 else 0.0,
                'Datei_Link': hyperlink_formel,
                'Dateiname': dateiname
            })
            
        # --- DatiBollo (Dubletten-Check) ---
        if not bollo_in_zeilen:
            importo_bollo_node = root.find('.//DatiGeneraliDocumento/DatiBollo/ImportoBollo')
            if importo_bollo_node is not None and importo_bollo_node.text:
                bollo_betrag_raw = safe_float(importo_bollo_node.text, 0.0)
                if bollo_betrag_raw > 0:
                    # Virtuelle Zeile anfügen
                    if is_gutschrift:
                        bollo_total = abs(bollo_betrag_raw)
                        bollo_qty = -1.0
                        bollo_price = -abs(bollo_betrag_raw)
                    else:
                        bollo_total = abs(bollo_betrag_raw)
                        bollo_qty = 1.0
                        bollo_price = abs(bollo_betrag_raw)
                    
                    abs_path = os.path.abspath(xml_path)
                    dateiname = os.path.basename(xml_path)
                    hyperlink_formel = f'=HYPERLINK("{abs_path}", "{dateiname}")'
                    
                    rechnungspositionen.append({
                        'Aktiv/Passiv': aktiv_passiv,
                        'Typ': dokumenttyp,
                        'Rechnungsnummer': rechnungs_nummer,
                        'Datum': rechnungs_datum,
                        'Lieferant': lieferant,
                        'Liefer ID': liefer_id,
                        'Kunde': kunde,
                        'Kunden ID': kunden_id,
                        'Beschreibung': "Marca da Bollo",
                        'Beschreibung_Full': "Marca da Bollo (aus DatiBollo)",
                        'Desc_Norm': "MARCA DA BOLLO",
                        'CdC': "",
                        'Kennzeichen': "",
                        'Fahrzeugtyp': "",
                        'Menge': bollo_qty,
                        'Einzelpreis_Roh': bollo_price,
                        'Gesamtpreis_Roh': bollo_total,
                        'Waehrung': waehrung,
                        'MwSt': 0.0,
                        'Datei_Link': hyperlink_formel,
                        'Dateiname': dateiname
                    })

    except Exception as e:
        error_msg = f"Fehler beim Parsen von {os.path.basename(xml_path)}: {e}"
        print(error_msg)
        print(traceback.format_exc())
        fehler_log.append(error_msg)
        
    return rechnungspositionen
