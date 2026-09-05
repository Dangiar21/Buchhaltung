import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QGridLayout, QGraphicsDropShadowEffect, QPushButton, QMessageBox,
    QDialog, QListWidget, QListWidgetItem, QFileDialog
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt, pyqtSignal
import qtawesome as qta
from src.core.translations import translator

class RestoreBackupDialog(QDialog):
    def __init__(self, parent, controller, config_manager):
        super().__init__(parent)
        self.controller = controller
        self.config_manager = config_manager
        self.lang = self.config_manager.get("language", "de")
        self.selected_backup_path = None
        
        self.setWindowTitle(translator.get(self.lang, "restore_dialog_title", "Backup wiederherstellen"))
        self.resize(550, 400)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel(translator.get(self.lang, "restore_dialog_title", "Backup wiederherstellen"))
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        desc = QLabel(translator.get(self.lang, "restore_dialog_desc", "Wähle ein Backup aus, um den Datenstand (Kunden, Rechnungen, KI-Cache) wiederherzustellen:"))
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("QListWidget { font-size: 11pt; padding: 5px; } QListWidget::item { padding: 8px; border-bottom: 1px solid #333333; }")
        layout.addWidget(self.list_widget)
        
        self.backups = self.controller.get_available_backups()
        for b in self.backups:
            size_str = f"{b['size_kb']:.1f} KB" if b['size_kb'] < 1024 else f"{b['size_kb']/1024.0:.1f} MB"
            item_text = f"📦 {b['filename']}  ({b['formatted_time']} - {size_str})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, b['path'])
            self.list_widget.addItem(item)
            
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            
        btn_browse = QPushButton(translator.get(self.lang, "btn_browse_backup", "📁 Andere ZIP-Datei auswählen..."))
        btn_browse.setObjectName("ToolBtnSecondary")
        btn_browse.clicked.connect(self.browse_external)
        layout.addWidget(btn_browse)
        
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        
        self.btn_confirm = QPushButton(translator.get(self.lang, "btn_restore", "Wiederherstellen"))
        self.btn_confirm.setObjectName("ToolBtn")
        self.btn_confirm.clicked.connect(self.accept_selection)
        btn_box.addWidget(self.btn_confirm)
        
        layout.addLayout(btn_box)

    def browse_external(self):
        backup_dir = os.path.join(getattr(self.controller, 'base_dir', '.'), "Backups")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Backup-ZIP auswählen",
            backup_dir if os.path.exists(backup_dir) else "",
            "ZIP-Dateien (*.zip)"
        )
        if file_path:
            self.selected_backup_path = file_path
            self.accept()

    def accept_selection(self):
        current_item = self.list_widget.currentItem()
        if not current_item and not self.selected_backup_path:
            QMessageBox.warning(self, "Keine Auswahl", "Bitte wähle ein Backup aus der Liste aus oder wähle eine externe ZIP-Datei.")
            return
        if current_item:
            self.selected_backup_path = current_item.data(Qt.ItemDataRole.UserRole)
        self.accept()

class DashboardFrame(QWidget):
    backup_finished_signal = pyqtSignal(bool, str)
    restore_finished_signal = pyqtSignal(bool, str)

    def __init__(self, parent, config_manager, controller):
        super().__init__(parent)
        self.config_manager = config_manager
        self.controller = controller
        self.backup_finished_signal.connect(self._on_backup_finished)
        self.restore_finished_signal.connect(self._on_restore_finished)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 40, 40, 40)
        self.main_layout.setSpacing(30)
        
        title = QLabel("Dashboard Overview")
        title.setObjectName("DashboardTitle")
        self.main_layout.addWidget(title)
        
        # Stats container
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(25)
        
        self.card_clients, body_clients = self.create_card("Gesamte Kunden", "Blue")
        self.lbl_client_count = QLabel("-")
        self.lbl_client_count.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        self.lbl_client_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_clients.layout().addWidget(self.lbl_client_count)
        stats_layout.addWidget(self.card_clients)
        
        self.card_backup, body_backup = self.create_card("Letztes Backup", "Blue")
        self.lbl_last_backup = QLabel("-")
        self.lbl_last_backup.setFont(QFont("Segoe UI", 18, QFont.Weight.Medium))
        self.lbl_last_backup.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_backup.layout().addWidget(self.lbl_last_backup)

        lang = self.config_manager.get("language", "de")
        self.btn_create_backup = QPushButton(translator.get(lang, "btn_create_backup", "Jetzt Backup erstellen"))
        self.btn_create_backup.setObjectName("ToolBtn")
        self.btn_create_backup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_create_backup.setIcon(qta.icon('fa5s.save', color='white'))
        self.btn_create_backup.clicked.connect(self.trigger_backup)
        body_backup.layout().addWidget(self.btn_create_backup)

        self.btn_restore_backup = QPushButton(translator.get(lang, "btn_restore_backup", "Backup wiederherstellen"))
        self.btn_restore_backup.setObjectName("ToolBtnSecondary")
        self.btn_restore_backup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_restore_backup.setIcon(qta.icon('fa5s.history', color='#3b82f6'))
        self.btn_restore_backup.clicked.connect(self.trigger_restore)
        body_backup.layout().addWidget(self.btn_restore_backup)
        stats_layout.addWidget(self.card_backup)
        
        self.card_recent, body_recent = self.create_card("Zuletzt verwendet", "Green")
        self.lbl_recent_clients = QLabel("-")
        self.lbl_recent_clients.setFont(QFont("Segoe UI", 11))
        self.lbl_recent_clients.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        body_recent.layout().addWidget(self.lbl_recent_clients)
        stats_layout.addWidget(self.card_recent)
        
        self.main_layout.addLayout(stats_layout)
        self.main_layout.addStretch()
        
    def create_card(self, title_text, color_theme="Blue"):
        card = QFrame()
        card.setObjectName("DashboardCard")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = QFrame()
        header.setObjectName(f"CardHeader{color_theme}")
        header.setFixedHeight(50)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 0, 15, 0)
        
        icon_label = QLabel()
        if "Kunden" in title_text: icon_label.setPixmap(qta.icon('fa5s.users', color='white').pixmap(20, 20))
        elif "Backup" in title_text: icon_label.setPixmap(qta.icon('fa5s.cloud-upload-alt', color='white').pixmap(20, 20))
        else: icon_label.setPixmap(qta.icon('fa5s.history', color='white').pixmap(20, 20))
        header_layout.addWidget(icon_label)
        
        lbl_title = QLabel(title_text)
        lbl_title.setObjectName("CardTitle")
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        
        body = QFrame()
        body.setObjectName("CardBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 25, 20, 25)
        body_layout.setSpacing(12)
        
        layout.addWidget(header)
        layout.addWidget(body)
        
        return card, body

    def trigger_backup(self):
        lang = self.config_manager.get("language", "de")
        self.btn_create_backup.setEnabled(False)
        self.btn_create_backup.setText(translator.get(lang, "backup_in_progress", "Erstelle Backup..."))
        self.btn_create_backup.setIcon(qta.icon('fa5s.spinner', color='white', animation=qta.Spin(self.btn_create_backup)))
        
        def _on_done(success, res):
            self.backup_finished_signal.emit(success, str(res))
            
        self.controller.create_backup(on_finish=_on_done)

    def _on_backup_finished(self, success, res):
        lang = self.config_manager.get("language", "de")
        self.btn_create_backup.setEnabled(True)
        self.btn_create_backup.setText(translator.get(lang, "btn_create_backup", "Jetzt Backup erstellen"))
        self.btn_create_backup.setIcon(qta.icon('fa5s.save', color='white'))
        self.refresh()
        
        if success:
            filename = os.path.basename(res)
            msg_prefix = translator.get(lang, "backup_success", "Das Backup wurde erfolgreich erstellt unter:")
            QMessageBox.information(
                self,
                "Backup erfolgreich",
                f"✅ {msg_prefix}\n\n{filename}\n\n(Gespeichert im Ordner 'Backups')"
            )
        else:
            QMessageBox.critical(
                self,
                "Backup-Fehler",
                f"❌ Fehler beim Erstellen des Backups:\n\n{res}"
            )

    def trigger_restore(self):
        dialog = RestoreBackupDialog(self, self.controller, self.config_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_backup_path:
            zip_path = dialog.selected_backup_path
            lang = self.config_manager.get("language", "de")
            filename = os.path.basename(zip_path)
            
            confirm_title = translator.get(lang, "restore_confirm_title", "Achtung: Backup wiederherstellen?")
            confirm_msg = translator.get(
                lang, 
                "restore_confirm_msg", 
                "Möchtest du wirklich den Datenstand aus folgendem Backup wiederherstellen?\n\n{filename}\n\n⚠️ ACHTUNG: Alle aktuellen Daten (Rechnungen, Kunden, gelernter KI-Cache) werden dabei durch den Stand des Backups überschrieben!"
            ).format(filename=filename)
            
            reply = QMessageBox.warning(
                self,
                confirm_title,
                confirm_msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.btn_create_backup.setEnabled(False)
                self.btn_restore_backup.setEnabled(False)
                self.btn_restore_backup.setText(translator.get(lang, "restore_in_progress", "Stelle Backup wieder her..."))
                self.btn_restore_backup.setIcon(qta.icon('fa5s.spinner', color='#3b82f6', animation=qta.Spin(self.btn_restore_backup)))
                
                def _on_done(success, res):
                    self.restore_finished_signal.emit(success, str(res))
                    
                self.controller.restore_backup(zip_path, on_finish=_on_done)

    def _on_restore_finished(self, success, res):
        lang = self.config_manager.get("language", "de")
        self.btn_create_backup.setEnabled(True)
        self.btn_restore_backup.setEnabled(True)
        self.btn_restore_backup.setText(translator.get(lang, "btn_restore_backup", "Backup wiederherstellen"))
        self.btn_restore_backup.setIcon(qta.icon('fa5s.history', color='#3b82f6'))
        
        self.refresh()
        
        # Kundenliste im Hauptfenster aktualisieren falls verfügbar
        main_win = self.window()
        if hasattr(main_win, 'refresh_clients'):
            try:
                main_win.refresh_clients()
            except Exception:
                pass
                
        if success:
            filename = os.path.basename(res)
            msg_prefix = translator.get(lang, "restore_success", "Das Backup wurde erfolgreich wiederhergestellt!")
            QMessageBox.information(
                self,
                "Wiederherstellung erfolgreich",
                f"✅ {msg_prefix}\n\nStand wiederhergestellt aus:\n{filename}"
            )
        else:
            msg_prefix = translator.get(lang, "restore_error", "Fehler bei der Wiederherstellung:")
            QMessageBox.critical(
                self,
                "Wiederherstellungs-Fehler",
                f"❌ {msg_prefix}\n\n{res}"
            )

    def refresh(self):
        stats = self.controller.get_dashboard_stats()
        self.lbl_client_count.setText(str(stats.get("client_count", 0)))
        self.lbl_last_backup.setText(stats.get("last_backup", "Nie"))
        
        lang = self.config_manager.get("language", "de")
        if hasattr(self, 'btn_create_backup'):
            self.btn_create_backup.setText(translator.get(lang, "btn_create_backup", "Jetzt Backup erstellen"))
        if hasattr(self, 'btn_restore_backup'):
            self.btn_restore_backup.setText(translator.get(lang, "btn_restore_backup", "Backup wiederherstellen"))
            
        recent = self.config_manager.get("recent_clients", [])
        if recent:
            self.lbl_recent_clients.setText("\n".join(recent))
        else:
            self.lbl_recent_clients.setText("Keine")
