from werkzeug.security import generate_password_hash
import psycopg2

conn = psycopg2.connect('dbname=sistema_reserva user=postgres password=Allison2023secure host=localhost')
cur = conn.cursor()
new_hash = generate_password_hash('123456')
cur.execute('UPDATE auxiliares SET "contraseña" = %s WHERE documento = %s', (new_hash, '80140666'))
rows = cur.rowcount
conn.commit()
print(f'✅ Contraseña actualizada para usuario 80140666')
print(f'   Filas actualizadas: {rows}')
print(f'   Nueva contraseña: 123456')
