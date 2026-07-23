# 📚 Buchhaltung & Rechnungs-Management

Ein intelligentes, automatisiertes Buchhaltungsprogramm zur Verwaltung, Auswertung und KI-gestützten Kontierung von elektronischen Rechnungen (XML/P7M).

## 🚀 Funktionen
- **Kundenverwaltung:** Strukturierte Ablage für beliebig viele Mandanten mit automatischer Speicherung des zuletzt genutzten Kunden.

- **XML zu Excel:** Schnellkonvertierung von Rechnungsordnern in übersichtliche Excel-Tabellen.
- **Automatisierte Kontierung:** Ein hybrides Regelsystem weist Rechnungen automatisch Konten zu (basiert auf kunden- und globalen Regeln).
- **KI-Integration & Deduplizierung:** Unbekannte Rechnungen werden durch hochpräzise Llama- & GPT-Modelle via Groq (KI) analysiert und dem passenden Konto zugewiesen. Ergebnisse werden lokal gecached (`Analyse_Memory.json` / `Konten_Memory.json`), um API-Kosten zu sparen und schnelle Durchläufe zu ermöglichen.
- **Sektorenanalyse (NEU):** KI-gestützte, hochgradig anpassbare Auswertungen für Sektorenstudien (z. B. Fleischart/Bio-Anteil beim Metzger, Ersatzteile beim Mechaniker). Die Auswertung erfolgt über einfache Excel-Kategorien-Setups (`Analyse_Setup.xlsx`) und injiziert die Ergebnisse direkt in anpassbare Dashboard-Templates (`Dashboard_Template.xlsx`).
- **Sicher & Robust:** Schutz vor XXE-Angriffen durch `defusedxml`, ASN.1 Krypto-Entschlüsselung für P7M-Dateien (`asn1crypto`) und automatische Retry-Fallbacks bei Limit-Auslastungen (429 Rate Limits).

## ⚙️ Installation & Setup auf einem neuen PC

Wenn du dieses Projekt auf einen neuen PC klonst, beachte bitte die folgenden Schritte:

### 1. Bibliotheken installieren
Führe nach dem Klonen die Datei **`install_dependencies.bat`** per Doppelklick aus. Sie installiert alle notwendigen Python-Bibliotheken (u. a. `pandas`, `customtkinter`, `groq`, `defusedxml`, `python-dotenv`).

### 2. Groq API-Key hinterlegen
Der API-Schlüssel für die Künstliche Intelligenz darf niemals öffentlich stehen und wird von Git ignoriert.
- Erstelle im Ordner `Systemdaten` eine Datei namens **`groq_key.env`** (oder `.env` im Hauptverzeichnis).
- Trage darin deinen API-Schlüssel ein:
  ```env
  GROQ_API_KEY=dein_persoenlicher_api_key
  ```
- *Alternativ:* Eine reine Textdatei `Systemdaten/groq_api_key.txt` mit dem Key wird als Fallback ebenfalls unterstützt.

### 3. Kunden & Rechnungsdaten
Aus Datenschutzgründen werden **keine echten Rechnungen oder Kundendaten** auf GitHub hochgeladen.
- Nach dem Start kannst du über die Schaltfläche **"+ Neuer Kunde"** neue Mandanten anlegen.
- Oder du kopierst deine bestehenden Kundenordner aus dem Backup direkt in das Verzeichnis `Kunden/`.

## 💻 Start des Programms
Starte die Hauptanwendung durch Ausführen der Datei:
**`BuchhaltungGUI.py`**
