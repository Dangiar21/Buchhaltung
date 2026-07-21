import os
import json
import time

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

def ensure_konten_template(nutzerdaten_dir):
    default_kontenplan = (
        "# KONTENPLAN FÜR KI - Bitte hier die für den Kunden relevanten Konten eintragen!\n"
        "# Die KI wird versuchen, Artikel in eine der folgenden Kategorien/Nummern einzuordnen.\n\n"
        "Klasse 0: Anlagevermögen (z.B. 0100000 Maschinen, 0200000 Fahrzeuge, 0300000 Software)\n"
        "Klasse 1: Finanzanlagen (z.B. 1000000 Beteiligungen)\n"
        "Klasse 2: Umlaufvermögen (z.B. 2000000 Vorräte, 2100000 Kasse)\n"
        "Klasse 3: Eigenkapital & Rückstellungen (z.B. 3000000 Stammkapital)\n"
        "Klasse 4: Verbindlichkeiten (z.B. 4000000 Bankkredite, 4100000 Lieferanten)\n"
        "Klasse 5: Materialaufwand / Wareneinkauf (z.B. 5000000 Rohstoffe, 5010000 Handelsware)\n"
        "Klasse 6: Personalaufwand (z.B. 6000000 Löhne, 6010000 Gehälter)\n"
        "Klasse 7: Dienstleistungen & Sonstige Aufwendungen (z.B. 7010000 Telefon, 7020000 Strom, 7040000 Treibstoff)\n"
        "Klasse 8: Finanzerträge und -aufwendungen (z.B. 8000000 Zinserträge, 8100000 Zinsaufwand)\n"
        "Klasse 9: Steuern & Außerordentliches (z.B. 9000000 Steuern vom Einkommen)"
    )
    if nutzerdaten_dir and os.path.exists(nutzerdaten_dir):
        konten_file = os.path.join(nutzerdaten_dir, "Buchung_Konten.txt")
        if not os.path.exists(konten_file):
            try:
                with open(konten_file, "w", encoding="utf-8") as f:
                    f.write(default_kontenplan)
            except Exception as e:
                print(f"Konnte Buchung_Konten.txt nicht erstellen: {e}")
    return default_kontenplan

def ask_gemini_batch(items_to_classify, api_key, nutzerdaten_dir=None):
    """
    items_to_classify ist eine Liste von dicts: [{'id': 0, 'desc': '...', 'supplier': '...'}, ...]
    Gibt ein dict zurück: {'0': '5000000', '1': '7040000', ...}
    """
    if not api_key:
        return {}
        
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("google-genai ist nicht installiert.")
        return {}

    client = genai.Client(api_key=api_key)
    
    # Chunking: Maximal 100 Artikel pro Request
    chunk_size = 100
    results = {}
    current_model = 'gemini-3.5-flash'
    
    # Standard-Kontenplan Vorlage sicherstellen
    default_kontenplan = ensure_konten_template(nutzerdaten_dir)
    kontenplan_text = default_kontenplan

    if nutzerdaten_dir and os.path.exists(nutzerdaten_dir):
        konten_file = os.path.join(nutzerdaten_dir, "Buchung_Konten.txt")
        if os.path.exists(konten_file):
            # Lese existierende Datei mit UTF-8
            try:
                with open(konten_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        kontenplan_text = content
            except Exception as e:
                print(f"Fehler beim Lesen von Buchung_Konten.txt: {e}")

    system_instruction = (
        "Du bist ein erfahrener Buchhalter in Italien. Deine Aufgabe ist es, Rechnungspositionen "
        "in einen vorgegebenen Kontenplan einzuordnen.\n"
        "Hier sind die exakten Vorgaben und Regeln für diesen Kunden:\n\n"
        f"{kontenplan_text}\n\n"
        "Du erhältst eine Liste von Artikeln mit ID, Beschreibung und Lieferant.\n"
        "Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt, wobei die Schlüssel die IDs (als String) sind "
        "und die Werte die vorgeschlagenen Kontonummern (z.B. '5000000').\n"
        "Beispiel-Antwort: {\"0\": \"5000000\", \"1\": \"7040000\"}"
    )

    total_items = len(items_to_classify)
    for i in range(0, total_items, chunk_size):
        chunk = items_to_classify[i:i+chunk_size]
        
        prompt_text = "Bitte klassifiziere folgende Artikel:\n"
        for local_idx, item in enumerate(chunk):
            prompt_text += f"ID: {local_idx} | Lieferant: {item['supplier']} | Beschreibung: {item['desc']}\n"
            
        print(f"Sende Batch {i//chunk_size + 1} (Modell: {current_model}) an Gemini ({len(chunk)} Artikel)...")
        
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
                        print(f"\nLimit für {current_model} erreicht. Wechsle automatisch zu gemini-3.1-flash-lite...")
                        current_model = 'gemini-3.1-flash-lite'
                        print(f"Wiederhole Batch {i//chunk_size + 1} mit {current_model}...")
                        response = client.models.generate_content(
                            model=current_model,
                            contents=prompt_text,
                            config=config
                        )
                    else:
                        raise e
                else:
                    raise e
            
            # Reparatur für abgeschnittene JSON-Antworten (typisch bei KI-Müdigkeit am Ende)
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
            except json.JSONDecodeError:
                print("Fehler beim Parsen der Gemini-Antwort (kein gültiges JSON).")
                print("Antwort:", response.text)
                
            # Dynamische Pause um Limits nicht zu sprengen
            if i + chunk_size < total_items:
                wait_time = 0.5 if total_items < 300 else 6.0
                time.sleep(wait_time)
                
        except Exception as e:
            print(f"Fehler bei der API Anfrage: {e}")
            
    return results
