import os
import json
import asyncio
from typing import Dict, List, Any
from difflib import SequenceMatcher
import re
from utils import is_similar_desc, is_generic_auxiliary

MAX_CONCURRENT_REQUESTS = 2
CONFIDENCE_THRESHOLD = 8
GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash"
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
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for typ in ["ER", "AR"]:
        txt_path = os.path.join(nutzerdaten_dir, f"{typ}_Kontenplan.txt")
        if not os.path.exists(txt_path):
            template_path = os.path.join(base_dir, "Systemdaten", "Templates", f"{typ}_Codice_Civile_2424.txt")
            if os.path.exists(template_path):
                try:
                    shutil.copy2(template_path, txt_path)
                except Exception as e:
                    pass

def build_system_instruction(nutzerdaten_dir: str, is_stage2: bool = False, is_er: bool = True) -> str:
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
    typ_prefix = "ER" if is_er else "AR"
    txt_path = os.path.join(nutzerdaten_dir, f"{typ_prefix}_Kontenplan.txt")
    if os.path.exists(txt_path):
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                kontenplan_text = f.read()
        except Exception:
            pass
            
    instruction = "Du bist ein KI-Buchhalter für den italienischen SDI Standard.\n"
    instruction += "Deine Aufgabe ist es, Rechnungs-Artikel einem passenden FIBU-Konto zuzuordnen.\n\n"
    instruction += client_info
    instruction += f"HINTERGRUND ({typ_prefix}-Kontenplan):\n"
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
        instruction += "5. Der Wert ist ausschließlich das exakte Konto (z.B. 100 / 801006_Kalb) genau wie im Kontenplan gelistet als String.\n"
        instruction += "6. Du MUSST dich zwingend für ein Konto entscheiden. Lass den Wert NIEMALS leer, auch wenn du unsicher bist. Wähle das wahrscheinlichste.\n"
        instruction += "BEISPIEL-ANTWORT:\n"
        instruction += "{\n  \"0\": \"100 / 801006\",\n  \"1\": \"104 / 821249\"\n}"
    
    return instruction
def get_api_key(base_dir: str) -> str:
    import keyring
    key = keyring.get_password("BuchhaltungApp", "GeminiAPI")
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
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
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



async def process_batch_stage1(chunk, system_instruction_stage1, batch_num, total_batches, sem, results) -> List[Dict[str, Any]]:
    global cancel_requested
    
    if cancel_requested:
        return []

    async with sem:
        if cancel_requested:
            return []
            
        print(f"-> Starte Stufe 1 Batch {batch_num}/{total_batches} ({len(chunk)} Artikel)...")
        prompt_text = "Bitte klassifiziere folgende Artikel:\n"
        for local_idx, item in enumerate(chunk):
            prompt_text += f"ID: {local_idx} | "
            for k, v in item.items():
                if k not in ['id', 'cache_key'] and str(v).strip() != "":
                    if k == 'Rechnung_Kontext':
                        prompt_text += f"Rechnungshauptleistung: {v} | "
                    else:
                        prompt_text += f"{k}: {v} | "
            prompt_text += "\n"
            
        unsichere_faelle = []
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
            
            geloeste_local_indices = set()
            if response_json and isinstance(response_json, dict):
                for local_idx_str, data in response_json.items():
                    if local_idx_str.isdigit():
                        local_idx = int(local_idx_str)
                        if 0 <= local_idx < len(chunk):
                            if isinstance(data, dict):
                                try:
                                    konfidenz = int(data.get("konfidenz", 0))
                                except (ValueError, TypeError):
                                    konfidenz = 0
                                if konfidenz >= CONFIDENCE_THRESHOLD:
                                    global_id = chunk[local_idx]['id']
                                    results[global_id] = str(data.get("konto", "")).strip()
                                    geloeste_local_indices.add(local_idx)
            
            for local_idx, item in enumerate(chunk):
                if local_idx not in geloeste_local_indices:
                    unsichere_faelle.append(item)
                    
            print(f"<- Stufe 1 Batch {batch_num}/{total_batches} fertig: {len(geloeste_local_indices)}/{len(chunk)} geloest ({len(unsichere_faelle)} fuer Stufe 2 vorgemerkt).")
            return unsichere_faelle
            
        except Exception as e:
            print(f"Fehler in Stufe 1 Batch {batch_num}: {e}")
            return chunk

async def process_batch_stage2(chunk, system_instruction_stage2, batch_num, total_batches, sem, results) -> bool:
    global cancel_requested
    
    if cancel_requested:
        return False

    async with sem:
        if cancel_requested:
            return False
            
        print(f"-> Starte Stufe 2 Batch {batch_num}/{total_batches} ({len(chunk)} Artikel) [Flash-Wasserfall]...")
        prompt_text_2 = "Bitte analysiere folgende schwierige Faelle:\n"
        for local_idx, item in enumerate(chunk):
            prompt_text_2 += f"ID: {local_idx} | "
            for k, v in item.items():
                if k not in ['id', 'cache_key'] and str(v).strip() != "":
                    if k == 'Rechnung_Kontext':
                        prompt_text_2 += f"Rechnungshauptleistung: {v} | "
                    else:
                        prompt_text_2 += f"{k}: {v} | "
            prompt_text_2 += "\n"
            
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            response_json_2 = await call_gemini_api_with_retry(
                None,  # Wird durch Wasserfall ueberschrieben
                system_instruction_stage2,
                prompt_text_2,
                f"S2-{batch_num}",
                base_dir,
                is_waterfall=True
            )
            
            if response_json_2 and isinstance(response_json_2, dict):
                geloest_s2 = 0
                for local_idx_str, konto in response_json_2.items():
                    if local_idx_str.isdigit():
                        local_idx = int(local_idx_str)
                        if 0 <= local_idx < len(chunk):
                            global_id = chunk[local_idx]['id']
                            if isinstance(konto, str):
                                results[global_id] = konto.strip()
                                geloest_s2 += 1
                            elif isinstance(konto, dict):
                                results[global_id] = str(konto.get("konto", "")).strip()
                                geloest_s2 += 1
                print(f"<- Stufe 2 Batch {batch_num}/{total_batches} abgeschlossen ({geloest_s2}/{len(chunk)} zugeordnet).")
                return True
            else:
                print(f"   Stufe 2 Batch {batch_num}/{total_batches}: Keine gueltige Antwort.")
                return False
                
        except Exception as e:
            print(f"Fehler in Stufe 2 Batch {batch_num}: {e}")
            return False

# Rueckwaertskompatibilitaet falls benoetigt
process_batch_async = process_batch_stage1

async def async_classify_items_with_ai(items_to_classify: List[Dict[str, Any]], api_key: str, nutzerdaten_dir: str, is_er: bool = True) -> Dict[str, str]:
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
        # Nutze die saubere Beschreibung (ohne Datum etc.) für den Cache, falls vorhanden
        desc = item.get('Desc_Norm', '')
        if not desc:
            desc = item.get('Beschreibung', '')
            
        rechnung_kontext = item.get('Rechnung_Kontext', '')
        if rechnung_kontext:
            cache_key = f"{supplier} | {desc} [KONTEXT: {rechnung_kontext}]".strip().upper()
        else:
            cache_key = f"{supplier} | {desc}".strip().upper()
        
        if cache_key in memory:
            results[item['id']] = memory[cache_key]
        else:
            # Fuzzy-Fallback im Cache (gleicher Lieferant, ähnlicher Artikel unter Berücksichtigung von Signalwörtern)
            supplier_upper = str(supplier).strip().upper()
            desc_upper = str(desc).strip().upper()
            matched_konto = None
            highest_ratio = 0.0
            
            # Nebenpositionen dürfen niemals generisch per Fuzzy gematcht werden, da sie vom Kontext abhängen
            if not is_generic_auxiliary(desc):
                for m_key, m_konto in memory.items():
                    if " | " in m_key:
                        k_supp, k_desc = m_key.split(" | ", 1)
                        k_supp = k_supp.strip()
                        k_desc = k_desc.strip()
                        k_desc_clean = re.sub(r'\s*\[KONTEXT:.*?\]', '', k_desc, flags=re.IGNORECASE).strip()
                        if k_supp == supplier_upper or (len(k_supp) >= 5 and (k_supp in supplier_upper or supplier_upper in k_supp)):
                            if not k_desc_clean:
                                continue
                            ratio = SequenceMatcher(None, desc_upper, k_desc_clean).ratio()
                            if is_similar_desc(desc_upper, k_desc_clean, threshold=0.80):
                                score = max(ratio, 0.80)
                                if score > highest_ratio:
                                    highest_ratio = score
                                    matched_konto = m_konto
                                
            if matched_konto:
                results[item['id']] = matched_konto
                memory[cache_key] = matched_konto
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
        
    system_instruction_stage1 = build_system_instruction(nutzerdaten_dir, is_stage2=False, is_er=is_er)
    system_instruction_stage2 = build_system_instruction(nutzerdaten_dir, is_stage2=True, is_er=is_er)
    
    chunk_size_stage1 = 25
    chunk_size_stage2 = 15
    total_items = len(items_for_api)
    results = {}
    
    print(f"\nSende {total_items} neue Positionen asynchron an die KI zur Kontierung...")
    
    chunks_stage1 = [items_for_api[i:i + chunk_size_stage1] for i in range(0, total_items, chunk_size_stage1)]
    sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    # --- STUFE 1: Vorfilterung ueber Lite-Modell ---
    total_batches_s1 = len(chunks_stage1)
    completed_batches_s1 = 0
    
    async def process_and_track_s1(chunk, i):
        nonlocal completed_batches_s1
        batch_unsichere = await process_batch_stage1(chunk, system_instruction_stage1, i + 1, total_batches_s1, sem, results)
        completed_batches_s1 += 1
        percent = 20 + int((completed_batches_s1 / total_batches_s1) * 40)
        print(f"[PROGRESS:{percent}]")
        return batch_unsichere

    tasks_s1 = [process_and_track_s1(chunk, i) for i, chunk in enumerate(chunks_stage1)]
    s1_outputs = await asyncio.gather(*tasks_s1, return_exceptions=True)
    
    if cancel_requested:
        return results
        
    all_unsichere = []
    for out in s1_outputs:
        if isinstance(out, list):
            all_unsichere.extend(out)
            
    geloest_s1 = len(results)
    print(f"\nStufe 1 beendet: {geloest_s1}/{total_items} Positionen direkt geloest (Konfidenz >= {CONFIDENCE_THRESHOLD}/10).")
    
    # --- STUFE 2: Unsichere Faelle sammeln und in 15er-Bloecken an Flash-Wasserfall senden ---
    if all_unsichere and not cancel_requested:
        chunks_stage2 = [all_unsichere[i:i + chunk_size_stage2] for i in range(0, len(all_unsichere), chunk_size_stage2)]
        total_batches_s2 = len(chunks_stage2)
        completed_batches_s2 = 0
        
        print(f"Sammle {len(all_unsichere)} Faelle fuer Stufe 2 in {total_batches_s2} Bloecke (max. {chunk_size_stage2} Artikel/Block)...")
        
        async def process_and_track_s2(chunk, i):
            nonlocal completed_batches_s2
            ok = await process_batch_stage2(chunk, system_instruction_stage2, i + 1, total_batches_s2, sem, results)
            completed_batches_s2 += 1
            percent = 60 + int((completed_batches_s2 / total_batches_s2) * 30)
            print(f"[PROGRESS:{percent}]")
            return ok

        tasks_s2 = [process_and_track_s2(chunk, i) for i, chunk in enumerate(chunks_stage2)]
        await asyncio.gather(*tasks_s2, return_exceptions=True)
    else:
        print("[PROGRESS:90]")
    
    # Track new entries for DB
    for item in items_for_api:
        if item['id'] in results:
            new_entries[item['cache_key']] = results[item['id']]
            
    # Save cache
    if new_entries:
        db.save_konten_cache_batch(kunden_id, new_entries)
        print("SQL Cache (Konten) wurde aktualisiert.")
    
    return results

def ask_gemini_batch(items_to_classify: List[Dict[str, Any]], api_key: str, nutzerdaten_dir: str, is_er: bool = True) -> Dict[str, str]:
    """
    Synchronous wrapper for the async AI classification function (Legacy Alias).
    """
    return asyncio.run(async_classify_items_with_ai(items_to_classify, api_key, nutzerdaten_dir, is_er))
