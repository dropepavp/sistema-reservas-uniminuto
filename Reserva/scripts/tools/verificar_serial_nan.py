import psycopg2

def verificar_serial_nan():
    """Verifica si hay equipos en inventario con serial 'nan'"""
    try:
        conn = psycopg2.connect('dbname=sistema_reserva user=postgres password=Allison2023secure host=localhost')
        cursor = conn.cursor()
        
        # Buscar equipos con serial inválido
        cursor.execute("""
            SELECT numero_inventario, item, serial, activo_fijo 
            FROM inventario 
            WHERE serial ILIKE '%nan%' 
               OR serial ILIKE '%undefined%' 
               OR serial ILIKE '%null%'
               OR activo_fijo ILIKE '%nan%'
               OR activo_fijo ILIKE '%undefined%'
               OR activo_fijo ILIKE '%null%'
        """)
        
        equipos_problematicos = cursor.fetchall()
        
        print(f"Se encontraron {len(equipos_problematicos)} equipos con valores inválidos:")
        
        for num_inv, item, serial, activo_fijo in equipos_problematicos:
            print(f"  - {item} ({num_inv}): serial='{serial}', activo_fijo='{activo_fijo}'")
        
        if equipos_problematicos:
            print("\n¿Desea limpiar estos valores inválidos? (y/n)")
            respuesta = input().lower().strip()
            
            if respuesta == 'y':
                # Limpiar valores inválidos
                cursor.execute("""
                    UPDATE inventario 
                    SET serial = NULL WHERE serial ILIKE '%nan%' 
                       OR serial ILIKE '%undefined%' 
                       OR serial ILIKE '%null%'
                """)
                
                cursor.execute("""
                    UPDATE inventario 
                    SET activo_fijo = NULL WHERE activo_fijo ILIKE '%nan%'
                       OR activo_fijo ILIKE '%undefined%'
                       OR activo_fijo ILIKE '%null%'
                """)
                
                conn.commit()
                print("✅ Valores inválidos limpiados correctamente")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    verificar_serial_nan()
