# 📚 Buchhaltung & Rechnungs-Management

Ein intelligentes, automatisiertes Buchhaltungsprogramm zur Verwaltung, Analyse und KI-gestützten Kontierung von elektronischen Rechnungen (XML/P7M).

## 🚀 Funktionen
- **Kundenverwaltung:** Strukturierte Ablage für beliebig viele Mandanten.
- **Automatisierte Kontierung:** Ein hybrides Regelsystem weist Rechnungen automatisch Konten zu (basiert auf Kunden- und globalen Regeln).
- **KI-Integration:** Unbekannte Rechnungen werden blitzschnell durch Google Gemini (KI) analysiert und dem passenden Konto zugewiesen (inkl. automatischer Deduplizierung).
- **Individuelle Kontenpläne:** Jeder Kunde kann einen eigenen, flexiblen KI-Kontenplan in seinem Ordner verwalten.
- **XML Preview:** Integrierte Vorschau für komplexe, elektronische Rechnungen (XML/P7M).

## ⚙️ Installation & Setup auf einem neuen PC (WICHTIG!)

Wenn du dieses Projekt auf einen neuen PC oder Laptop klonst, beachte bitte unbedingt die folgenden Schritte, da sensible Daten aus Sicherheitsgründen **nicht** auf GitHub gespeichert sind.

### 1. Bibliotheken installieren
Führe nach dem Klonen/Herunterladen die Datei **`install_dependencies.bat`** per Doppelklick aus. Sie installiert alle notwendigen Python-Module (wie `pandas`, `customtkinter` und `google-genai`).

### 2. Gemini API-Key hinterlegen
Der API-Schlüssel für die Künstliche Intelligenz darf niemals öffentlich im Internet stehen und wurde daher von Git ignoriert.
- Erstelle im Hauptverzeichnis einen Ordner namens `Systemdaten` (falls nicht vorhanden).
- Erstelle darin eine Textdatei namens **`gemini_api_key.txt`**.
- Füge deinen persönlichen Google Gemini API-Schlüssel (z.B. `AQ...`) als Text in diese Datei ein.

### 3. Kunden & Rechnungsdaten
Aus Datenschutzgründen werden **keine echten Rechnungen oder Kundendaten** auf GitHub hochgeladen. Der Ordner `Kunden` existiert zwar als leere Hülle, enthält aber keine deiner privaten Daten.
- Wenn du das Programm startest, ist die Kundenliste anfangs leer.
- Du kannst entweder über die Schaltfläche **"+ Neuer Kunde"** frisch starten oder deinen existierenden, echten `Kunden`-Ordner von deinem alten PC manuell (z.B. per USB-Stick) in das Hauptverzeichnis kopieren.

## 💻 Start des Programms
Starte die Hauptanwendung durch Ausführen der Datei:
**`BuchhaltungGUI.py`**
