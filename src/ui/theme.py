import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor

def get_light_palette():
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f0f4f8"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#2c3e50"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#2c3e50"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#2c3e50"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#2c3e50"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#3a7ebf"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#3a7ebf"))
    palette.setColor(QPalette.ColorRole.Midlight, QColor("#e2e8f0"))
    palette.setColor(QPalette.ColorRole.Mid, QColor("#cbd5e1"))
    palette.setColor(QPalette.ColorRole.Dark, QColor("#94a3b8"))
    return palette

def get_dark_palette():
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#18181b"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1f1f23"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#27272a"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#27272a"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#27272a"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#3a7ebf"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#60a5fa"))
    palette.setColor(QPalette.ColorRole.Midlight, QColor("#3f3f46"))
    palette.setColor(QPalette.ColorRole.Mid, QColor("#52525b"))
    palette.setColor(QPalette.ColorRole.Dark, QColor("#71717a"))
    return palette

def apply_theme(qapp=None, mode="Light"):
    if qapp is None:
        qapp = QApplication.instance()
    if qapp is None:
        return

    is_dark = (mode == "Dark")
    palette = get_dark_palette() if is_dark else get_light_palette()
    qapp.setPalette(palette)
    
    style_file = "style_dark.qss" if is_dark else "style.qss"
    ui_dir = os.path.dirname(os.path.abspath(__file__))
    style_path = os.path.join(ui_dir, style_file)
    assets_dir = os.path.join(ui_dir, "assets").replace("\\", "/")
    
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            qss = f.read()
        qss = qss.replace("{{ASSETS_DIR}}", assets_dir)
        qapp.setStyleSheet(qss)
