import os
import json
import asyncio
from typing import Dict, List, Any

MAX_CONCURRENT_REQUESTS = 2
CONFIDENCE_THRESHOLD = 8
GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3-flash"
]
current_waterfall_idx = 0

cancel_requested = False
import sys
script_dir = os.path.dirname(os.path.abspath(__file__))
prog_dir = os.path.dirname(script_dir)
if prog_dir not in sys.path:
    sys.path.append(prog_dir)

try:
    from DatabaseManager import get_db
except ImportError:
    pass



def ensure_konten_template(nutzerdaten_dir: str):
    import shutil
    txt_path = os.path.join(nutzerdaten_dir, "KI_Kontenplan.txt")
    if not os.path.exists(txt_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        template_path = os.path.join(base_dir, "Systemdaten", "Templates", "Codice_Civile_2424.txt")
        if os.path.exists(template_path):
            try:
                shutil.copy2(template_path, txt_path)
            except Exception as e:
                print(f"Fehler beim Kopieren des KI-Kontenplan Templates: {e}")

def build_system_instruction(nutzerdaten_dir: str, is_stage2: bool = False) -> str:
    client_info = ""
    info_path = os.path.join(nutzerdaten_dir, "info.json")
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                desc = data.get('Beschreibung', '').strip()
                if desc:
                    client_info = f"Informationen zum Kundenunternehmen:\nBranche/Tätigkeit: {desc}\n\n"
        except Exception:
            pass

    kontenplan_text = "Kein Kontenplan hinterlegt."
    txt_path = os.path.join(nutzerdaten_dir, "KI_Kontenplan.txt")
    if os.path.exists(txt_path):
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                kontenplan_text = f.read()
        except Exception:
            pass
            
    instruction = "Du bist ein KI-Buchhalter für den italienischen SDI Standard.\n"
    instruction += "Deine Aufgabe ist es, Rechnungs-Artikel einem passenden FIBU-Konto zuzuordnen.\n\n"
    instruction += client_info
    instruction += "HINTERGRUND (Kontenplan):\n"
    instruction += kontenplan_text + "\n\n"
    
    instruction += "REGELN FÜR DIE AUSGABE:\n"
    instruction += "1. Du erhältst eine Liste von Artikeln im Format: ID: [id] | Eigenschaft: Wert | ...\n"
    instruction += "2. Bestimme für JEDEN Artikel das passendste Konto aus dem obigen Kontenplan.\n"
    instruction += "3. Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt. Keine Markdown-Blöcke, kein anderer Text.\n"
    instruction += "4. Die Schlüssel im JSON-Objekt sind die IDs der Artikel (als String).\n"
    
    if not is_stage2:
        instruction += "5. Der Wert muss ein JSON-Objekt sein mit 3 Schlüsseln: 'gedankengang' (Erklärung in 1 Satz), 'konfidenz' (Zahl von 1 bis 10), und 'konto' (exaktes Konto).\n"
        instruction += "6. Berücksichtige zwingend die Branche des Käufers und was beim Lieferanten gekauft wurde.\n"
        instruction += "BEISPIEL-ANTWORT:\n"
        instruction += "{\n  \"0\": {\n    \"gedankengang\": \"Käufer ist Metzger, Verkäufer ist Bäcker, Produkt ist Brot -> Wareneinkauf\",\n    \"konfidenz\": 9,\n    \"konto\": \"100 / 801006\"\n  }\n}"
    else:
        instruction += "5. Der Wert ist ausschließlich das exakte Konto (z.B. 100 / 801006) genau wie im Kontenplan gelistet als String.\n"
        instruction += "6. Du MUSST dich zwingend für ein Konto entscheiden. Lass den Wert NIEMALS leer, auch wenn du unsicher bist. Wähle das wahrscheinlichste.\n"
        instruction += "BEISPIEL-ANTWORT:\n"
        instruction += "{\n  \"0\": \"100 / 801006\",\n  \"1\": \"104 / 821249\"\n}"
    
    return instruction

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
            
            # Markdown JSON Stripping
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



async def process_batch_async(chunk, system_instruction_stage1, system_instruction_stage2, batch_num, total_batches, sem, results):
    global cancel_requested
    
    if cancel_requested:
        return False

    async with sem:
        if cancel_requested:
            return False
            
        print(f"-> Starte Batch {batch_num}/{total_batches} ({len(chunk)} Artikel) [Stufe 1]...")
        prompt_text = "Bitte klassifiziere folgende Artikel:\n"
        for local_idx, item in enumerate(chunk):
            prompt_text += f"ID: {local_idx} | "
            for k, v in item.items():
                if k not in ['id', 'cache_key'] and str(v).strip() != "":
                    prompt_text += f"{k}: {v} | "
            prompt_text += "\n"
            
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
                        global_id = chunk[local_idx]['id']
                        if isinstance(data, dict):
                            konfidenz = data.get("konfidenz", 0)
                            if konfidenz >= CONFIDENCE_THRESHOLD:
                                results[global_id] = data.get("konto", "")
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
                    prompt_text_2 += f"ID: {local_idx} | "
                    for k, v in item.items():
                        if k not in ['id', 'cache_key'] and str(v).strip() != "":
                            prompt_text_2 += f"{k}: {v} | "
                    prompt_text_2 += "\n"
                    
                response_json_2 = await call_gemini_api_with_retry(
                    None,  # Wird durch Wasserfall ueberschrieben
                    system_instruction_stage2,
                    prompt_text_2,
                    batch_num,
                    base_dir,
                    is_waterfall=True
                )
                
                if response_json_2:
                    for local_idx_str, konto in response_json_2.items():
                        if local_idx_str.isdigit():
                            local_idx = int(local_idx_str)
                            if 0 <= local_idx < len(chunk):
                                global_id = chunk[local_idx]['id']
                                # In Stufe 2 ist das Resultat direkt das Konto, kein Dict
                                results[global_id] = konto
                                
            print(f"<- Batch {batch_num} vollstaendig abgeschlossen.")
            return True
            
        except Exception as e:
            print(f"Fehler in Batch {batch_num}: {e}")
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
        supplier = item.get('Lieferant', 'Unbekannt')
        desc = item.get('Beschreibung', '')
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
        
    system_instruction_stage1 = build_system_instruction(nutzerdaten_dir, is_stage2=False)
    system_instruction_stage2 = build_system_instruction(nutzerdaten_dir, is_stage2=True)
    
    chunk_size = 25
    total_items = len(items_for_api)
    results = {}
    
    print(f"\nSende {total_items} neue Positionen asynchron an die KI zur Kontierung...")
    
    chunks = [items_for_api[i:i + chunk_size] for i in range(0, total_items, chunk_size)]
    sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    tasks = []
    for i, chunk in enumerate(chunks):
        task = process_batch_async(chunk, system_instruction_stage1, system_instruction_stage2, i + 1, len(chunks), sem, results)
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
