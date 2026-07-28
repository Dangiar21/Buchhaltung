import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
sys.path.append(os.path.join(script_dir, 'Programme', 'Buchungen erstellen'))
sys.path.append(os.path.join(script_dir, 'Programme', 'XML zu Excel'))
sys.path.append(os.path.join(script_dir, 'Programme', 'Analyse erstellen'))
sys.path.append(os.path.join(script_dir, 'Programme', 'KI_Training'))
sys.path.append(os.path.join(script_dir, 'Programme', 'CSV zu Excel'))

from src.ui.main_window import BuchhaltungApp
from PyQt6.QtWidgets import QApplication

if __name__ == "__main__":
    qapp = QApplication(sys.argv)
    app = BuchhaltungApp()
    app.show()
    sys.exit(qapp.exec())
