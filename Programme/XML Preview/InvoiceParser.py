import defusedxml.ElementTree as ET
import os

from asn1crypto import cms

def decrypt_p7m(file_path):
    with open(file_path, 'rb') as f:
        der_data = f.read()
    
    xml_bytes = None
    signature_info = None
    
    try:
        content_info = cms.ContentInfo.load(der_data)
        if content_info['content_type'].native == 'signed_data':
            signed_data = content_info['content']
            encap_content_info = signed_data['encap_content_info']
            if encap_content_info['content'].native:
                xml_bytes = encap_content_info['content'].native
            
            try:
                if signed_data['signer_infos']:
                    signer = signed_data['signer_infos'][0]
                    signing_time = None
                    if hasattr(signer, 'native') and 'signed_attrs' in signer.native:
                        for attr in signer.native['signed_attrs']:
                            if attr['type'] == 'signing_time':
                                signing_time = attr['values'][0]
                                if signing_time:
                                    signing_time = signing_time.strftime("%d/%m/%Y %H:%M:%S")
                    
                    if signed_data['certificates']:
                        cert = signed_data['certificates'][0].chosen['tbs_certificate']
                        def format_name(name_obj):
                            parts = []
                            if hasattr(name_obj, 'native') and isinstance(name_obj.native, dict):
                                for k, v in name_obj.native.items():
                                    if k == 'country_name': k = 'C'
                                    elif k == 'organization_name': k = 'O'
                                    elif k == 'title': k = 'T'
                                    elif k == 'surname': k = 'SURNAME'
                                    elif k == 'given_name': k = 'GIVENNAME'
                                    elif k == 'serial_number': k = 'SERIALNUMBER'
                                    elif k == 'common_name': k = 'CN'
                                    elif k == 'dn_qualifier': k = 'DN'
                                    elif k == 'organizational_unit_name': k = 'OU'
                                    parts.append(f"{k}={v}")
                            return parts
                            
                        subject_parts = format_name(cert['subject'])
                        issuer_parts = format_name(cert['issuer'])
                        
                        signature_info = {
                            'Stato della firma': 'Firma valida',
                            'Data di firma': signing_time if signing_time else 'Unbekannt',
                            'Soggetto': subject_parts,
                            'Certificato emesso da': issuer_parts
                        }
            except Exception as e:
                print("Fehler beim Extrahieren der Signatur-Details:", e)
    except Exception as e:
        print(f"Fehler bei P7M Entschlüsselung: {e}")
        
    if xml_bytes is not None:
        return xml_bytes, signature_info
        
    # Fallback mit Byte-Slicing
    try:
        start_tags = [b'<?xml', b'<p:FatturaElettronica', b'<FatturaElettronica', b'<ns2:FatturaElettronica', b'<ns3:FatturaElettronica']
        start = -1
        for tag in start_tags:
            start = der_data.find(tag)
            if start != -1:
                break
                
        if start != -1:
            end = der_data.rfind(b'>') + 1
            if end > start:
                return der_data[start:end], None
    except Exception as e:
        print(f"Fallback fehlgeschlagen: {e}")
        
    return None, None


def parse_invoice(file_path):
    invoice_data = {
        'filepath': file_path,
        'filename': os.path.basename(file_path),
        'mittente': {},
        'destinatario': {},
        'dati_generali': {},
        'linee': [],
        'riepilogo': [],
        'pagamenti': [],
        'allegati': []
    }
    
    try:
        if file_path.lower().endswith('.p7m'):
            xml_bytes, signature_info = decrypt_p7m(file_path)
            if xml_bytes is None:
                raise ValueError("Konnte XML nicht aus P7M extrahieren")
            invoice_data['signature_info'] = signature_info
            root = ET.fromstring(xml_bytes)
        else:
            invoice_data['signature_info'] = None
            tree = ET.parse(file_path)
            root = tree.getroot()
            
        # Namespace entfernen, um XPath-Suchen zu vereinfachen
        for elem in root.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]
                
        # Helper-Funktion
        def get_text(node, xpath, default=""):
            if node is None: return default
            child = node.find(xpath)
            val = child.text if child is not None and child.text else default
            if val and xpath in ('Data', 'RiferimentoData', 'DataScadenzaPagamento'):
                try:
                    if len(val) >= 10 and val[4] == '-' and val[7] == '-':
                        val = f"{val[8:10]}.{val[5:7]}.{val[0:4]}"
                except Exception:
                    pass
            return val

        # Mittente (CedentePrestatore)
        cedente_prest = root.find('.//CedentePrestatore')
        if cedente_prest is not None:
            ced_anag = cedente_prest.find('.//DatiAnagrafici/Anagrafica')
            if ced_anag is not None:
                denom = get_text(ced_anag, 'Denominazione')
                if not denom:
                    nome = get_text(ced_anag, 'Nome')
                    cognome = get_text(ced_anag, 'Cognome')
                    denom = f"{nome} {cognome}".strip()
                invoice_data['mittente']['Denominazione'] = denom
            
            invoice_data['mittente']['PartitaIVA'] = get_text(cedente_prest, './/DatiAnagrafici/IdFiscaleIVA/IdCodice')
            invoice_data['mittente']['CodiceFiscale'] = get_text(cedente_prest, './/DatiAnagrafici/CodiceFiscale')
            invoice_data['mittente']['RegimeFiscale'] = get_text(cedente_prest, './/DatiAnagrafici/RegimeFiscale')
            
            sede = cedente_prest.find('.//Sede')
            if sede is not None:
                invoice_data['mittente']['Indirizzo'] = get_text(sede, 'Indirizzo')
                invoice_data['mittente']['Comune'] = get_text(sede, 'Comune')
                invoice_data['mittente']['Provincia'] = get_text(sede, 'Provincia')
                invoice_data['mittente']['CAP'] = get_text(sede, 'CAP')
                invoice_data['mittente']['Nazione'] = get_text(sede, 'Nazione')
                
            contatti = cedente_prest.find('.//Contatti')
            if contatti is not None:
                invoice_data['mittente']['Telefono'] = get_text(contatti, 'Telefono')
                invoice_data['mittente']['Email'] = get_text(contatti, 'Email')
                
            invoice_data['mittente']['RiferimentoAmministrazione'] = get_text(cedente_prest, './/RiferimentoAmministrazione')

        # Terzo Intermediario
        terzo = root.find('.//TerzoIntermediarioOSoggettoEmittente')
        if terzo is not None:
            t_data = {}
            t_data['PartitaIVA'] = get_text(terzo, './/IdFiscaleIVA/IdCodice')
            t_anag = terzo.find('.//Anagrafica')
            if t_anag is not None:
                denom = get_text(t_anag, 'Denominazione')
                if not denom:
                    nome = get_text(t_anag, 'Nome')
                    cognome = get_text(t_anag, 'Cognome')
                    denom = f"{nome} {cognome}".strip()
                t_data['Denominazione'] = denom
            invoice_data['terzo_intermediario'] = t_data

        # Destinatario (CessionarioCommittente)
        cess_comm = root.find('.//CessionarioCommittente')
        if cess_comm is not None:
            cess_anag = cess_comm.find('.//DatiAnagrafici/Anagrafica')
            if cess_anag is not None:
                denom = get_text(cess_anag, 'Denominazione')
                if not denom:
                    nome = get_text(cess_anag, 'Nome')
                    cognome = get_text(cess_anag, 'Cognome')
                    denom = f"{nome} {cognome}".strip()
                invoice_data['destinatario']['Denominazione'] = denom
            
            invoice_data['destinatario']['PartitaIVA'] = get_text(cess_comm, './/DatiAnagrafici/IdFiscaleIVA/IdCodice')
            invoice_data['destinatario']['CodiceFiscale'] = get_text(cess_comm, './/DatiAnagrafici/CodiceFiscale')
            
            sede = cess_comm.find('.//Sede')
            if sede is not None:
                invoice_data['destinatario']['Indirizzo'] = get_text(sede, 'Indirizzo')
                invoice_data['destinatario']['Comune'] = get_text(sede, 'Comune')
                invoice_data['destinatario']['Provincia'] = get_text(sede, 'Provincia')
                invoice_data['destinatario']['CAP'] = get_text(sede, 'CAP')
                invoice_data['destinatario']['Nazione'] = get_text(sede, 'Nazione')
        
        # Dati Trasmissione (für PEC und Codice Destinatario)
        trasm = root.find('.//DatiTrasmissione')
        if trasm is not None:
            invoice_data['destinatario']['PECDestinatario'] = get_text(trasm, 'PECDestinatario')
            invoice_data['destinatario']['CodiceDestinatario'] = get_text(trasm, 'CodiceDestinatario')

        # Dati Generali
        dati_gen = root.find('.//DatiGeneraliDocumento')
        if dati_gen is not None:
            invoice_data['dati_generali']['TipoDocumento'] = get_text(dati_gen, 'TipoDocumento')
            invoice_data['dati_generali']['Data'] = get_text(dati_gen, 'Data')
            invoice_data['dati_generali']['Numero'] = get_text(dati_gen, 'Numero')
            invoice_data['dati_generali']['ImportoTotaleDocumento'] = get_text(dati_gen, 'ImportoTotaleDocumento')
            invoice_data['dati_generali']['Art73'] = get_text(dati_gen, 'Art73')
            
        # Dettaglio Linee
        for linea in root.findall('.//DettaglioLinee'):
            l = {
                'NumeroLinea': get_text(linea, 'NumeroLinea'),
                'CodiceArticolo': get_text(linea, './/CodiceArticolo/CodiceValore'),
                'Descrizione': get_text(linea, 'Descrizione'), # Volle Beschreibung
                'Quantita': get_text(linea, 'Quantita'),
                'UnitaMisura': get_text(linea, 'UnitaMisura'),
                'PrezzoUnitario': get_text(linea, 'PrezzoUnitario'),
                'ScontoMaggiorazione': get_text(linea, './/ScontoMaggiorazione/Importo'),
                'PrezzoTotale': get_text(linea, 'PrezzoTotale'),
                'AliquotaIVA': get_text(linea, 'AliquotaIVA'),
                'AltriDatiGestionali': []
            }
            
            for adg in linea.findall('.//AltriDatiGestionali'):
                dati = {
                    'TipoDato': get_text(adg, 'TipoDato'),
                    'RiferimentoTesto': get_text(adg, 'RiferimentoTesto'),
                    'RiferimentoNumero': get_text(adg, 'RiferimentoNumero'),
                    'RiferimentoData': get_text(adg, 'RiferimentoData')
                }
                l['AltriDatiGestionali'].append(dati)
                
            invoice_data['linee'].append(l)
            
        # Dati Riepilogo
        for riepilogo in root.findall('.//DatiRiepilogo'):
            r = {
                'AliquotaIVA': get_text(riepilogo, 'AliquotaIVA'),
                'Natura': get_text(riepilogo, 'Natura'),
                'SpeseAccessorie': get_text(riepilogo, 'SpeseAccessorie'),
                'ImponibileImporto': get_text(riepilogo, 'ImponibileImporto'),
                'Imposta': get_text(riepilogo, 'Imposta'),
                'EsigibilitaIVA': get_text(riepilogo, 'EsigibilitaIVA'),
                'RiferimentoNormativo': get_text(riepilogo, 'RiferimentoNormativo')
            }
            invoice_data['riepilogo'].append(r)
            
        # Dati Pagamento
        for pag in root.findall('.//DatiPagamento/DettaglioPagamento'):
            p = {
                'ModalitaPagamento': get_text(pag, 'ModalitaPagamento'),
                'DataScadenzaPagamento': get_text(pag, 'DataScadenzaPagamento'),
                'ImportoPagamento': get_text(pag, 'ImportoPagamento'),
                'IBAN': get_text(pag, 'IBAN'),
                'ABI': get_text(pag, 'ABI'),
                'CAB': get_text(pag, 'CAB'),
                'IstitutoFinanziario': get_text(pag, 'IstitutoFinanziario'),
                'CodicePagamento': get_text(pag, 'CodicePagamento'),
                'DataTerminePagamento': get_text(pag, 'DataTerminePagamento'),
                'GiorniTerminiPagamento': get_text(pag, 'GiorniTerminiPagamento')
            }
            invoice_data['pagamenti'].append(p)
            
        # Allegati
        for allegato in root.findall('.//Allegati'):
            a = {
                'NomeAttachment': get_text(allegato, 'NomeAttachment', 'Anhang'),
                'FormatoAttachment': get_text(allegato, 'FormatoAttachment'),
                'DescrizioneAttachment': get_text(allegato, 'DescrizioneAttachment'),
                'Attachment': get_text(allegato, 'Attachment')
            }
            if a['Attachment']: 
                invoice_data['allegati'].append(a)
            
        return invoice_data
        
    except Exception as e:
        import traceback
        print(f"Fehler beim Parsen von {os.path.basename(file_path)}: {e}")
        traceback.print_exc()
        return None
