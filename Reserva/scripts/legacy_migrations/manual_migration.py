import psycopg2

DATABASE_URL = "postgresql://postgres:Allison2023*@127.0.0.1:5432/sistema_reserva"

def run_migration():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        queries = [
            "ALTER TABLE inventario ADD COLUMN IF NOT EXISTS bodega_id INTEGER REFERENCES bodegas(id)",
            "ALTER TABLE reservas ADD COLUMN IF NOT EXISTS sede_id INTEGER REFERENCES sedes(id)",
            "ALTER TABLE prestamos_equipos ADD COLUMN IF NOT EXISTS sede_id INTEGER REFERENCES sedes(id)",
            "ALTER TABLE auxiliares ADD COLUMN IF NOT EXISTS sede_id INTEGER REFERENCES sedes(id)"
        ]
        
        for query in queries:
            try:
                cursor.execute(query)
                conn.commit()
                print(f"✅ Ejecutado: {query}")
            except Exception as e:
                conn.rollback()
                print(f"⚠️ Nota o Error: {e}")
                
        cursor.close()
        conn.close()
        print("\n🚀 Migración manual completada.")
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")

if __name__ == "__main__":
    run_migration()
