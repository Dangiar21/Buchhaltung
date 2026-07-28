from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout, QGraphicsDropShadowEffect
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt
import qtawesome as qta

class DashboardFrame(QWidget):
    def __init__(self, parent, config_manager, controller):
        super().__init__(parent)
        self.config_manager = config_manager
        self.controller = controller
        
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
        body_layout.setContentsMargins(20, 40, 20, 40)
        
        layout.addWidget(header)
        layout.addWidget(body)
        
        return card, body

    def refresh(self):
        stats = self.controller.get_dashboard_stats()
        self.lbl_client_count.setText(str(stats.get("client_count", 0)))
        self.lbl_last_backup.setText(stats.get("last_backup", "Nie"))
        
        recent = self.config_manager.get("recent_clients", [])
        if recent:
            self.lbl_recent_clients.setText("\n".join(recent))
        else:
            self.lbl_recent_clients.setText("Keine")
