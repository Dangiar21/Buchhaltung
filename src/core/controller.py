import os
import re
import json
import shutil
import threading
import logging
import datetime
import concurrent.futures
from src.db.database import init_db, Kunde
from src.db.validators import ClientDataValidator
from pydantic import ValidationError

try:
    from Programme.Buchungen_erstellen.Buchung_KI import ensure_konten_template
except ImportError:
    ensure_konten_template = None
    
# Try importing module functions directly or passing them.
# The modules are currently in Programme. We'll import them via sys.path or absolute imports if added.
import sys
script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if script_dir not in sys.path:
    sys.path.append(script_dir)
sys.path.append(os.path.join(script_dir, 'Programme', 'Buchungen erstellen'))
sys.path.append(os.path.join(script_dir, 'Programme', 'XML zu Excel'))

sys.path.append(os.path.join(script_dir, 'Programme', 'KI_Training'))
sys.path.append(os.path.join(script_dir, 'Programme', 'CSV zu Excel'))

try:
    from BuchungenErstellen import run_conversion
except ImportError:
    run_conversion = None

try:
    from XMLzuExcel import run_conversion as run_xml_to_excel
except ImportError:
    run_xml_to_excel = None

try:
    from CSVzuExcel import run_conversion as run_csv_to_excel
except ImportError:
    run_csv_to_excel = None



try:
    import Buchung_KI
    from Buchung_KI import ensure_konten_template
except ImportError:
    Buchung_KI = None
    ensure_konten_template = None



logger = logging.getLogger(__name__)

class AppController:
    def __init__(self, base_kunden_dir):
        self.base_kunden_dir = base_kunden_dir
        if not os.path.exists(self.base_kunden_dir):
            os.makedirs(self.base_kunden_dir)
        db_path = os.path.join(self.base_kunden_dir, "kunden.db")
        self.session = init_db(db_path)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    def get_all_clients(self):
        try:
            results = self.session.query(Kunde.name).order_by(Kunde.name).all()
            return [r[0] for r in results]
        except Exception as e:
            logger.error(f"Fehler beim Laden der Kunden: {e}")
            return []

    def get_client_data(self, name):
        try:
            kunde = self.session.query(Kunde).filter_by(name=name).first()
            if kunde:
                return {
                    "Kundenname": kunde.name,
                    "Rechtsform": kunde.rechtsform,
                    "Beschreibung": kunde.beschreibung,
                    "Partita_IVA": kunde.partita_iva,
                    "Codice_Fiscale": kunde.codice_fiscale,
                    "Regime_Contabile": kunde.regime_contabile,
                    "Liquidazione_IVA": kunde.liquidazione_iva,
                    "Adresse": kunde.adresse,
                    "PEC": kunde.pec,
                    "SDI": kunde.sdi,
                    "IBAN": kunde.iban
                }
            return {}
        except Exception as e:
            logger.error(f"Fehler beim Laden der Kundendaten: {e}")
            return {}

    def get_dashboard_stats(self):
        try:
            client_count = self.session.query(Kunde).count()
            
            backup_dir = os.path.join(os.path.dirname(self.base_kunden_dir), "Backups")
            last_backup = "Nie"
            if os.path.exists(backup_dir):
                backups = [f for f in os.listdir(backup_dir) if f.endswith(".zip")]
                if backups:
                    backups.sort(key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)), reverse=True)
                    latest_backup = backups[0]
                    # Format timestamp
                    import time
                    mod_time = os.path.getmtime(os.path.join(backup_dir, latest_backup))
                    last_backup = time.strftime('%d.%m.%Y %H:%M', time.localtime(mod_time))
                    
            return {
                "client_count": client_count,
                "last_backup": last_backup
            }
        except Exception as e:
            logger.error(f"Fehler beim Laden der Dashboard-Stats: {e}")
            return {"client_count": 0, "last_backup": "Fehler"}

    def save_client(self, name_raw, is_edit, client_data, template_name):
        try:
            client_data_to_validate = client_data.copy()
            client_data_to_validate["Kundenname"] = name_raw
            ClientDataValidator(**client_data_to_validate)
        except ValidationError as e:
            error_msg = e.errors()[0]['msg']
            if "Value error, " in error_msg:
                error_msg = error_msg.replace("Value error, ", "")
            logger.error(f"Validierungsfehler: {error_msg}")
            return False, error_msg

        name = re.sub(r'[<>:"/\\|?*]', '_', name_raw)
        client_dir = os.path.join(self.base_kunden_dir, name)
        info_nutzerdaten_dir = os.path.join(client_dir, "Nutzerdaten")
        
        if is_edit:
            success_msg = f"\\n=> Kunde '{name}' erfolgreich aktualisiert!"
        else:
            if os.path.exists(client_dir) or self.session.query(Kunde).filter_by(name=name).first():
                logger.error(f"Kunde '{name}' existiert bereits!")
                return False, name
                
            os.makedirs(client_dir, exist_ok=True)
            os.makedirs(os.path.join(client_dir, "Rechnungen"), exist_ok=True)
            os.makedirs(os.path.join(client_dir, "Buchhaltung"), exist_ok=True)
            os.makedirs(os.path.join(client_dir, "Analyse"), exist_ok=True)
            os.makedirs(info_nutzerdaten_dir, exist_ok=True)
            
            if ensure_konten_template:
                ensure_konten_template(info_nutzerdaten_dir)
            
            if template_name:
                for typ in ["ER", "AR"]:
                    template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "Systemdaten", "Templates", f"{typ}_{template_name}.txt")
                    target_txt_path = os.path.join(info_nutzerdaten_dir, f"{typ}_Kontenplan.txt")
                    if os.path.exists(template_path):
                        shutil.copy2(template_path, target_txt_path)
                    else:
                        with open(target_txt_path, "w", encoding="utf-8") as f:
                            f.write("HINTERGRUND:\n- Konto 0000: Unbekannt\n\nREGELN:\n")
            
            success_msg = f"\n=> Kunde '{name}' erfolgreich angelegt!"

        try:
            kunde = self.session.query(Kunde).filter_by(name=name).first()
            if not kunde:
                kunde = Kunde(name=name)
                self.session.add(kunde)
            
            kunde.rechtsform = client_data.get("Rechtsform", "")
            kunde.beschreibung = client_data.get("Beschreibung", "")
            kunde.partita_iva = client_data.get("Partita_IVA", "")
            kunde.codice_fiscale = client_data.get("Codice_Fiscale", "")
            kunde.regime_contabile = client_data.get("Regime_Contabile", "")
            kunde.liquidazione_iva = client_data.get("Liquidazione_IVA", "")
            kunde.adresse = client_data.get("Adresse", "")
            kunde.pec = client_data.get("PEC", "")
            kunde.sdi = client_data.get("SDI", "")
            kunde.iban = client_data.get("IBAN", "")
            
            self.session.commit()
            logger.info(success_msg)
            return True, name
        except Exception as e:
            self.session.rollback()
            logger.error(f"Fehler beim Speichern der Kundendaten in der DB: {e}")
            return False, name

    def create_backup(self, on_finish=None):
        try:
            backup_dir = os.path.join(os.path.dirname(self.base_kunden_dir), "Backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_filename = f"Backup_Kunden_{timestamp}"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            logger.info(f"\\nStarte Backup nach {backup_dir}... Bitte warten.")
            
            def _backup_thread():
                try:
                    shutil.make_archive(backup_path, 'zip', self.base_kunden_dir)
                    logger.info(f"\\n✅ Backup erfolgreich erstellt unter:\\n{backup_path}.zip")
                except Exception as e:
                    logger.error(f"\\n❌ Fehler beim Backup: {e}")
                    raise e
                    
            future = self.executor.submit(_backup_thread)
            if on_finish:
                future.add_done_callback(lambda f: on_finish())
            # Add a generic error handler
            future.add_done_callback(self._future_error_handler)
            return True
        except Exception as e:
            logger.error(f"Fehler beim Initialisieren des Backups: {e}")
            return False

    def cancel_task(self):
        logger.info("\\n[!] Abbruch angefordert! Die aktuelle Verarbeitung wird nach dem laufenden Batch beendet und gespeichert.")
        if Buchung_KI:
            Buchung_KI.cancel_requested = True


    def process_paths(self, paths, active_tool, current_client, on_start=None, on_finish=None):
        if not current_client or current_client == "Kein Kunde":
            logger.error("\\n❌ Bitte wähle zuerst einen Kunden in der Seitenleiste aus!")
            return
            
        logger.info(f"\\n--- Starte Verarbeitung für Kunde: {current_client} ({len(paths)} Elemente erkannt) ---")
        client_dir = os.path.join(self.base_kunden_dir, current_client)
        output_dir = os.path.join(client_dir, "Buchhaltung")
        nutzerdaten_dir = os.path.join(client_dir, "Nutzerdaten")
        
        func = None
        if active_tool == 'buchung_erstellen':
            func = run_conversion
        elif active_tool == 'xml_to_excel':
            func = run_xml_to_excel
        elif active_tool == 'csv_to_excel':
            func = run_csv_to_excel

                
        if func:
            future = self.executor.submit(self._run_task_thread, paths, output_dir, nutzerdaten_dir, func, on_start)
            
            # Chain the finish callback and error handler
            def done_callback(f):
                if on_finish:
                    # Execute on_finish (which is a GUI callback) - ideally should be threaded back to main thread by UI, but tkinter allows basic stuff
                    on_finish()
                self._future_error_handler(f)
                
            future.add_done_callback(done_callback)
        else:
            logger.error(f"Fehler: Tool {active_tool} konnte nicht geladen werden.")

    def _future_error_handler(self, future):
        try:
            future.result()
        except Exception as e:
            logger.error(f"\\n❌ Unerwarteter Thread-Fehler: {e}")

    def _run_task_thread(self, paths, output_dir, nutzerdaten_dir, func, on_start):
        try:
            if Buchung_KI:
                Buchung_KI.cancel_requested = False

                
            if on_start:
                on_start()

            func(paths, output_dir=output_dir, nutzerdaten_dir=nutzerdaten_dir)
            
            if Buchung_KI and getattr(Buchung_KI, 'cancel_requested', False):
                logger.warning("\\n⚠️ Verarbeitung wurde vorzeitig abgebrochen. Die bisherigen Ergebnisse wurden gespeichert.")
            else:
                logger.info("\\n✅ Verarbeitung abgeschlossen.")
                
        except Exception as e:
            logger.error(f"\\n❌ Ein unerwarteter Fehler ist in der Task-Ausführung aufgetreten: {e}")
            raise e
