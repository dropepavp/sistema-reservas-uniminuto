import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash

doc = '80140666'
nueva_pwd = 'Psw00rd123'

conn = psycopg2.connect(
    host='127.0.0.1', port=5432,
    user='postgres', password='Allison2023secure',
    dbname='sistema_reserva', client_encoding='utf8'
)
c = conn.cursor()

# Verificar nombre exacto de la columna de contrasena
c.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'auxiliares'
""")
cols = [row[0] for row in c.fetchall()]
print("Columnas de 'auxiliares':", cols)

# Encontrar la columna de contrasena
col_pwd = None
for col in cols:
    if 'contrase' in col.lower() or 'password' in col.lower() or 'pwd' in col.lower():
        col_pwd = col
        break

if not col_pwd:
    print("ERROR: No se encontro columna de contrasena")
    conn.close()
    exit(1)

print(f"Columna de contrasena: '{col_pwd}'")

# Generar nuevo hash
nuevo_hash = generate_password_hash(nueva_pwd)

# Actualizar usando la columna correcta
sql = f'UPDATE auxiliares SET "{col_pwd}" = %s WHERE documento = %s'
c.execute(sql, (nuevo_hash, doc))

if c.rowcount == 0:
    print(f"ERROR: Usuario '{doc}' no encontrado")
    conn.rollback()
else:
    conn.commit()
    # Verificar
    c.execute(f'SELECT "{col_pwd}" FROM auxiliares WHERE documento = %s', (doc,))
    row = c.fetchone()
    ok = check_password_hash(row[0], nueva_pwd)
    print("-" * 40)
    print(f"Usuario    : {doc}")
    print(f"Contrasena : {nueva_pwd}")
    print(f"Resultado  : {'OK - Contrasena actualizada correctamente' if ok else 'FALLO - Verificacion incorrecta'}")

conn.close()
