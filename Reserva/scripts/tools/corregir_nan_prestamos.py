import psycopg2

def corregir_descripciones_nan():
    """Corrige las descripciones de equipos que contienen '(nan)' en préstamos existentes"""
    try:
        conn = psycopg2.connect('dbname=sistema_reserva user=postgres password=Allison2023secure host=localhost')
        cursor = conn.cursor()
        
        # Buscar préstamos con '(nan)' en la descripción
        cursor.execute("""
            SELECT id_prestamo, equipo_prestado 
            FROM prestamos_equipos 
            WHERE equipo_prestado LIKE '%(nan)%'
        """)
        
        prestamos_corregir = cursor.fetchall()
        
        print(f"Se encontraron {len(prestamos_corregir)} préstamos con '(nan)'")
        
        for prestamo_id, descripcion_actual in prestamos_corregir:
            # Reemplazar '(nan)' con '(S/N)'
            descripcion_corregida = descripcion_actual.replace('(nan)', '(S/N)')
            
            print(f"Corrigiendo préstamo {prestamo_id}: '{descripcion_actual}' -> '{descripcion_corregida}'")
            
            # Actualizar la descripción
            cursor.execute("""
                UPDATE prestamos_equipos 
                SET equipo_prestado = %s 
                WHERE id_prestamo = %s
            """, (descripcion_corregida, prestamo_id))
        
        # Confirmar cambios
        conn.commit()
        print(f"✅ Se corrigieron {len(prestamos_corregir)} préstamos exitosamente")
        
        # Verificar que no queden '(nan)'
        cursor.execute("""
            SELECT COUNT(*) FROM prestamos_equipos 
            WHERE equipo_prestado LIKE '%(nan)%'
        """)
        restantes = cursor.fetchone()[0]
        
        if restantes == 0:
            print("✅ No quedan préstamos con '(nan)'")
        else:
            print(f"⚠️ Quedan {restantes} préstamos con '(nan)'")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    corregir_descripciones_nan()
