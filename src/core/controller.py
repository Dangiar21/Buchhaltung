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
        
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.templates_dir = os.path.join(self.project_root, "Systemdaten", "Templates")
        os.makedirs(self.templates_dir, exist_ok=True)

    def get_templates_dir(self):
        return self.templates_dir

    def get_available_templates(self):
        """Gibt eine sortierte Liste aller Vorlagennamen zurück."""
        templates = set()
        if os.path.exists(self.templates_dir):
            for fname in os.listdir(self.templates_dir):
                if (fname.startswith("ER_") or fname.startswith("AR_")) and fname.endswith(".txt"):
                    name = fname[3:-4].strip()
                    if name:
                        templates.add(name)
        result = sorted(list(templates))
        if not result:
            result = ["Standard"]
            self.ensure_template_files("Standard")
        return result

    def get_template_path(self, template_name, typ):
        """Gibt den Dateipfad zu einer Vorlagendatei zurück und stellt sicher, dass sie existiert."""
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', template_name).strip()
        filename = f"{typ}_{clean_name}.txt"
        file_path = os.path.join(self.templates_dir, filename)
        if not os.path.exists(file_path):
            os.makedirs(self.templates_dir, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                if typ == "ER":
                    f.write("- Konto 5000: Wareneinkauf\n- Konto 7000: Dienstleistungen\n")
                else:
                    f.write("- Konto 4000: Umsatzerlöse\n")
        return file_path

    def ensure_template_files(self, template_name):
        """Stellt sicher, dass sowohl ER als auch AR Vorlagendateien existieren."""
        for typ in ["ER", "AR"]:
            self.get_template_path(template_name, typ)

    def create_template(self, template_name, base_template=None):
        """Erstellt eine neue Kontenplan-Vorlage, optional basierend auf einer bestehenden."""
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', template_name).strip()
        if not clean_name:
            return False, "Der Vorlagenname darf nicht leer sein."
        
        er_path = os.path.join(self.templates_dir, f"ER_{clean_name}.txt")
        ar_path = os.path.join(self.templates_dir, f"AR_{clean_name}.txt")
        
        if os.path.exists(er_path) or os.path.exists(ar_path):
            return False, f"Eine Vorlage mit dem Namen '{clean_name}' existiert bereits."
            
        try:
            os.makedirs(self.templates_dir, exist_ok=True)
            if base_template and base_template in self.get_available_templates():
                base_er = self.get_template_path(base_template, "ER")
                base_ar = self.get_template_path(base_template, "AR")
                shutil.copy2(base_er, er_path)
                shutil.copy2(base_ar, ar_path)
            else:
                with open(er_path, "w", encoding="utf-8") as f:
                    f.write("- Konto 5000: Wareneinkauf\n- Konto 7000: Dienstleistungen\n")
                with open(ar_path, "w", encoding="utf-8") as f:
                    f.write("- Konto 4000: Umsatzerlöse\n")
            return True, clean_name
        except Exception as e:
            logger.error(f"Fehler beim Erstellen der Vorlage '{clean_name}': {e}")
            return False, str(e)

    def duplicate_template(self, source_name, new_name):
        return self.create_template(new_name, base_template=source_name)

    def rename_template(self, old_name, new_name):
        """Benennt eine Vorlage um."""
        clean_old = re.sub(r'[<>:"/\\|?*]', '_', old_name).strip()
        clean_new = re.sub(r'[<>:"/\\|?*]', '_', new_name).strip()
        if not clean_new:
            return False, "Der neue Vorlagenname darf nicht leer sein."
        if clean_old == clean_new:
            return True, clean_new
            
        new_er = os.path.join(self.templates_dir, f"ER_{clean_new}.txt")
        new_ar = os.path.join(self.templates_dir, f"AR_{clean_new}.txt")
        if os.path.exists(new_er) or os.path.exists(new_ar):
            return False, f"Eine Vorlage mit dem Namen '{clean_new}' existiert bereits."
            
        try:
            old_er = self.get_template_path(clean_old, "ER")
            old_ar = self.get_template_path(clean_old, "AR")
            shutil.move(old_er, new_er)
            shutil.move(old_ar, new_ar)
            return True, clean_new
        except Exception as e:
            logger.error(f"Fehler beim Umbenennen der Vorlage '{clean_old}' zu '{clean_new}': {e}")
            return False, str(e)

    def delete_template(self, template_name):
        """Löscht eine Vorlage. Mindestens eine Vorlage muss im System verbleiben."""
        all_templates = self.get_available_templates()
        if len(all_templates) <= 1:
            return False, "Die letzte verbleibende Vorlage kann nicht gelöscht werden."
            
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', template_name).strip()
        er_path = os.path.join(self.templates_dir, f"ER_{clean_name}.txt")
        ar_path = os.path.join(self.templates_dir, f"AR_{clean_name}.txt")
        
        try:
            if os.path.exists(er_path):
                os.remove(er_path)
            if os.path.exists(ar_path):
                os.remove(ar_path)
            return True, clean_name
        except Exception as e:
            logger.error(f"Fehler beim Löschen der Vorlage '{clean_name}': {e}")
            return False, str(e)


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
            
            if template_name:
                for typ in ["ER", "AR"]:
                    template_path = self.get_template_path(template_name, typ)
                    target_txt_path = os.path.join(info_nutzerdaten_dir, f"{typ}_Kontenplan.txt")
                    if os.path.exists(template_path):
                        shutil.copy2(template_path, target_txt_path)
                    else:
                        with open(target_txt_path, "w", encoding="utf-8") as f:
                            f.write("- Konto 0000: Unbekannt\n")
            elif ensure_konten_template:
                ensure_konten_template(info_nutzerdaten_dir)
            
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
