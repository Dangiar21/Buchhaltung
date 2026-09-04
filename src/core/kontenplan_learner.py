import os
import re
import json
import asyncio
import datetime
import shutil
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd

# Gemini models waterfall
GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash"
]

def get_base_dir() -> str:
    """Gibt das Root-Verzeichnis der Anwendung zurück."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_gemini_api_key() -> Optional[str]:
    """Holt den Gemini API-Key sicher aus dem Keyring oder aus config.json."""
    try:
        import keyring
        key = keyring.get_password("BuchhaltungApp", "GeminiAPI")
        if key:
            return key
    except Exception:
        pass
        
    try:
        base_dir = get_base_dir()
        config_path = os.path.join(base_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg.get("gemini_api_key")
    except Exception:
        pass
    return None


def clean_str(val: Any) -> str:
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "null", "???"):
        return ""
    return s


def find_column(df_columns: List[str], candidates: List[str]) -> Optional[str]:
    """Findet die erste passende Spalte unabhängig von Groß-/Kleinschreibung."""
    col_map = {c.strip().lower(): c for c in df_columns}
    for cand in candidates:
        cand_lower = cand.strip().lower()
        if cand_lower in col_map:
            return col_map[cand_lower]
        # Teilstring-Suche
        for col_name_lower, orig_col in col_map.items():
            if cand_lower in col_name_lower:
                return orig_col
    return None


def parse_booking_excel(excel_path: str, target_typ: str = "ER") -> Dict[str, Any]:
    """
    Liest eine Excel-Datei (z. B. Gesammelte_Buchungen.xlsx) ein und gruppiert
    die Datensätze nach Kontonummer.
    
    :param excel_path: Pfad zur Excel-Datei
    :param target_typ: 'ER' (Eingangsrechnungen) oder 'AR' (Ausgangsrechnungen)
    :return: Dict mit 'items_by_konto', 'total_rows', 'valid_rows', 'sheet_name'
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel-Datei nicht gefunden: {excel_path}")

    with pd.ExcelFile(excel_path) as xls:
        sheet_names = xls.sheet_names
        
        # Bestimme das passende Sheet
        selected_sheet = None
        if target_typ == "ER":
            for s in sheet_names:
                if any(k in s.lower() for k in ["eingang", "er_", "passiv", "fornitor", "acquisto"]):
                    selected_sheet = s
                    break
        elif target_typ == "AR":
            for s in sheet_names:
                if any(k in s.lower() for k in ["ausgang", "ar_", "aktiv", "client", "vendit"]):
                    selected_sheet = s
                    break
                    
        if not selected_sheet:
            # Fallback: Erstes Sheet
            selected_sheet = sheet_names[0]

        df = pd.read_excel(xls, sheet_name=selected_sheet)
    total_rows = len(df)
    
    # Spalten lokalisieren
    col_konto = find_column(df.columns, [
        "unterkonto", "konto", "hauptkonto", "sottoconto", "conto", "mastro", "fibu"
    ])
    col_desc = find_column(df.columns, [
        "beschreibung", "artikel", "produkt", "bezeichnung", "descrizione", "prodotto", "text"
    ])
    col_supplier = find_column(df.columns, [
        "lieferant", "kunde", "partner", "fornitore", "cliente", "name", "ragione sociale"
    ])
    col_typ = find_column(df.columns, ["aktiv/passiv", "typ", "rechnungstyp"])

    if not col_konto:
        raise ValueError(f"In Sheet '{selected_sheet}' konnte keine Konto-Spalte gefunden werden.")
    if not col_desc:
        raise ValueError(f"In Sheet '{selected_sheet}' konnte keine Beschreibungs-Spalte gefunden werden.")

    # Filter nach Aktiv/Passiv falls Spalte existiert und eindeutig trennbar ist
    if col_typ:
        if target_typ == "ER":
            df = df[df[col_typ].astype(str).str.lower().str.contains("passiv|er|fornitor", na=False) | (df[col_typ].isna())]
        elif target_typ == "AR":
            df = df[df[col_typ].astype(str).str.lower().str.contains("aktiv|ar|client", na=False) | (df[col_typ].isna())]

    items_by_konto: Dict[str, List[Dict[str, str]]] = {}
    valid_rows = 0
    seen_pairs_by_konto: Dict[str, set] = {}

    for _, row in df.iterrows():
        raw_konto = clean_str(row.get(col_konto))
        raw_desc = clean_str(row.get(col_desc))
        supplier = clean_str(row.get(col_supplier)) if col_supplier else ""

        if not raw_konto or not raw_desc or raw_konto == "???":
            continue

        # Normalisierung des Kontos
        # Oft steht in Excel z.B. 801001 oder 104 / 801001 oder 104 / 801001 – Verbrauchsmaterial
        konto_key = raw_konto.strip()

        if konto_key not in items_by_konto:
            items_by_konto[konto_key] = []
            seen_pairs_by_konto[konto_key] = set()

        # Dedupliziere exakt gleiche Kombination aus Beschreibung + Lieferant
        pair_key = (raw_desc.lower(), supplier.lower())
        if pair_key not in seen_pairs_by_konto[konto_key]:
            seen_pairs_by_konto[konto_key].add(pair_key)
            items_by_konto[konto_key].append({
                "beschreibung": raw_desc,
                "lieferant": supplier
            })
            valid_rows += 1

    return {
        "items_by_konto": items_by_konto,
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "sheet_name": selected_sheet
    }


async def call_gemini_json(
    client,
    system_instruction: str,
    prompt_text: str,
    temperature: float = 0.1,
    max_retries: int = 10
) -> Optional[Any]:
    """Führt einen API-Aufruf an Gemini mit strukturiertem JSON-Output und Fallback durch."""
    from google.genai import types

    for model_name in GEMINI_MODELS:
        for attempt in range(max_retries):
            try:
                def _call():
                    return client.models.generate_content(
                        model=model_name,
                        contents=prompt_text,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            response_mime_type="application/json",
                            temperature=temperature,
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        ),
                    )
                response = await asyncio.to_thread(_call)
                raw_text = response.text
                raw_text = re.sub(r"^```json\s*", "", raw_text, flags=re.IGNORECASE)
                raw_text = re.sub(r"```\s*$", "", raw_text)
                return json.loads(raw_text.strip())
            except Exception as e:
                err_msg = str(e).lower()
                if "429" in err_msg or "quota" in err_msg or "resourceexhausted" in err_msg:
                    if "per minute" in err_msg:
                        await asyncio.sleep(15)
                        continue
                    # Tageslimit -> Nächstes Modell im Wasserfall
                    break
                if attempt < 3:
                    await asyncio.sleep(2)
                else:
                    break
    return None


async def synthesize_terms_for_chunk(
    client,
    konto_name: str,
    chunk: List[Dict[str, str]]
) -> List[str]:
    """
    Stufe 1: Generalisiert bis zu 50 Rechnungsbeschreibungen eines Kontos
    in prägnante Überbegriffe.
    """
    sys_instruction = (
        "Du bist ein Experte für Buchhaltung und FIBU-Kontenpläne im italienischen SDI-Standard (Südtirol, zweisprachig DE & IT).\n"
        "Deine Aufgabe ist es, Rechnungs-Artikelbeschreibungen zu analysieren und prägnante, allgemeine Überbegriffe bzw. "
        "Gattungsbeispiele (Keywords) zu formulieren, die sich ideal als Kontenplan-Beispiele eignen.\n\n"
        "REGELN:\n"
        "1. Wandle spezifische Produkt- oder Markennamen in allgemeine Gattungsbegriffe um (z.B. aus 'HP LaserJet CE285A Schwarz' wird 'Toner & Druckerpatronen', aus 'Würth Holzschraube 4x40' wird 'Schrauben & Holzverbindungsmittel').\n"
        "2. Keine Modellnummern, Seriennummern, Abmessungen oder Einzelfirmen.\n"
        "3. Berücksichtige die Sprache der Eingaben: Antworte in Deutsch und/oder Italienisch, je nachdem wie die Rechnungen formuliert sind.\n"
        "4. Antworte AUSSCHLIESSLICH als valides JSON-Array von Strings, z. B. [\"Begriff 1\", \"Begriff 2\"]."
    )

    items_text = "\n".join([
        f"- {item['beschreibung']}" + (f" (Lieferant: {item['lieferant']})" if item.get('lieferant') else "")
        for item in chunk
    ])

    prompt = (
        f"KONTO: {konto_name}\n\n"
        f"RECHNUNGSPOSITIONEN:\n{items_text}\n\n"
        "Formuliere daraus 3 bis 10 treffende, verallgemeinerte Überbegriffe/Kategorien für dieses Konto."
    )

    res = await call_gemini_json(client, sys_instruction, prompt)
    if isinstance(res, list):
        return [str(x).strip() for x in res if str(x).strip()]
    elif isinstance(res, dict) and "begriffe" in res:
        return [str(x).strip() for x in res["begriffe"] if str(x).strip()]
    return []


async def clean_and_deduplicate_konto_terms(
    client,
    konto_name: str,
    existing_terms: List[str],
    raw_proposed_terms: List[str],
    max_limit: int = 20
) -> List[str]:
    """
    Stufe 2: Bereinigt, dedupliziert und filtert die gesammelten Vorschläge.
    Gleicht sie mit existierenden Beispielen im Kontenplan ab und begrenzt
    die Gesamtzahl auf max_limit (Standard: 20).
    """
    if not raw_proposed_terms:
        return []

    sys_instruction = (
        "Du bist ein FIBU-Experte. Du bereinigst und optimierst Kontenplan-Beispiele.\n"
        "Deine Aufgabe:\n"
        "1. Entferne Duplikate und nahe Synonyme aus den neuen Vorschlägen.\n"
        "2. Entferne Vorschläge, die inhaltlich bereits durch bestehende Beispiele abgedeckt sind.\n"
        "3. Entferne unpassende, zu generische (z.B. 'Dienstleistung' oder 'Produkt') oder triviale Begriffe.\n"
        f"4. Begrenze das Gesamtergebnis so, dass bestehende Beispiele + neue Vorschläge maximal {max_limit} nicht überschreiten.\n"
        "5. Antworte AUSSCHLIESSLICH als JSON-Array der NEUEN, zu ergänzenden Begriffe (Strings)."
    )

    prompt = (
        f"KONTO: {konto_name}\n\n"
        f"BEREITS IM KONTENPLAN VORHANDEN:\n{json.dumps(existing_terms, ensure_ascii=False)}\n\n"
        f"NEUE VORSCHLÄGE AUS BUCHUNGEN:\n{json.dumps(raw_proposed_terms, ensure_ascii=False)}\n\n"
        f"Gib maximal {max(1, max_limit - len(existing_terms))} hochwertige, NEUE Ergänzungsbegriffe zurück."
    )

    res = await call_gemini_json(client, sys_instruction, prompt)
    if isinstance(res, list):
        cleaned = [str(x).strip() for x in res if str(x).strip()]
        # Sicherstellen dass max_limit nicht überschritten wird
        max_allowed = max(0, max_limit - len(existing_terms))
        return cleaned[:max_allowed]
    return raw_proposed_terms[:max(1, max_limit - len(existing_terms))]


def extract_existing_examples_from_desc(desc: str) -> List[str]:
    """
    Extrahiert bestehende Beispiele aus der Beschreibung eines Kontos,
    z. B. aus '(Z. B. Vakuumsäcke, Garn)' -> ['Vakuumsäcke', 'Garn'].
    """
    if not desc:
        return []
    
    # Suche nach (z. B. ...) oder (z.B. ...) oder (es. ...)
    m = re.search(r'\((?:z\.?\s*b\.?|es\.?|ad es\.?)\s*:?\s*([^)]+)\)', desc, flags=re.IGNORECASE)
    if m:
        content = m.group(1)
        # Trenne an Kommas oder Semikolons
        parts = [p.strip() for p in re.split(r'[,;/]', content) if p.strip()]
        return parts
        
    # Falls keine Klammer da ist, aber Aufzählungen mit Kommas existieren
    if "," in desc:
        return [p.strip() for p in desc.split(",") if p.strip()]
        
    return [desc.strip()] if desc.strip() else []


def merge_examples_into_desc(existing_desc: str, new_terms: List[str], max_limit: int = 20) -> str:
    """
    Fügt neue Beispiele sauber in die bestehende Kontenbeschreibung ein.
    """
    if not new_terms:
        return existing_desc

    current_examples = extract_existing_examples_from_desc(existing_desc)
    
    # Deduplizieren mit Case-Insensitive Check
    seen = {e.lower(): e for e in current_examples}
    for t in new_terms:
        if t.lower() not in seen:
            seen[t.lower()] = t
            current_examples.append(t)
            if len(current_examples) >= max_limit:
                break
                
    examples_str = ", ".join(current_examples[:max_limit])
    formatted_zb = f"(Z. B. {examples_str})"
    
    # Wenn im bisherigen Text bereits ein (Z. B. ...) stand, diesen ersetzen
    if re.search(r'\((?:z\.?\s*b\.?|es\.?|ad es\.?)\s*:?\s*[^)]+\)', existing_desc, flags=re.IGNORECASE):
        return re.sub(
            r'\((?:z\.?\s*b\.?|es\.?|ad es\.?)\s*:?\s*[^)]+\)',
            formatted_zb,
            existing_desc,
            flags=re.IGNORECASE
        ).strip()
    elif existing_desc.strip():
        # Text vorhanden, aber ohne (Z. B. ...)
        return f"{existing_desc.strip()}\n{formatted_zb}"
    else:
        # Komplett neu
        return formatted_zb


def apply_confirmed_terms_to_kontenplan(
    target_kontenplan_path: str,
    confirmed_updates: Dict[str, Dict[str, Any]],
    max_limit: int = 20
) -> Tuple[bool, str, int]:
    """
    Schreibt die bestätigten Begriffe in den Kontenplan zurück und erstellt vorher ein Backup.
    
    :param target_kontenplan_path: Pfad zur .txt Datei
    :param confirmed_updates: Dict mit Konto-Schlüssel -> {'name': str, 'terms': List[str], 'is_new': bool}
    :param max_limit: Max Beispiele pro Konto
    :return: (Erfolg: bool, Statusmeldung: str, Anzahl aktualisierter Konten: int)
    """
    from src.ui.kontenplan_editor import parse_kontenplan, serialize_kontenplan

    if not os.path.exists(target_kontenplan_path):
        # Falls Datei noch nicht existiert, leer anlegen
        os.makedirs(os.path.dirname(target_kontenplan_path), exist_ok=True)
        with open(target_kontenplan_path, "w", encoding="utf-8") as f:
            f.write("")

    # 1. Backup anlegen
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{target_kontenplan_path}.backup_{timestamp}"
    try:
        shutil.copy2(target_kontenplan_path, backup_path)
    except Exception as e:
        return False, f"Backup konnte nicht erstellt werden: {e}", 0

    # 2. Kontenplan parsen
    with open(target_kontenplan_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    entries = parse_kontenplan(content)
    
    # Map aufbauen: normalisierte Kontonummer -> Index im Array
    def normalize_konto_str(s: str) -> str:
        s = s.strip()
        numbers = re.findall(r'[\w]+', s)
        return "_".join(numbers).upper()

    existing_map: Dict[str, int] = {}
    for idx, e in enumerate(entries):
        k = normalize_konto_str(e.get("konto", ""))
        if k:
            existing_map[k] = idx

    updated_count = 0

    for konto_key, update_info in confirmed_updates.items():
        terms = update_info.get("terms", [])
        if not terms:
            continue

        norm_key = normalize_konto_str(konto_key)
        
        # Versuche exakten oder teilweisen Match
        match_idx = existing_map.get(norm_key)
        if match_idx is None:
            # Versuche Match anhand der reinen Unterkontonummer (z.B. 801001)
            sub_numbers = re.findall(r'\d{4,}', konto_key)
            if sub_numbers:
                target_sub = sub_numbers[-1]
                for k_norm, e_idx in existing_map.items():
                    if target_sub in k_norm:
                        match_idx = e_idx
                        break

        if match_idx is not None:
            # Bestehendes Konto aktualisieren
            current_entry = entries[match_idx]
            current_desc = current_entry.get("beschreibung", "")
            current_entry["beschreibung"] = merge_examples_into_desc(current_desc, terms, max_limit)
            updated_count += 1
        else:
            # Neues Konto anlegen
            # Trenne Konto und Name falls in konto_key enthalten (z. B. "104 / 801001 – Ware")
            k_name = update_info.get("name", "").strip()
            k_num = konto_key.strip()
            if "–" in k_num:
                parts = k_num.split("–", 1)
                k_num = parts[0].strip()
                if not k_name:
                    k_name = parts[1].strip()
            elif " - " in k_num:
                parts = k_num.split(" - ", 1)
                k_num = parts[0].strip()
                if not k_name:
                    k_name = parts[1].strip()

            if not k_name:
                k_name = "Konto"

            entries.append({
                "konto": k_num,
                "name": k_name,
                "beschreibung": merge_examples_into_desc("", terms, max_limit)
            })
            updated_count += 1

    # 3. Kontenplan serialisieren und speichern
    new_content = serialize_kontenplan(entries)
    with open(target_kontenplan_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True, f"Erfolgreich {updated_count} Konten aktualisiert. Backup: {os.path.basename(backup_path)}", updated_count
