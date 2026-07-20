import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

def generate_invoice_pdf(invoice_data, output_path):
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    normal_style = styles['Normal']
    bold_style = ParagraphStyle('Bold', parent=normal_style, fontName='Helvetica-Bold')
    
    elements = []
    
    # Header
    gen = invoice_data.get('dati_generali', {})
    tipo = gen.get('TipoDocumento', 'Rechnung')
    num = gen.get('Numero', '')
    data = gen.get('Data', '')
    divisa = gen.get('Divisa', 'EUR')
    
    elements.append(Paragraph(f"{tipo} Nr. {num} vom {data}", title_style))
    
    causale = gen.get('Causale')
    if causale:
        elements.append(Paragraph(f"<b>Causale:</b> {causale}", normal_style))
    
    elements.append(Spacer(1, 0.5*cm))
    
    # Addresses
    mit = invoice_data.get('mittente', {})
    dest = invoice_data.get('destinatario', {})
    
    def format_address(person):
        lines = []
        den = person.get('Denominazione', '')
        if den: lines.append(f"<b>{den}</b>")
        
        ind = person.get('Indirizzo', '')
        if ind: lines.append(ind)
        
        cap = person.get('CAP', '')
        comune = person.get('Comune', '')
        prov = person.get('Provincia', '')
        loc = f"{cap} {comune}"
        if prov: loc += f" ({prov})"
        if loc.strip(): lines.append(loc.strip())
        
        piva = person.get('PartitaIVA', '')
        if piva: lines.append(f"MwSt-Nr.: {piva}")
        
        cf = person.get('CodiceFiscale', '')
        if cf: lines.append(f"CF: {cf}")
        
        regime = person.get('RegimeFiscale', '')
        if regime: lines.append(f"Regime Fiscale: {regime}")
        
        return "<br/>".join(lines)
        
    address_data = [
        [Paragraph('<b>Absender (Cedente)</b>', normal_style), Paragraph('<b>Empfänger (Cessionario)</b>', normal_style)],
        [Paragraph(format_address(mit), normal_style), Paragraph(format_address(dest), normal_style)]
    ]
    
    addr_table = Table(address_data, colWidths=[8.5*cm, 8.5*cm])
    addr_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (1,0), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    
    elements.append(addr_table)
    elements.append(Spacer(1, 1*cm))
    
    # Line Items
    elements.append(Paragraph('<b>Rechnungspositionen (Dettaglio Linee)</b>', bold_style))
    elements.append(Spacer(1, 0.3*cm))
    
    line_data = [['#', 'Beschreibung', 'Menge', 'EP', 'Gesamt', 'MwSt']]
    for l in invoice_data.get('linee', []):
        line_data.append([
            l.get('NumeroLinea', ''),
            Paragraph(l.get('Descrizione', ''), normal_style),
            l.get('Quantita', ''),
            l.get('PrezzoUnitario', ''),
            l.get('PrezzoTotale', ''),
            l.get('AliquotaIVA', '') + '%'
        ])
        
    line_table = Table(line_data, colWidths=[1*cm, 7*cm, 2*cm, 2.5*cm, 2.5*cm, 2*cm])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#004488')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('ALIGN', (2,1), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    
    elements.append(line_table)
    elements.append(Spacer(1, 1*cm))
    
    # Riepilogo
    elements.append(Paragraph('<b>MwSt-Zusammenfassung (Dati Riepilogo)</b>', bold_style))
    elements.append(Spacer(1, 0.3*cm))
    
    riep_data = [['MwSt %', 'Steuergrundlage', 'Steuer', 'Art (Natura)', 'Esigibilita']]
    for r in invoice_data.get('riepilogo', []):
        riep_data.append([
            r.get('AliquotaIVA', '') + '%',
            r.get('ImponibileImporto', ''),
            r.get('Imposta', ''),
            r.get('Natura', ''),
            r.get('EsigibilitaIVA', '')
        ])
        
    riep_table = Table(riep_data, colWidths=[2.5*cm, 4*cm, 3*cm, 2.5*cm, 2.5*cm])
    riep_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    
    elements.append(riep_table)
    elements.append(Spacer(1, 1*cm))
    
    # Pagamenti
    pagamenti = invoice_data.get('pagamenti', [])
    if pagamenti:
        elements.append(Paragraph('<b>Zahlungsdaten (Dati Pagamento)</b>', bold_style))
        elements.append(Spacer(1, 0.3*cm))
        
        pag_data = [['Zahlungsart', 'Fälligkeit', 'Betrag', 'IBAN']]
        for p in pagamenti:
            pag_data.append([
                Paragraph(p.get('ModalitaPagamento', ''), normal_style),
                p.get('DataScadenzaPagamento', ''),
                p.get('ImportoPagamento', ''),
                Paragraph(p.get('IBAN', ''), normal_style)
            ])
            
        pag_table = Table(pag_data, colWidths=[4*cm, 3*cm, 3*cm, 7*cm])
        pag_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        
        elements.append(pag_table)
        elements.append(Spacer(1, 1*cm))
    
    # Total
    total = gen.get('ImportoTotaleDocumento', '')
    if total:
        elements.append(Paragraph(f"<b>Gesamtbetrag Dokument: {total} {divisa}</b>", styles['Heading3']))
    
    doc.build(elements)
