import os
import json
import time
import asyncio
from typing import List, Dict, Any

MAX_CONCURRENT_REQUESTS = 3

SYSTEM_INSTRUCTION = """
Du bist ein hochpräziser Datenextraktions-Assistent für italienische Rechnungen (Fattura).
Analysiere das PDF der Rechnung und extrahiere die Daten in einem strikten JSON-Format.

Erwartetes JSON-Format: Ein Array von JSON-Objekten (da eine Rechnung meist mehrere Rechnungspositionen/Artikel enthält). 
Für jeden Artikel auf der Rechnung erstellst du ein separates Objekt im Array. Die Header-Daten (Lieferant, Datum etc.) müssen in JEDEM Objekt des Arrays wiederholt werden.

Beispiel:
[
  {
    "Typ": "Rechnung", 
    "Rechnungsnummer": "123/A",
    "Datum": "YYYY-MM-DD",
    "Waehrung": "EUR",
    "Lieferant": "Max Mustermann Srl",
    "Liefer ID": "IT01234567890",
    "Kunde": "Kundenname GmbH",
    "Kunden ID": "IT09876543210",
    "Beschreibung": "Artikel 1 Beschreibung",
    "Menge": 1.0,
    "Einzelpreis": 10.50,
    "MwSt_Satz": 22.0,
    "Kennzeichen": "" 
  }
]

Wichtige Regeln:
1. "Typ": "Rechnung" oder "Gutschrift" (Nota di credito).
2. "Liefer ID" / "Kunden ID": Suche nach 'Partita IVA', 'P.IVA' oder 'Codice Fiscale' (CF). Nur die alphanumerische ID extrahieren (ohne Leerzeichen).
3. "Kennzeichen": Wenn in der Artikelbeschreibung ein Fahrzeugkennzeichen (Targa, Targa: AB123CD, KZ: ...) steht, dieses extrahieren (ohne Leerzeichen).
4. Zahlen als reine Floats (Punkt statt Komma, keine Tausendertrennzeichen).
5. Gib AUSSCHLIESSLICH das reine JSON-Array zurück. Keine Markdown-Blöcke (kein ```json).
"""

async def process_pdf_async(client, pdf_path: str, sem: asyncio.Semaphore) -> List[Dict[str, Any]]:
    async with sem:
        print(f"Lade PDF hoch: {os.path.basename(pdf_path)}...")
        uploaded_file = None
        try:
            uploaded_file = await asyncio.to_thread(client.files.upload, file=pdf_path)
            
            while uploaded_file.state.name == "PROCESSING":
                print(f"Warte auf Verarbeitung von {os.path.basename(pdf_path)}...")
                await asyncio.sleep(2)
                uploaded_file = await asyncio.to_thread(client.files.get, name=uploaded_file.name)
                
            if uploaded_file.state.name == "FAILED":
                print(f"Fehler: PDF-Upload fehlgeschlagen für {pdf_path}")
                return []
                
            print(f"Analysiere PDF: {os.path.basename(pdf_path)}...")
            response = await client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    uploaded_file,
                    SYSTEM_INSTRUCTION
                ],
                config={"temperature": 0.1}
            )
            
            text = response.text.strip()
            if text.startswith("```json"):
                text = text.replace("```json", "", 1).strip()
            if text.endswith("```"):
                text = text.replace("```", "").strip()
                
            return json.loads(text)
            
        except Exception as e:
            print(f"Fehler bei PDF {os.path.basename(pdf_path)}: {e}")
            return []
        finally:
            if uploaded_file:
                try:
                    await asyncio.to_thread(client.files.delete, name=uploaded_file.name)
                except Exception as e:
                    print(f"Fehler beim Löschen des temporären PDF-Uploads {uploaded_file.name}: {e}")

async def async_parse_pdfs(pdf_paths: List[str], api_key: str) -> Dict[str, List[Dict[str, Any]]]:
    if not pdf_paths:
        return {}
        
    try:
        from google import genai
    except ImportError:
        print("google-genai ist nicht installiert.")
        return {}
        
    client = genai.Client(api_key=api_key)
    sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    tasks = []
    for path in pdf_paths:
        tasks.append(process_pdf_async(client, path, sem))
        
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    parsed_data = {}
    for path, res in zip(pdf_paths, results):
        if isinstance(res, list):
            parsed_data[path] = res
        else:
            print(f"Fehler bei {path}: {res}")
            parsed_data[path] = []
            
    return parsed_data

def parse_pdfs(pdf_paths: List[str], api_key: str) -> Dict[str, List[Dict[str, Any]]]:
    return asyncio.run(async_parse_pdfs(pdf_paths, api_key))
