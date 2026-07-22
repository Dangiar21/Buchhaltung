import sqlite3
conn = sqlite3.connect('c:/Users/Dangi/Desktop/Buchhaltung/Systemdaten/buchhaltung.db')
cur = conn.cursor()

print("--- cache_konten ---")
cur.execute("SELECT * FROM cache_konten WHERE konto='5000000'")
print(cur.fetchall())

print("--- kontenregeln ---")
cur.execute("SELECT * FROM kontenregeln WHERE konto='5000000'")
print(cur.fetchall())
