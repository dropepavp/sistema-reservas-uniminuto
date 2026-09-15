import psycopg2
from werkzeug.security import generate_password_hash

conn = psycopg2.connect('dbname=sistema_reserva user=postgres password=Allison2023secure host=localhost')
cur = conn.cursor()

# Primero eliminar el usuario problemático
print("Eliminando usuario problemático...")
cur.execute("DELETE FROM auxiliares WHERE documento = '80140666'")
conn.commit()
print(f"Filas eliminadas: {cur.rowcount}")

# Luego recrearlo con datos limpios
print("\nRecreando usuario...")
new_hash = generate_password_hash("123456")

cur.execute("""
INSERT INTO auxiliares (documento, nombre_completo, correo, "contraseña", rol)
VALUES (%s, %s, %s, %s, %s)
""", ('80140666', 'Admin', 'admin80140666@clean.com', new_hash, 'admin'))

conn.commit()
print("Usuario recreado exitosamente")
print("Documento: 80140666")
print("Contraseña: 123456")
