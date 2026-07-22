import pandas as pd
import csv

import os

def export_to_bpoint_csv(df, output_path):
    """
    Exportiert einen DataFrame in ein B Point-kompatibles CSV-Format.
    """
    if df.empty:
        print("B Point Export übersprungen: DataFrame ist leer.")
        return

    # Arbeite auf einer Kopie, um das Original-Excel-Format nicht zu verändern
    df_export = df.copy()

    # 1. Spaltenstruktur (Mapping) - Platzhalter
    # B Point erwartet wahrscheinlich ein spezifisches Mapping. 
    # Sobald das Mapping bekannt ist, kann es hier aktiviert werden:
    # mapping = {
    #     'Datum': 'DATA_REG',
    #     'Conto': 'CONTO',
    #     'Gesamtpreis': 'IMPORTO',
    #     # ... weitere Mappings ...
    # }
    # df_export.rename(columns=mapping, inplace=True)

    # 1. Text-Bereinigung (String-Spalten)
    # NaN/None zu leeren Strings
    df_export = df_export.fillna('')
    
    # Identifiziere alle Text-Spalten
    string_cols = df_export.select_dtypes(include=['object', 'string']).columns
    for col in string_cols:
        # Semikolons durch Komma ersetzen und Zeilenumbrüche entfernen
        df_export[col] = df_export[col].astype(str).str.replace(';', ',', regex=False)
        df_export[col] = df_export[col].str.replace('\n', ' ', regex=False)
        df_export[col] = df_export[col].str.replace('\r', '', regex=False)

    # 2. Datums-Formatierung (DD/MM/YYYY)
    if 'Datum' in df_export.columns:
        # Versuche das Datum zu parsen. coerce setzt fehlerhafte Werte auf NaT, was dann zu "" wird
        df_export['Datum'] = pd.to_datetime(df_export['Datum'], errors='coerce', dayfirst=True).dt.strftime('%d/%m/%Y')
        df_export['Datum'] = df_export['Datum'].fillna('')

    # 3. Zahlen-Formatierung (Komma als Trenner, 2 Nachkommastellen)
    # Identifiziere Float-Spalten
    float_cols = df_export.select_dtypes(include=['float64', 'float32']).columns
    for col in float_cols:
        # Formatiere auf exakt 2 Nachkommastellen und ersetze Punkt durch Komma
        df_export[col] = df_export[col].apply(lambda x: f"{x:.2f}".replace('.', ',') if pd.notnull(x) and str(x).strip() != "" else "")

    # 4. Der eigentliche Export
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    df_export.to_csv(
        output_path,
        sep=';',
        index=False,
        encoding='cp1252',
        quoting=csv.QUOTE_NONE,
        escapechar='\\' # Verhindert Pandas-Fehler bei QUOTE_NONE
    )
    
    print(f"B Point Export erfolgreich erstellt unter: {output_path}")
