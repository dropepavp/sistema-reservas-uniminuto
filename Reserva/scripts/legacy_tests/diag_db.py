import psycopg2
import os

def check_profesores():
    try:
        # Credenciales directas basadas en run_with_postgres.py
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='postgres',
            password='Allison2023secure',
            database='sistema_reserva',
            client_encoding='utf8'
        )
        cur = conn.cursor()
        
        print("Conexión exitosa a PostgreSQL.")
        
        # Verificar tabla
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'profesores');")
        exists = cur.fetchone()[0]
        print(f"¿Existe la tabla 'profesores'?: {exists}")
        
        if exists:
            cur.execute("SELECT count(*) FROM profesores;")
            count = cur.fetchone()[0]
            print(f"Total de registros en 'profesores': {count}")
            
            if count > 0:
                print("\nPrimeros 5 registros:")
                cur.execute("SELECT cedula, nombre_completo FROM profesores LIMIT 5;")
                for row in cur.fetchall():
                    print(f"- Cédula: {row[0]}, Nombre: {row[1]}")
            else:
                print("La tabla está vacía.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_profesores()
