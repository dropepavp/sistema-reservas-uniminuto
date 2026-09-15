import psycopg2

DB_URL = 'postgresql://postgres:Allison2023secure@localhost:5432/sistema_reserva'
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Get all table names
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    ORDER BY table_name
""")

print('=== Tablas en la BD ===')
for row in cur.fetchall():
    print(row[0])

cur.close()
conn.close()
