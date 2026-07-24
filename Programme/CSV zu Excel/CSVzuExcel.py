import os
import pandas as pd
import re
import csv
import traceback

def clean_number(val):
    if pd.isna(val):
        return val
        
    val_str = str(val).strip()
    
    # Check if it looks like a messy number
    # It might have € or $ signs
    val_str_clean = re.sub(r'[€$\s]', '', val_str)
    
    # It must contain at least one digit
    if not any(c.isdigit() for c in val_str_clean):
        return val
        
    # If it's just digits, maybe with a minus
    if re.fullmatch(r'-?\d+', val_str_clean):
        try:
            return int(val_str_clean)
        except:
            return val_str
            
    # Now for the messy commas and dots
    # Pattern: 1.000,50 or 1,000.50 or 1.000 or 1,000 or 12.50
    # Let's count dots and commas
    num_dots = val_str_clean.count('.')
    num_commas = val_str_clean.count(',')
    
    # If both exist
    if num_dots > 0 and num_commas > 0:
        last_dot = val_str_clean.rfind('.')
        last_comma = val_str_clean.rfind(',')
        
        if last_dot > last_comma:
            # e.g., 1,000.50 (English style)
            # Remove all commas, leave the dot
            val_str_clean = val_str_clean.replace(',', '')
        else:
            # e.g., 1.000,50 (German style)
            # Remove all dots, replace comma with dot
            val_str_clean = val_str_clean.replace('.', '').replace(',', '.')
    
    elif num_dots > 0 and num_commas == 0:
        # Only dots
        if num_dots == 1:
            # Could be 1.000 or 1.50
            parts = val_str_clean.split('.')
            if len(parts[1]) == 3:
                # E.g. 1.000 -> assume it's a thousand separator
                val_str_clean = val_str_clean.replace('.', '')
            else:
                # E.g. 1.50 or 1.1 -> assume it's a decimal
                pass # dot is already fine for float
        else:
            # Multiple dots -> e.g. 1.000.000 -> all thousand separators
            val_str_clean = val_str_clean.replace('.', '')
            
    elif num_commas > 0 and num_dots == 0:
        # Only commas
        if num_commas == 1:
            parts = val_str_clean.split(',')
            if len(parts[1]) == 3:
                # E.g. 1,000 -> assume thousand separator
                val_str_clean = val_str_clean.replace(',', '')
            else:
                # E.g. 1,50 -> assume decimal
                val_str_clean = val_str_clean.replace(',', '.')
        else:
            # Multiple commas -> all thousand separators
            val_str_clean = val_str_clean.replace(',', '')

    try:
        # Try to convert to float
        if '.' in val_str_clean:
            return float(val_str_clean)
        return int(val_str_clean)
    except:
        return val  # Return original if parsing fails

def process_csv(csv_path):
    try:
        # Try sniffing the delimiter
        with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
            sample = f.read(10000)
            try:
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
            except:
                delimiter = ','
                if sample.count(';') > sample.count(','):
                    delimiter = ';'
                    
        df = pd.read_csv(csv_path, sep=delimiter, dtype=str, encoding='utf-8', encoding_errors='replace')
        
        # Apply cleaning to all columns
        for col in df.columns:
            df[col] = df[col].apply(clean_number)
            
        output_path = os.path.splitext(csv_path)[0] + "_cleaned.xlsx"
        df.to_excel(output_path, index=False)
        
        # Open the generated file automatically on Windows
        if os.name == 'nt':
            os.startfile(output_path)
            
        return True, output_path
    except Exception as e:
        return False, str(e)

def run_conversion(input_paths, output_dir=None, nutzerdaten_dir=None, progress_callback=None):
    if not input_paths:
        print("Keine Dateien ausgewählt.")
        return
        
    csv_files = []
    for path in input_paths:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.lower().endswith('.csv'):
                        csv_files.append(os.path.join(root, file))
        elif os.path.isfile(path) and path.lower().endswith('.csv'):
            csv_files.append(path)
            
    if not csv_files:
        print("Keine CSV-Dateien gefunden.")
        return
        
    total_files = len(csv_files)
    print(f"Starte Konvertierung von {total_files} CSV-Dateien...")
    
    success_count = 0
    for i, csv_file in enumerate(csv_files):
        print(f"-> Verarbeite: {os.path.basename(csv_file)}")
        success, result = process_csv(csv_file)
        if success:
            print(f"   Erfolgreich erstellt: {os.path.basename(result)}")
            success_count += 1
        else:
            print(f"   Fehler: {result}")
            
        if progress_callback:
            progress_callback(int(((i + 1) / total_files) * 100))
        else:
            print(f"[PROGRESS:{int(((i + 1) / total_files) * 100)}]")
            
    print(f"\\nFertig! {success_count} von {total_files} Dateien konvertiert.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        run_conversion(sys.argv[1:])
    else:
        print("Bitte CSV-Dateien oder Ordner als Argument übergeben.")
