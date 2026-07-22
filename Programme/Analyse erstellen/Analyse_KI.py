import os
import json

import asyncio


MAX_CONCURRENT_REQUESTS = 3

def get_memory_path(nutzerdaten_dir):
    return os.path.join(nutzerdaten_dir, "Analyse_Memory.json")

import sys
script_dir = os.path.dirname(os.path.abspath(__file__))
prog_dir = os.path.dirname(script_dir)
if prog_dir not in sys.path:
    sys.path.append(prog_dir)

try:
    from DatabaseManager import get_db
except ImportError:
    pass

def get_api_key(base_dir):
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

async def process_batch_async(client, chunk, system_instruction, current_model, batch_num, total_batches, sem, memory, results, new_entries):
    async with sem:
        print(f"-> Starte Batch {batch_num}/{total_batches} ({len(chunk)} Artikel)...")
        prompt_text = "Bitte klassifiziere folgende Artikel:\n"
        for local_idx, item in enumerate(chunk):
            supplier = item.get('supplier') or item.get('Lieferant', 'Unbekannt')
            desc = item.get('desc') or item.get('Beschreibung', '')
            prompt_text += f"[{local_idx}] {supplier} | {desc}\n"
            
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
                
                new_entries_found = False
                for local_idx_str, kategorien_dict in batch_result.items():
                    if local_idx_str.isdigit():
                        local_idx = int(local_idx_str)
                        if 0 <= local_idx < len(chunk):
                            item = chunk[local_idx]
                            results[item['id']] = kategorien_dict
                            new_entries[item['cache_key']] = kategorien_dict
                            new_entries_found = True
                
                if new_entries_found:
                    print(f"<- Batch {batch_num} erfolgreich abgeschlossen.")
                return new_entries_found
                            
            except json.JSONDecodeError:
                print(f"Fehler beim Parsen der Gemini-Antwort (kein gültiges JSON) in Batch {batch_num}.")
                return False
                
        except Exception as e:
            print(f"Fehler bei der API Anfrage in Batch {batch_num}: {e}")
            return False

async def async_analyze_items_with_ai(items_to_classify, api_key, nutzerdaten_dir, system_instruction):
    if not items_to_classify:
        return {}
        
    kunden_id = os.path.basename(os.path.dirname(nutzerdaten_dir))
    db = get_db()
    memory = db.get_analyse_cache(kunden_id)
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
        return results

    client = genai.Client(api_key=api_key)
    
    # 2. Batch Processing
    chunk_size = 100
    current_model = 'gemini-3.5-flash'
    total_items = len(items_for_api)
    
    print(f"\nSende {total_items} neue Positionen asynchron an die KI zur Analyse...")
    
    chunks = [items_for_api[i:i + chunk_size] for i in range(0, total_items, chunk_size)]
    sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    tasks = []
    for i, chunk in enumerate(chunks):
        task = process_batch_async(client, chunk, system_instruction, current_model, i + 1, len(chunks), sem, memory, results, new_entries)
        tasks.append(task)
        
    # Execute all batches concurrently
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    new_memory_entries = any(res is True for res in batch_results if not isinstance(res, Exception))
    
    # 3. Cache Speichern
    if new_entries:
        db.save_analyse_cache_batch(kunden_id, new_entries)
        print("SQL Cache (Analyse) wurde aktualisiert.")
        
    return results

def analyze_items_with_ai(items_to_classify, api_key, nutzerdaten_dir, system_instruction):
    """
    Klassifiziert eine Liste von Items synchron durch asyncio wrapper.
    """
    return asyncio.run(async_analyze_items_with_ai(items_to_classify, api_key, nutzerdaten_dir, system_instruction))
