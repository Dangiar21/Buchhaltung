import os
import json
import time
import asyncio
import shutil
from typing import Dict, List, Any

MAX_CONCURRENT_REQUESTS = 3

import sys
script_dir = os.path.dirname(os.path.abspath(__file__))
prog_dir = os.path.dirname(script_dir)
if prog_dir not in sys.path:
    sys.path.append(prog_dir)

try:
    from DatabaseManager import get_db
except ImportError:
    pass

def get_api_key(base_dir: str) -> str:
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(base_dir, "Systemdaten", "gemini_key.env")
        load_dotenv(dotenv_path=env_path)
    except Exception:
        pass

    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key

    key_path = os.path.join(base_dir, "Systemdaten", "gemini_api_key.txt")
    if os.path.exists(key_path):
        with open(key_path, "r", encoding="utf-8") as f:
            key = f.read().strip()
            if key:
                return key
    return None

def build_system_instruction(nutzerdaten_dir: str) -> str:
    konten = []
    client_rules_path = os.path.join(nutzerdaten_dir, "Kunden_KontenRegeln.xlsx")
    if os.path.exists(client_rules_path):
        import pandas as pd
        try:
            df = pd.read_excel(client_rules_path, sheet_name='Kontenplan')
            for _, row in df.iterrows():
                if pd.notna(row.get('Konto-Nummer')):
                    konten.append({
                        "Konto": str(row['Konto-Nummer']).replace('.0', ''),
                        "Bezeichnung": str(row.get('Bezeichnung', '')),
                        "Beschreibung": ""
                    })
        except Exception as e:
            print("Fehler beim Lesen des Kontenplans:", e)

    instruction = "Du bist ein KI-Buchhalter für den italienischen SDI Standard (XML/P7M).\n"
    instruction += "Deine Aufgabe ist es, Rechnungs-Artikel einem passenden FIBU-Konto zuzuordnen.\n\n"
    
    instruction += "HINTERGRUND (Kontenplan):\n"
    for k in konten:
        instruction += f"- Konto {k['Konto']}: {k['Bezeichnung']} ({k['Beschreibung']})\n"
        
    instruction += "\nREGELN FÜR DIE AUSGABE:\n"
    instruction += "1. Du erhältst eine Liste von Artikeln im Format: ID | Lieferant | Beschreibung\n"
    instruction += "2. Bestimme für JEDEN Artikel das passendste Konto (ausschließlich die Kontonummer als String).\n"
    instruction += "3. Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt. Keine Markdown-Blöcke, kein anderer Text.\n"
    instruction += "4. Die Schlüssel im JSON-Objekt sind die IDs der Artikel (als String).\n"
    instruction += "5. Wenn du unsicher bist, wähle das Konto 'Sonstiges' (falls vorhanden) oder lass den Wert leer ('').\n\n"
    
    instruction += "BEISPIEL-ANTWORT:\n"
    instruction += "{\n  \"0\": \"3200\",\n  \"1\": \"3250\",\n  \"2\": \"\"\n}"
    
    return instruction

async def process_batch_async(client, chunk, system_instruction, current_model, batch_num, total_batches, sem, results):
    async with sem:
        print(f"-> Starte Batch {batch_num}/{total_batches} ({len(chunk)} Artikel)...")
        prompt_text = "Bitte klassifiziere folgende Artikel:\n"
        for local_idx, item in enumerate(chunk):
            prompt_text += f"ID: {local_idx} | Lieferant: {item['supplier']} | Beschreibung: {item['desc']}\n"
            
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=8192
            )
            
            try:
                response = await client.aio.models.generate_content(
                    model=current_model,
                    contents=prompt_text,
                    config=config
                )
            except Exception as e:
                error_msg = str(e)
                if any(err in error_msg for err in ["429", "RESOURCE_EXHAUSTED", "Quota exceeded", "503", "UNAVAILABLE"]):
                    if current_model == 'gemini-3.5-flash':
                        print(f"\nLimit für {current_model} erreicht. Wechsle für Batch {batch_num} zu gemini-3.1-flash-lite...")
                        current_model = 'gemini-3.1-flash-lite'
                        response = await client.aio.models.generate_content(
                            model=current_model,
                            contents=prompt_text,
                            config=config
                        )
                    else:
                        raise e
                else:
                    raise e
            
            # Reparatur für abgeschnittene JSON-Antworten
            try:
                json_text = response.text.strip()
                if not json_text.endswith("}"):
                    json_text += "\n}"
                    
                batch_result = json.loads(json_text)
                
                for local_idx_str, konto in batch_result.items():
                    if local_idx_str.isdigit():
                        local_idx = int(local_idx_str)
                        if 0 <= local_idx < len(chunk):
                            global_id = chunk[local_idx]['id']
                            results[global_id] = konto
                
                print(f"<- Batch {batch_num} erfolgreich abgeschlossen.")
                return True
                            
            except json.JSONDecodeError:
                print(f"Fehler beim Parsen der Gemini-Antwort (kein gültiges JSON) in Batch {batch_num}.")
                return False
                
        except Exception as e:
            print(f"Fehler bei der API Anfrage in Batch {batch_num}: {e}")
            return False

async def async_classify_items_with_ai(items_to_classify: List[Dict[str, Any]], api_key: str, nutzerdaten_dir: str) -> Dict[str, str]:
    if not items_to_classify:
        return {}
        
    kunden_id = os.path.basename(os.path.dirname(nutzerdaten_dir))
    db = get_db()
    memory = db.get_konten_cache(kunden_id)
    new_entries = {}
    
    results = {}
    items_for_api = []
    
    # 1. Cache Check
    for item in items_to_classify:
        supplier = item.get('supplier') or item.get('Lieferant', 'Unbekannt')
        desc = item.get('desc') or item.get('Beschreibung', '')
        cache_key = f"{supplier} | {desc}".strip().upper()
        
        if cache_key in memory:
            results[item['id']] = memory[cache_key]
        else:
            item['cache_key'] = cache_key
            items_for_api.append(item)
            
    if not items_for_api:
        print(f"Alle {len(items_to_classify)} Positionen waren bereits im Cache!")
        return results
        
    if not api_key:
        print("Kein API Key gefunden! Es wurden nur Cache-Ergebnisse verwendet.")
        return results
        
    try:
        from google import genai
    except ImportError:
        print("google-genai ist nicht installiert.")
        return {}
        
    client = genai.Client(api_key=api_key)
    system_instruction = build_system_instruction(nutzerdaten_dir)
    
    chunk_size = 100
    current_model = 'gemini-3.5-flash'
    total_items = len(items_for_api)
    results = {}
    
    print(f"\nSende {total_items} neue Positionen asynchron an die KI zur Kontierung...")
    
    chunks = [items_for_api[i:i + chunk_size] for i in range(0, total_items, chunk_size)]
    sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    tasks = []
    for i, chunk in enumerate(chunks):
        task = process_batch_async(client, chunk, system_instruction, current_model, i + 1, len(chunks), sem, results)
        tasks.append(task)
        
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Track new entries for DB
    for item in items_for_api:
        if item['id'] in results:
            new_entries[item['cache_key']] = results[item['id']]
            
    # Save cache
    if new_entries:
        db.save_konten_cache_batch(kunden_id, new_entries)
        print("SQL Cache (Konten) wurde aktualisiert.")
    
    return results

def ask_gemini_batch(items_to_classify: List[Dict[str, Any]], api_key: str, nutzerdaten_dir: str) -> Dict[str, str]:
    """
    Synchronous wrapper for the async AI classification function (Legacy Alias).
    """
    return asyncio.run(async_classify_items_with_ai(items_to_classify, api_key, nutzerdaten_dir))
