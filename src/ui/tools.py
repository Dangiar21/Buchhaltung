import os
import sys
import subprocess
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextEdit, QProgressBar, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.core.translations import translator

logger = logging.getLogger(__name__)

class DropZoneFrame(QFrame):
    def __init__(self, parent, app, tool_id):
        super().__init__(parent)
        self.app = app
        self.tool_id = tool_id
        self.setAcceptDrops(True)
        
        # Styling
        self.setObjectName("DropZone")
        self.setStyleSheet("""
            #DropZone {
                background-color: palette(alternate-base);
                border: 2px dashed palette(mid);
                border-radius: 15px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(Qt.GlobalColor.black)
        shadow.setOffset(0, 4)
        # self.setGraphicsEffect(shadow)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self.setStyleSheet("""
                #DropZone {
                    background-color: #e4f0fa;
                    border: 2px dashed #3a7ebf;
                    border-radius: 15px;
                }
            """)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            #DropZone {
                background-color: #f8fafc;
                border: 2px dashed #cbd5e1;
                border-radius: 15px;
            }
        """)

    def dropEvent(self, event):
        self.setStyleSheet("""
            #DropZone {
                background-color: #f8fafc;
                border: 2px dashed #cbd5e1;
                border-radius: 15px;
            }
        """)
        paths = []
        for url in event.mimeData().urls():
            paths.append(url.toLocalFile())
        if paths:
            self.app.process_paths(paths, tool_id=self.tool_id)


def build_tool_frame(parent_frame, app, tool_id, has_setup=False):
    layout = QVBoxLayout(parent_frame)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(15)

    drop_frame = DropZoneFrame(parent_frame, app, tool_id)
    drop_layout = QVBoxLayout(drop_frame)
    drop_layout.setContentsMargins(20, 40, 20, 40)
    
    lbl_key = 'drop_label_csv' if tool_id == 'csv_to_excel' else 'drop_label'
    drop_label = QLabel(translator.get(app.lang, lbl_key))
    font = QFont()
    font.setPointSize(16)
    drop_label.setFont(font)
    drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    drop_layout.addWidget(drop_label)
    
    btn_layout = QHBoxLayout()
    btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    btn_files = QPushButton(translator.get(app.lang, 'btn_files'))
    btn_files.setObjectName("ToolBtn")
    btn_files.clicked.connect(lambda: app.select_files(tool_id))
    btn_layout.addWidget(btn_files)
    
    btn_folder = QPushButton(translator.get(app.lang, 'btn_folder'))
    btn_folder.setObjectName("ToolBtnSecondary")
    btn_folder.clicked.connect(lambda: app.select_folder(tool_id))
    btn_layout.addWidget(btn_folder)
    
    btn_setup = None
    if has_setup:
        def open_setup():
            if not app.current_client or app.current_client == "Kein Kunde":
                logger.error("\n❌ Bitte wähle zuerst einen Kunden in der Seitenleiste aus!")
                return
            client_dir = os.path.join(app.controller.base_kunden_dir, app.current_client)
            nutzerdaten_dir = os.path.join(client_dir, "Nutzerdaten")
            setup_path = os.path.join(nutzerdaten_dir, "Analyse_Setup.xlsx")
            
            try:
                import Analyse_Config
                Analyse_Config.ensure_setup_file(nutzerdaten_dir)
            except ImportError:
                pass
                
            logger.info(f"Öffne {setup_path}...")
            if os.name == 'nt' or sys.platform == 'win32':
                os.startfile(setup_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', setup_path], check=True)
            else:
                subprocess.run(['xdg-open', setup_path], check=True)
                
        btn_setup = QPushButton("Kategorien-Setup öffnen")
        btn_setup.setStyleSheet("background-color: #c85a17; color: white;")
        btn_setup.clicked.connect(open_setup)
        btn_layout.addWidget(btn_setup)
        
    btn_cancel = QPushButton("Abbrechen & Speichern")
    btn_cancel.setStyleSheet("background-color: red; color: white;")
    btn_cancel.clicked.connect(app.controller.cancel_task)
    btn_cancel.hide()
    btn_layout.addWidget(btn_cancel)

    drop_layout.addLayout(btn_layout)
    layout.addWidget(drop_frame, stretch=2)

    log_textbox = QTextEdit()
    log_textbox.setReadOnly(True)
    layout.addWidget(log_textbox, stretch=1)

    progress_bar = QProgressBar()
    progress_bar.setRange(0, 100)
    progress_bar.setValue(0)
    layout.addWidget(progress_bar)

    # We need to monkey-patch configure methods for compatibility with main_window if needed,
    # or just fix main_window.py to use standard Qt methods. Let's fix main_window.py directly.
    return drop_label, btn_files, btn_folder, btn_cancel, log_textbox, progress_bar
