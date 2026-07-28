import polars as pl
import os
import re
import csv
import traceback

def clean_number(val):
    if val is None:
        return val
        
    val_str = str(val).strip()
    
    # Check if it looks like a messy number
    val_str_clean = re.sub(r'[€$\s]', '', val_str)
    
    if not any(c.isdigit() for c in val_str_clean):
        return val
        
    if re.fullmatch(r'-?\d+', val_str_clean):
        try:
            return int(val_str_clean)
        except:
            return val_str
            
    num_dots = val_str_clean.count('.')
    num_commas = val_str_clean.count(',')
    
    if num_dots > 0 and num_commas > 0:
        last_dot = val_str_clean.rfind('.')
        last_comma = val_str_clean.rfind(',')
        
        if last_dot > last_comma:
            val_str_clean = val_str_clean.replace(',', '')
        else:
            val_str_clean = val_str_clean.replace('.', '').replace(',', '.')
    
    elif num_dots > 0 and num_commas == 0:
        if num_dots == 1:
            parts = val_str_clean.split('.')
            if len(parts[1]) == 3:
                val_str_clean = val_str_clean.replace('.', '')
            else:
                pass
        else:
            val_str_clean = val_str_clean.replace('.', '')
            
    elif num_commas > 0 and num_dots == 0:
        if num_commas == 1:
            parts = val_str_clean.split(',')
            if len(parts[1]) == 3:
                val_str_clean = val_str_clean.replace(',', '')
            else:
                val_str_clean = val_str_clean.replace(',', '.')
        else:
            val_str_clean = val_str_clean.replace(',', '')

    try:
        if '.' in val_str_clean:
            return float(val_str_clean)
        return int(val_str_clean)
    except:
        return val

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
                    
        # Read with Polars
        df = pl.read_csv(csv_path, separator=delimiter, infer_schema_length=0, encoding='utf8-lossy')
        
        # Apply cleaning to all columns
        # Note: clean_number can return int, float or string. We use map_elements with return_dtype=pl.Object or let Polars infer.
        # To make it write to excel properly, we can convert back to standard python dicts or try to cast.
        # Easiest way to handle mixed types in polars for excel export:
        
        exprs = []
        for col in df.columns:
            exprs.append(
                pl.col(col).map_elements(lambda x: clean_number(x), return_dtype=pl.String, skip_nulls=False).alias(col)
            )
        
        df = df.with_columns(exprs)
        
        output_path = os.path.splitext(csv_path)[0] + "_cleaned.xlsx"
        # Write to excel using polars
        df.write_excel(output_path)
        
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
