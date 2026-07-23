import sqlite3
import os
import json
import pandas as pd
from typing import Dict, Any

class DatabaseManager:
    _instance = None

    def __new__(cls, base_dir=None):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.init_db(base_dir)
        return cls._instance

    def init_db(self, base_dir):
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        system_dir = os.path.join(base_dir, "Systemdaten")
        os.makedirs(system_dir, exist_ok=True)
        self.db_path = os.path.join(system_dir, "buchhaltung.db")
        
        self.create_tables()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def create_tables(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Cache Analyse (Sektorenanalyse)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache_analyse (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kunden_id TEXT NOT NULL,
                    supplier TEXT NOT NULL,
                    description TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    confirmed INTEGER DEFAULT 0,
                    UNIQUE(kunden_id, supplier, description)
                )
            ''')
            try:
                cursor.execute('ALTER TABLE cache_analyse ADD COLUMN confirmed INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass
            
            # Cache Konten (FIBU)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache_konten (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kunden_id TEXT NOT NULL,
                    supplier TEXT NOT NULL,
                    description TEXT NOT NULL,
                    konto TEXT NOT NULL,
                    confirmed INTEGER DEFAULT 0,
                    UNIQUE(kunden_id, supplier, description)
                )
            ''')
            try:
                cursor.execute('ALTER TABLE cache_konten ADD COLUMN confirmed INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass
            
            # Kontenregeln (Hybrid from Excel)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS kontenregeln (
                    kunden_id TEXT NOT NULL,
                    regel_typ TEXT NOT NULL,
                    prioritaet INTEGER,
                    lieferant TEXT,
                    suchbegriff TEXT,
                    konto TEXT,
                    lieferant_id TEXT,
                    target_kunden_id TEXT,
                    status TEXT,
                    beschreibung TEXT
                )
            ''')
            
            # Legacy KI-Zuweisungen aus der Datenbank löschen (werden jetzt nur noch über den Cache gesteuert)
            cursor.execute("DELETE FROM kontenregeln WHERE regel_typ IN ('ai_pending', 'ai_confirmed')")
            
            # Sync Status (Meta-Tabelle)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_status (
                    kunden_id TEXT,
                    regel_typ TEXT,
                    last_modified REAL NOT NULL,
                    PRIMARY KEY (kunden_id, regel_typ)
                )
            ''')
            
            # Create Indices for blazing fast lookup
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_analyse_lookup ON cache_analyse (kunden_id, supplier, description)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_konten_lookup ON cache_konten (kunden_id, supplier, description)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_regeln_lookup ON kontenregeln (kunden_id)')
            
            conn.commit()

    # --- Cache Analyse ---
    def get_analyse_cache(self, kunden_id: str) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT supplier, description, result_json FROM cache_analyse WHERE kunden_id = ?', (kunden_id,))
            rows = cursor.fetchall()
            
        memory = {}
        for supplier, desc, result_json in rows:
            cache_key = f"{supplier} | {desc}".strip().upper()
            try:
                memory[cache_key] = json.loads(result_json)
            except Exception as e:
                print(f'Fehler: {e}')
                memory[cache_key] = result_json
        return memory

    def get_analyse_cache_full(self, kunden_id: str) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT supplier, description, result_json, confirmed FROM cache_analyse WHERE kunden_id = ?', (kunden_id,))
            rows = cursor.fetchall()
            
        memory = {}
        for supplier, desc, result_json, confirmed in rows:
            cache_key = f"{supplier} | {desc}".strip().upper()
            try:
                val = json.loads(result_json)
            except Exception as e:
                val = result_json
            memory[cache_key] = {'value': val, 'confirmed': bool(confirmed)}
        return memory

    def save_analyse_cache_batch(self, kunden_id: str, new_entries: Dict[str, Any]):
        if not new_entries:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for cache_key, data in new_entries.items():
                if " | " in cache_key:
                    parts = cache_key.split(" | ", 1)
                    supplier = parts[0]
                    desc = parts[1] if len(parts) > 1 else ""
                else:
                    supplier = cache_key
                    desc = ""
                    
                if isinstance(data, dict) and 'value' in data and 'confirmed' in data:
                    result = data['value']
                    confirmed = 1 if data['confirmed'] else 0
                else:
                    result = data
                    confirmed = 0
                    
                result_json = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
                
                # Upsert
                cursor.execute('''
                    INSERT INTO cache_analyse (kunden_id, supplier, description, result_json, confirmed)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(kunden_id, supplier, description) DO UPDATE SET 
                    result_json = excluded.result_json,
                    confirmed = excluded.confirmed
                ''', (kunden_id, supplier, desc, result_json, confirmed))
            conn.commit()
            
    # --- Cache Konten ---
    def get_konten_cache(self, kunden_id: str) -> Dict[str, str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT supplier, description, konto FROM cache_konten WHERE kunden_id = ?', (kunden_id,))
            rows = cursor.fetchall()
            
        memory = {}
        for supplier, desc, konto in rows:
            cache_key = f"{supplier} | {desc}".strip().upper()
            memory[cache_key] = konto
        return memory

    def get_konten_cache_full(self, kunden_id: str) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT supplier, description, konto, confirmed FROM cache_konten WHERE kunden_id = ?', (kunden_id,))
            rows = cursor.fetchall()
            
        memory = {}
        for supplier, desc, konto, confirmed in rows:
            cache_key = f"{supplier} | {desc}".strip().upper()
            memory[cache_key] = {'value': konto, 'confirmed': bool(confirmed)}
        return memory

    def save_konten_cache_batch(self, kunden_id: str, new_entries: Dict[str, Any]):
        if not new_entries:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for cache_key, data in new_entries.items():
                if " | " in cache_key:
                    parts = cache_key.split(" | ", 1)
                    supplier = parts[0]
                    desc = parts[1] if len(parts) > 1 else ""
                else:
                    supplier = cache_key
                    desc = ""
                    
                if isinstance(data, dict) and 'value' in data and 'confirmed' in data:
                    konto = data['value']
                    confirmed = 1 if data['confirmed'] else 0
                else:
                    konto = data
                    confirmed = 0
                    
                # Upsert
                cursor.execute('''
                    INSERT INTO cache_konten (kunden_id, supplier, description, konto, confirmed)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(kunden_id, supplier, description) DO UPDATE SET 
                    konto = excluded.konto,
                    confirmed = excluded.confirmed
                ''', (kunden_id, supplier, desc, konto, confirmed))
            conn.commit()

    # --- Sync Status ---
    def get_sync_status(self, kunden_id: str, regel_typ: str) -> float:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT last_modified FROM sync_status WHERE kunden_id = ? AND regel_typ = ?', (kunden_id, regel_typ))
            row = cursor.fetchone()
            return row[0] if row else 0.0

    def set_sync_status(self, kunden_id: str, regel_typ: str, timestamp: float):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sync_status (kunden_id, regel_typ, last_modified)
                VALUES (?, ?, ?)
                ON CONFLICT(kunden_id, regel_typ) DO UPDATE SET last_modified = excluded.last_modified
            ''', (kunden_id, regel_typ, timestamp))
            conn.commit()

    # --- Kontenregeln ---
    def sync_rules(self, kunden_id: str, regel_typ: str, rules_df: pd.DataFrame):
        """Bulk insert rules using pandas to_sql."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM kontenregeln WHERE kunden_id = ?', (kunden_id,))
            if not rules_df.empty:
                # Ensure kunden_id is the sync group ID
                rules_df['kunden_id'] = kunden_id
                rules_df.to_sql('kontenregeln', conn, if_exists='append', index=False)
            conn.commit()
            
    def get_rules(self, kunden_id: str, sync_group: str) -> pd.DataFrame:
        with self.get_connection() as conn:
            return pd.read_sql_query('SELECT * FROM kontenregeln WHERE kunden_id = ?', conn, params=(kunden_id,))

    # --- UI Cache Editor Helpers ---
    def delete_all_cache(self, cache_type: str, kunden_id: str):
        table = "cache_analyse" if cache_type == "Sektorenanalyse" else "cache_konten"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'DELETE FROM {table} WHERE kunden_id = ?', (kunden_id,))
            conn.commit()

    def delete_cache_entry(self, cache_type: str, kunden_id: str, cache_key: str):
        if " | " in cache_key:
            parts = cache_key.split(" | ", 1)
            supplier = parts[0]
            desc = parts[1] if len(parts) > 1 else ""
        else:
            supplier = cache_key
            desc = ""
            
        table = "cache_analyse" if cache_type == "Sektorenanalyse" else "cache_konten"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'DELETE FROM {table} WHERE kunden_id = ? AND supplier = ? AND description = ?', 
                           (kunden_id, supplier, desc))
            conn.commit()

    # --- Migration von JSON -> SQLite ---
    def migrate_all_json_caches(self, base_dir):
        kunden_dir = os.path.join(base_dir, "Kunden")
        if not os.path.exists(kunden_dir):
            return
            
        for kunde in os.listdir(kunden_dir):
            nutzerdaten = os.path.join(kunden_dir, kunde, "Nutzerdaten")
            if not os.path.isdir(nutzerdaten):
                continue
                
            # Migrate Analyse
            analyse_json = os.path.join(nutzerdaten, "Analyse_Memory.json")
            if os.path.exists(analyse_json):
                try:
                    with open(analyse_json, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if data:
                        self.save_analyse_cache_batch(kunde, data)
                        print(f"Migrated Analyse Cache für Kunde: {kunde}")
                    # Rename to prevent double migration
                    os.rename(analyse_json, analyse_json + ".migrated")
                except Exception as e:
                    print(f"Fehler bei Migration Analyse_Memory für {kunde}: {e}")
                    
            # Migrate Konten
            konten_json = os.path.join(nutzerdaten, "Konten_Memory.json")
            if os.path.exists(konten_json):
                try:
                    with open(konten_json, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if data:
                        self.save_konten_cache_batch(kunde, data)
                        print(f"Migrated Konten Cache für Kunde: {kunde}")
                    os.rename(konten_json, konten_json + ".migrated")
                except Exception as e:
                    print(f"Fehler bei Migration Konten_Memory für {kunde}: {e}")

# Global instance getter
def get_db(base_dir=None):
    return DatabaseManager(base_dir)
