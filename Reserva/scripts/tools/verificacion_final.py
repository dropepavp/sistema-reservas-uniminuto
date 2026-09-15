import psycopg2

def verificacion_final():
    """Verificación final de que no queden valores 'nan' en el sistema"""
    try:
        conn = psycopg2.connect('dbname=sistema_reserva user=postgres password=Allison2023secure host=localhost')
        cursor = conn.cursor()
        
        print("🔍 VERIFICACIÓN FINAL - Sistema de Préstamos")
        print("=" * 50)
        
        # 1. Verificar préstamos con '(nan)'
        cursor.execute("""
            SELECT COUNT(*) FROM prestamos_equipos 
            WHERE equipo_prestado LIKE '%(nan)%'
        """)
        prestamos_nan = cursor.fetchone()[0]
        
        # 2. Verificar inventario con serial/activo_fijo 'nan'
        cursor.execute("""
            SELECT COUNT(*) FROM inventario 
            WHERE serial ILIKE '%nan%' 
               OR serial ILIKE '%undefined%' 
               OR serial ILIKE '%null%'
               OR activo_fijo ILIKE '%nan%'
               OR activo_fijo ILIKE '%undefined%'
               OR activo_fijo ILIKE '%null%'
        """)
        inventario_nan = cursor.fetchone()[0]
        
        # 3. Verificar adaptadores disponibles
        cursor.execute("""
            SELECT COUNT(*) FROM inventario 
            WHERE (item ILIKE '%adaptador%' OR item ILIKE '%cargador%') 
            AND estado = 'Disponible'
        """)
        adaptadores_disponibles = cursor.fetchone()[0]
        
        # 4. Verificar teclados disponibles
        cursor.execute("""
            SELECT COUNT(*) FROM inventario 
            WHERE item ILIKE '%teclado%' 
            AND estado = 'Disponible'
        """)
        teclados_disponibles = cursor.fetchone()[0]
        
        # 5. Mostrar algunos ejemplos de equipos disponibles
        cursor.execute("""
            SELECT item, numero_inventario, estado 
            FROM inventario 
            WHERE (item ILIKE '%adaptador%' OR item ILIKE '%cargador%') 
            AND estado = 'Disponible'
            LIMIT 5
        """)
        ejemplos_adaptadores = cursor.fetchall()
        
        print(f"📊 RESULTADOS:")
        print(f"   Préstamos con '(nan)': {prestamos_nan}")
        print(f"   Inventario con valores inválidos: {inventario_nan}")
        print(f"   Adaptadores/ Cargadores disponibles: {adaptadores_disponibles}")
        print(f"   Teclados disponibles: {teclados_disponibles}")
        
        print(f"\n📋 EJEMPLOS DE ADAPTADORES DISPONIBLES:")
        for item, num_inv, estado in ejemplos_adaptadores:
            print(f"   - {item} ({num_inv}) - {estado}")
        
        # Verificación final
        if prestamos_nan == 0 and inventario_nan == 0:
            print(f"\n✅ VERIFICACIÓN EXITOSA:")
            print(f"   • No quedan préstamos con '(nan)'")
            print(f"   • No quedan valores inválidos en inventario")
            print(f"   • Hay {adaptadores_disponibles} adaptadores/cargadores disponibles")
            print(f"   • El sistema está listo para funcionar correctamente")
        else:
            print(f"\n⚠️ QUEDAN PROBLEMAS POR RESOLVER:")
            if prestamos_nan > 0:
                print(f"   • Quedan {prestamos_nan} préstamos con '(nan)'")
            if inventario_nan > 0:
                print(f"   • Quedan {inventario_nan} equipos con valores inválidos")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    verificacion_final()
