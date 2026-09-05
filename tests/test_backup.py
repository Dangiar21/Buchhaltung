import unittest
import os
import tempfile
import shutil
import zipfile
import sys
import threading

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)

from src.core.controller import AppController

class TestBackup(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Create minimal directory structure
        self.kunden_dir = os.path.join(self.test_dir, "Kunden")
        os.makedirs(self.kunden_dir, exist_ok=True)
            
        self.sys_dir = os.path.join(self.test_dir, "Systemdaten")
        os.makedirs(self.sys_dir, exist_ok=True)
        with open(os.path.join(self.sys_dir, "buchhaltung.db"), "w") as f:
            f.write("test_buchhaltung_db")
            
        with open(os.path.join(self.test_dir, "config.json"), "w") as f:
            f.write("{\"language\": \"de\"}")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_backup_comprehensive(self):
        controller = AppController(self.kunden_dir)
        done_event = threading.Event()
        callback_result = {}

        def _on_finish(success, res):
            callback_result["success"] = success
            callback_result["res"] = res
            done_event.set()

        started = controller.create_backup(on_finish=_on_finish)
        self.assertTrue(started)

        # Wait for thread to complete
        finished = done_event.wait(timeout=5)
        self.assertTrue(finished, "Backup callback did not fire in time")
        self.assertTrue(callback_result.get("success"), f"Backup failed: {callback_result.get('res')}")

        backup_file = callback_result.get("res")
        self.assertTrue(os.path.exists(backup_file), f"File {backup_file} does not exist")
        self.assertTrue(backup_file.endswith(".zip"))

        # Verify ZIP contents
        with zipfile.ZipFile(backup_file, 'r') as zf:
            namelist = zf.namelist()
            # Normalize path separators for cross-platform checking
            norm_names = [n.replace("\\", "/") for n in namelist]
            self.assertIn("Kunden/kunden.db", norm_names)
            self.assertIn("Systemdaten/buchhaltung.db", norm_names)
            self.assertIn("config.json", norm_names)

        # Check dashboard stats detects the backup
        stats = controller.get_dashboard_stats()
        self.assertNotEqual(stats.get("last_backup"), "Nie")

    def test_get_available_backups_and_restore(self):
        controller = AppController(self.kunden_dir)

        # 1. Create a backup first
        done_event = threading.Event()
        callback_res = {}
        def _on_finish_backup(success, res):
            callback_res["success"] = success
            callback_res["res"] = res
            done_event.set()

        controller.create_backup(on_finish=_on_finish_backup)
        done_event.wait(timeout=5)
        self.assertTrue(callback_res.get("success"))
        backup_zip = callback_res.get("res")

        # 2. Check get_available_backups
        backups = controller.get_available_backups()
        self.assertGreaterEqual(len(backups), 1)
        self.assertEqual(backups[0]["path"], backup_zip)

        # 3. Modify a file to simulate data change
        test_file = os.path.join(self.sys_dir, "buchhaltung.db")
        with open(test_file, "w") as f:
            f.write("MODIFIED_DATA")

        with open(test_file, "r") as f:
            self.assertEqual(f.read(), "MODIFIED_DATA")

        # 4. Restore the backup
        restore_event = threading.Event()
        restore_res = {}
        def _on_finish_restore(success, res):
            restore_res["success"] = success
            restore_res["res"] = res
            restore_event.set()

        controller.restore_backup(backup_zip, on_finish=_on_finish_restore)
        restore_event.wait(timeout=5)
        self.assertTrue(restore_res.get("success"))

        # 5. Verify data was restored
        with open(test_file, "r") as f:
            self.assertEqual(f.read(), "test_buchhaltung_db")

if __name__ == '__main__':
    unittest.main()
