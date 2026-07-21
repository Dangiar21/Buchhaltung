import os
import json
import time

def get_memory_path(nutzerdaten_dir):
    return os.path.join(nutzerdaten_dir, "Analyse_Memory.json")

def load_memory(nutzerdaten_dir):
    path = get_memory_path(nutzerdaten_dir)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Fehler beim Laden von Analyse_Memory.json: {e}")
    return {}

def save_memory(nutzerdaten_dir, memory):
    path = get_memory_path(nutzerdaten_dir)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Fehler beim Speichern von Analyse_Memory.json: {e}")

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

def analyze_items_with_ai(items_to_classify, api_key, nutzerdaten_dir, system_instruction):
    """
    Klassifiziert eine Liste von Items: [{'id': 'unique_id', 'desc': '...', 'supplier': '...'}, ...]
    Gibt ein Dict zurück: {'unique_id': {'Kategorie1': 'Wert1', 'Kategorie2': 'Wert2'}, ...}
    Nutzt den lokalen Cache, um API Calls zu minimieren.
    """
    if not items_to_classify:
        return {}
        
    memory = load_memory(nutzerdaten_dir)
    results = {}
    items_for_api = []
    
    # 1. Cache Check
    for item in items_to_classify:
        supplier = item.get('supplier') or item.get('Lieferant', 'Unbekannt')
        desc = item.get('desc') or item.get('Beschreibung', '')
        # Key: "Lieferant | Beschreibung"
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
        from google.genai import types
    except ImportError:
        print("google-genai ist nicht installiert.")
        return results

    client = genai.Client(api_key=api_key)
    
    # 2. Batch Processing
    chunk_size = 15
    current_model = 'gemini-3.5-flash'
    total_items = len(items_for_api)
    new_memory_entries = False
    
    print(f"\nSende {total_items} neue Positionen an die KI zur Analyse...")
    
    for i in range(0, total_items, chunk_size):
        chunk = items_for_api[i:i+chunk_size]
        
        prompt_text = "Bitte klassifiziere folgende Artikel:\n"
        for local_idx, item in enumerate(chunk):
            supplier = item.get('supplier') or item.get('Lieferant', 'Unbekannt')
            desc = item.get('desc') or item.get('Beschreibung', '')
            prompt_text += f"[{local_idx}] {supplier} | {desc}\n"
            
        print(f"-> Batch {i//chunk_size + 1}/{(total_items-1)//chunk_size + 1} ({len(chunk)} Artikel)...")
        
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.1
            )
            
            try:
                response = client.models.generate_content(
                    model=current_model,
                    contents=prompt_text,
                    config=config
                )
            except Exception as e:
                error_msg = str(e)
                if any(err in error_msg for err in ["429", "RESOURCE_EXHAUSTED", "Quota exceeded", "503", "UNAVAILABLE"]):
                    if current_model == 'gemini-3.5-flash':
                        print(f"\nLimit für {current_model} erreicht. Wechsle zu gemini-3.1-flash-lite...")
                        current_model = 'gemini-3.1-flash-lite'
                        response = client.models.generate_content(
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
                
                for local_idx_str, kategorien_dict in batch_result.items():
                    if local_idx_str.isdigit():
                        local_idx = int(local_idx_str)
                        if 0 <= local_idx < len(chunk):
                            item = chunk[local_idx]
                            results[item['id']] = kategorien_dict
                            memory[item['cache_key']] = kategorien_dict
                            new_memory_entries = True
                            
            except json.JSONDecodeError:
                print("Fehler beim Parsen der Gemini-Antwort (kein gültiges JSON).")
                print("Antwort:", response.text)
                
            # Rate Limiting Pause
            if i + chunk_size < total_items:
                time.sleep(3.0)
                
        except Exception as e:
            print(f"Fehler bei der API Anfrage: {e}")
            
    # 3. Cache Speichern
    if new_memory_entries:
        save_memory(nutzerdaten_dir, memory)
        print("Analyse_Memory.json wurde aktualisiert.")
        
    return results
