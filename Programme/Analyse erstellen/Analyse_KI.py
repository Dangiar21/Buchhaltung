import os
import json
import asyncio

MAX_CONCURRENT_REQUESTS = 2
CONFIDENCE_THRESHOLD = 8
GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3-flash"
]
current_waterfall_idx = 0

cancel_requested = False

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



def get_api_key(base_dir: str) -> str:
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(base_dir, "Systemdaten", "gemini_key.env")
        load_dotenv(dotenv_path=env_path)
    except Exception:
        pass
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        key_path = os.path.join(base_dir, "Systemdaten", "gemini_api_key.txt")
        if os.path.exists(key_path):
            with open(key_path, "r", encoding="utf-8") as f:
                key = f.read().strip()
    return key

async def call_gemini_api_with_retry(model_name, system_instruction, prompt_text, batch_num, base_dir, is_waterfall=False):
    import asyncio
    import json
    import re
    global current_waterfall_idx
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("   -> FEHLER: google-genai Bibliothek fehlt!")
        return None
    gemini_key = get_api_key(base_dir)
    if not gemini_key:
        print("   -> FEHLER: Gemini Key fehlt! Bitte trage ihn ein.")
        return None
    
    client = genai.Client(api_key=gemini_key)
    max_retries = 15
    
    for attempt in range(max_retries):
        current_model = GEMINI_MODELS[current_waterfall_idx] if is_waterfall else model_name
        try:
            def _call():
                return client.models.generate_content(
                    model=current_model,
                    contents=prompt_text,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
            response = await asyncio.to_thread(_call)
            
            raw_text = response.text
            raw_text = re.sub(r"^```json\s*", "", raw_text, flags=re.IGNORECASE)
            raw_text = re.sub(r"```\s*$", "", raw_text)
            
            return json.loads(raw_text.strip())
        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "quota" in error_msg or "resourceexhausted" in error_msg:
                if "per minute" in error_msg:
                    print(f"   [RPM Limit] {current_model} hat das Minuten-Limit erreicht. Warte 30s...")
                    await asyncio.sleep(30)
                    continue
                elif "per day" in error_msg or "quota exceeded" in error_msg:
                    if is_waterfall:
                        print(f"   [PPD Limit] {current_model} ist fuer heute ausgeschoepft! Wechsle Modell...")
                        if current_waterfall_idx < len(GEMINI_MODELS) - 1:
                            current_waterfall_idx += 1
                        else:
                            print("   ALLE Wasserfall-Modelle sind ausgeschoepft! Warte 60s...")
                            await asyncio.sleep(60)
                        continue
                    else:
                        print(f"   [PPD Limit] {current_model} (Stufe 1) ist ausgeschoepft! Warte 60s...")
                        await asyncio.sleep(60)
                        continue
            
            print(f"   API-Fehler Gemini in Batch {batch_num} ({current_model}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5)
            else:
                return None
    return None




async def process_batch_async(chunk, system_instruction_stage1, system_instruction_stage2, batch_num, total_batches, sem, memory, results, new_entries):
    global cancel_requested
    
    if cancel_requested:
        return False

    async with sem:
        if cancel_requested:
            return False
            
        print(f"-> Starte Batch {batch_num}/{total_batches} ({len(chunk)} Artikel) [Stufe 1]...")
        prompt_text = "Bitte klassifiziere folgende Artikel:\n"
        for local_idx, item in enumerate(chunk):
            supplier = item.get('supplier') or item.get('Lieferant', 'Unbekannt')
            desc = item.get('desc') or item.get('Beschreibung', '')
            prompt_text += f"[{local_idx}] {supplier} | {desc}\n"
            
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            # STUFE 1: Lite Modell
            response_json = await call_gemini_api_with_retry(
                "gemini-3.5-flash-lite", 
                system_instruction_stage1, 
                prompt_text, 
                batch_num, 
                base_dir,
                is_waterfall=False
            )
            
            if not response_json:
                return False
                
            unsichere_faelle = []
            geloest = 0
            
            for local_idx_str, data in response_json.items():
                if local_idx_str.isdigit():
                    local_idx = int(local_idx_str)
                    if 0 <= local_idx < len(chunk):
                        item = chunk[local_idx]
                        if isinstance(data, dict):
                            konfidenz = data.get("konfidenz", 0)
                            if konfidenz >= CONFIDENCE_THRESHOLD:
                                kategorien_dict = data.get("konto", {}) # Konto ist in Analyse_KI ein Dict
                                results[item['id']] = kategorien_dict
                                new_entries[item['cache_key']] = kategorien_dict
                                geloest += 1
                            else:
                                unsichere_faelle.append(local_idx)
                        else:
                            unsichere_faelle.append(local_idx)
                            
            print(f"   Stufe 1 Batch {batch_num}: {geloest}/{len(chunk)} geloest. {len(unsichere_faelle)} gehen an Stufe 2.")
            
            # STUFE 2: Wasserfall für schwere Fälle
            if unsichere_faelle and not cancel_requested:
                print(f"   Batch {batch_num}: Starte Stufe 2 Wasserfall fuer {len(unsichere_faelle)} Artikel...")
                prompt_text_2 = "Bitte analysiere folgende schwierige Faelle:\n"
                for local_idx in unsichere_faelle:
                    item = chunk[local_idx]
                    supplier = item.get('supplier') or item.get('Lieferant', 'Unbekannt')
                    desc = item.get('desc') or item.get('Beschreibung', '')
                    prompt_text_2 += f"[{local_idx}] {supplier} | {desc}\n"
                    
                response_json_2 = await call_gemini_api_with_retry(
                    None,
                    system_instruction_stage2,
                    prompt_text_2,
                    batch_num,
                    base_dir,
                    is_waterfall=True
                )
                
                if response_json_2:
                    for local_idx_str, kategorien_dict in response_json_2.items():
                        if local_idx_str.isdigit():
                            local_idx = int(local_idx_str)
                            if 0 <= local_idx < len(chunk):
                                item = chunk[local_idx]
                                results[item['id']] = kategorien_dict
                                new_entries[item['cache_key']] = kategorien_dict
                                
            print(f"<- Batch {batch_num} vollstaendig abgeschlossen.")
            return True
            
        except Exception as e:
            print(f"Fehler in Batch {batch_num}: {e}")
            return False

async def async_analyze_items_with_ai(items_to_classify, api_key, nutzerdaten_dir, system_instruction=None):
    from Analyse_Config import load_setup, build_system_instruction
    kategorien = load_setup(nutzerdaten_dir)
    system_instruction_stage1 = build_system_instruction(kategorien, is_stage2=False)
    system_instruction_stage2 = build_system_instruction(kategorien, is_stage2=True)
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
        
    # 2. Batch Processing
    chunk_size = 25
    total_items = len(items_for_api)
    
    print(f"\nSende {total_items} neue Positionen asynchron an die KI zur Analyse...")
    
    chunks = [items_for_api[i:i + chunk_size] for i in range(0, total_items, chunk_size)]
    sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    tasks = []
    for i, chunk in enumerate(chunks):
        task = process_batch_async(chunk, system_instruction_stage1, system_instruction_stage2, i + 1, len(chunks), sem, memory, results, new_entries)
        tasks.append(task)
        
    # Execute all batches concurrently
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
    
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
