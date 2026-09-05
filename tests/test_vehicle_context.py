import unittest
import sys
import os

# Add project paths
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
prog_dir = os.path.join(base_dir, "Programme")
be_dir = os.path.join(prog_dir, "Buchungen erstellen")
for p in [base_dir, prog_dir, be_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

import BuchungenErstellen
import Buchung_KI

class TestVehicleContext(unittest.TestCase):
    def test_fuzzy_cache_match_context_separation(self):
        """Fuzzy cache matching must never cross-match different contexts."""
        cache = {
            "ENI | DIESEL [KONTEXT: LKW]": {"value": "810005", "confirmed": True},
            "ENI | DIESEL [KONTEXT: PKW]": {"value": "810001", "confirmed": True},
            "ENI | DIESEL [KONTEXT: TRAKTOR]": {"value": "810007", "confirmed": True},
            "ENI | BENZIN": {"value": "810000", "confirmed": True},
        }

        # 1. Match with exact required context
        match_lkw = BuchungenErstellen.find_fuzzy_cache_match("ENI", "Diesel", cache, required_context="LKW")
        self.assertIsNotNone(match_lkw)
        self.assertEqual(match_lkw["value"], "810005")

        match_pkw = BuchungenErstellen.find_fuzzy_cache_match("ENI", "Diesel", cache, required_context="PKW")
        self.assertIsNotNone(match_pkw)
        self.assertEqual(match_pkw["value"], "810001")

        match_traktor = BuchungenErstellen.find_fuzzy_cache_match("ENI", "Diesel", cache, required_context="Traktor")
        self.assertIsNotNone(match_traktor)
        self.assertEqual(match_traktor["value"], "810007")

        # 2. Asking for BAGGER when only LKW, PKW, TRAKTOR exist -> should NOT match
        match_bagger = BuchungenErstellen.find_fuzzy_cache_match("ENI", "Diesel", cache, required_context="Bagger")
        self.assertIsNone(match_bagger)

        # 3. Asking without context should NOT match context entries
        match_no_ctx = BuchungenErstellen.find_fuzzy_cache_match("ENI", "Diesel", cache, required_context="")
        self.assertIsNone(match_no_ctx)

        # 4. Asking without context for uncontexted entry should match
        match_benzin = BuchungenErstellen.find_fuzzy_cache_match("ENI", "Benzin", cache, required_context="")
        self.assertIsNotNone(match_benzin)
        self.assertEqual(match_benzin["value"], "810000")

    def test_deduplication_keeps_different_vehicles_separate(self):
        """Deduplication before AI call must not combine different vehicle types."""
        positions = [
            {
                "Aktiv/Passiv": "Passiva",
                "Typ": "TD01",
                "Rechnungsnummer": "1",
                "Datum": "2024-01-01",
                "Lieferant": "ENI",
                "Liefer ID": "IT12345678901",
                "Kunde": "Musterkunde",
                "Kunden ID": "IT98765432109",
                "Beschreibung": "Diesel Kraftstoff",
                "Unterkonto": "???",
                "Hauptkonto": "",
                "is_pending": True,
                "_rechnung_kontext": "LKW",
                "CdC": "",
                "Kennzeichen": "AA111AA",
                "Fahrzeugtyp": "LKW",
                "Menge": 50,
                "Einzelpreis (EUR)": 1.8,
                "Gesamtpreis (EUR)": 90.0,
                "MwSt (%)": 0.22,
            },
            {
                "Aktiv/Passiv": "Passiva",
                "Typ": "TD01",
                "Rechnungsnummer": "2",
                "Datum": "2024-01-02",
                "Lieferant": "ENI",
                "Liefer ID": "IT12345678901",
                "Kunde": "Musterkunde",
                "Kunden ID": "IT98765432109",
                "Beschreibung": "Diesel Kraftstoff",
                "Unterkonto": "???",
                "Hauptkonto": "",
                "is_pending": True,
                "_rechnung_kontext": "PKW",
                "CdC": "",
                "Kennzeichen": "BB222BB",
                "Fahrzeugtyp": "PKW",
                "Menge": 40,
                "Einzelpreis (EUR)": 1.8,
                "Gesamtpreis (EUR)": 72.0,
                "MwSt (%)": 0.22,
            },
            {
                "Aktiv/Passiv": "Passiva",
                "Typ": "TD01",
                "Rechnungsnummer": "3",
                "Datum": "2024-01-03",
                "Lieferant": "ENI",
                "Liefer ID": "IT12345678901",
                "Kunde": "Musterkunde",
                "Kunden ID": "IT98765432109",
                "Beschreibung": "Diesel Kraftstoff",
                "Unterkonto": "???",
                "Hauptkonto": "",
                "is_pending": True,
                "_rechnung_kontext": "Traktor",
                "CdC": "",
                "Kennzeichen": "CC333CC",
                "Fahrzeugtyp": "Traktor",
                "Menge": 100,
                "Einzelpreis (EUR)": 1.8,
                "Gesamtpreis (EUR)": 180.0,
                "MwSt (%)": 0.22,
            },
            {
                "Aktiv/Passiv": "Passiva",
                "Typ": "TD01",
                "Rechnungsnummer": "4",
                "Datum": "2024-01-04",
                "Lieferant": "ENI",
                "Liefer ID": "IT12345678901",
                "Kunde": "Musterkunde",
                "Kunden ID": "IT98765432109",
                "Beschreibung": "Diesel Kraftstoff",
                "Unterkonto": "???",
                "Hauptkonto": "",
                "is_pending": True,
                "_rechnung_kontext": "LKW",
                "CdC": "",
                "Kennzeichen": "AA111AA",
                "Fahrzeugtyp": "LKW",
                "Menge": 60,
                "Einzelpreis (EUR)": 1.8,
                "Gesamtpreis (EUR)": 108.0,
                "MwSt (%)": 0.22,
            }
        ]

        unique_unknowns_er = {}
        for i, pos in enumerate(positions):
            desc_raw = pos.get('Beschreibung', '')
            desc_norm = BuchungenErstellen.clean_description_for_dedup(desc_raw)
            liefer_id = pos.get('Liefer ID', '')
            kunden_id = pos.get('Kunden ID', '')
            rechnung_kontext = pos.get('_rechnung_kontext', '')

            matched_key = None
            for existing_key in unique_unknowns_er.keys():
                e_liefer, e_desc, e_kunden, e_kontext = existing_key
                if e_liefer == liefer_id and e_kunden == kunden_id and e_kontext == rechnung_kontext:
                    if BuchungenErstellen.is_similar_desc(e_desc, desc_norm):
                        matched_key = existing_key
                        break

            if not matched_key:
                matched_key = (liefer_id, desc_norm, kunden_id, rechnung_kontext)
                item_id = f"er_{len(unique_unknowns_er)}"
                item_data = {'id': item_id, 'Desc_Norm': desc_norm}
                if rechnung_kontext:
                    item_data['Rechnung_Kontext'] = rechnung_kontext
                unique_unknowns_er[matched_key] = {
                    'item': item_data,
                    'indices': []
                }
            unique_unknowns_er[matched_key]['indices'].append(i)

        # 4 positions, but pos 0 and 3 are both LKW
        # Therefore, unique items sent to AI should be 3: (LKW, PKW, Traktor)
        self.assertEqual(len(unique_unknowns_er), 3)

        contexts = [data['item'].get('Rechnung_Kontext') for data in unique_unknowns_er.values()]
        self.assertIn("LKW", contexts)
        self.assertIn("PKW", contexts)
        self.assertIn("Traktor", contexts)

        # The LKW item should contain indices 0 and 3
        lkw_data = [data for data in unique_unknowns_er.values() if data['item'].get('Rechnung_Kontext') == 'LKW'][0]
        self.assertEqual(lkw_data['indices'], [0, 3])

    def test_prompt_generation_includes_context_in_description(self):
        """When Rechnung_Kontext is present, prompt building should tag Beschreibung with [Kontext: ...]."""
        chunk = [
            {
                "id": "er_0",
                "Desc_Norm": "DIESEL",
                "Rechnung_Kontext": "LKW",
                "Lieferant": "ENI",
                "Beschreibung": "Diesel Kraftstoff",
                "Fahrzeugtyp": "LKW"
            },
            {
                "id": "er_1",
                "Desc_Norm": "DIESEL",
                "Rechnung_Kontext": "Traktor",
                "Lieferant": "ENI",
                "Beschreibung": "Diesel Kraftstoff",
                "Fahrzeugtyp": "Traktor"
            },
            {
                "id": "er_2",
                "Desc_Norm": "PAPIER A4",
                "Lieferant": "Bürobedarf",
                "Beschreibung": "Kopierpapier"
            }
        ]

        # Simulate the loop from process_batch_stage1
        prompt_lines = []
        for local_idx, item in enumerate(chunk):
            line = f"ID: {local_idx} | "
            ctx = str(item.get('Rechnung_Kontext', '')).strip()
            for k, v in item.items():
                if k not in ['id', 'cache_key'] and str(v).strip() != "":
                    if k == 'Rechnung_Kontext':
                        line += f"Kontext: {v} | "
                    elif k == 'Beschreibung' and ctx and "[KONTEXT:" not in str(v).upper():
                        line += f"Beschreibung: {v} [Kontext: {ctx}] | "
                    else:
                        line += f"{k}: {v} | "
            prompt_lines.append(line)

        # Check line 0 (LKW)
        self.assertIn("Beschreibung: Diesel Kraftstoff [Kontext: LKW]", prompt_lines[0])
        self.assertIn("Kontext: LKW", prompt_lines[0])

        # Check line 1 (Traktor)
        self.assertIn("Beschreibung: Diesel Kraftstoff [Kontext: Traktor]", prompt_lines[1])
        self.assertIn("Kontext: Traktor", prompt_lines[1])

        # Check line 2 (No context)
        self.assertIn("Beschreibung: Kopierpapier", prompt_lines[2])
        self.assertNotIn("[Kontext:", prompt_lines[2])

if __name__ == "__main__":
    unittest.main()
