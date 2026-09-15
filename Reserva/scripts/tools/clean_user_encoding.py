import psycopg2
import time

conn = psycopg2.connect('dbname=sistema_reserva user=postgres password=Allison2023secure host=localhost')
cur = conn.cursor()

# Limpiar el usuario: actualizar con valores ASCII seguros y correo único
email_limpio = f"admin80140666-{int(time.time())}@sistema.com"

cur.execute("""
UPDATE auxiliares 
SET 
  nombre_completo = 'Admin 80140666',
  correo = %s
WHERE documento = '80140666'
""", (email_limpio,))

rows = cur.rowcount
conn.commit()

print(f"Filas actualizadas: {rows}")
print(f"Nuevo correo: {email_limpio}")
print("Usuario limpiado de caracteres con problemas de encoding")
