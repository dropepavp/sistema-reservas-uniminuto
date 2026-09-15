import psycopg2

def verificar_disponibilidad():
    """Verifica qué equipos están disponibles y cuáles no"""
    try:
        conn = psycopg2.connect('dbname=sistema_reserva user=postgres password=Allison2023secure host=localhost')
        cursor = conn.cursor()
        
        print("🔍 VERIFICACIÓN DE DISPONIBILIDAD DE EQUIPOS")
        print("=" * 60)
        
        # Verificar equipos LAP que están prestados
        cursor.execute("""
            SELECT numero_inventario, item, estado 
            FROM inventario 
            WHERE item ILIKE '%laptop%' 
            ORDER BY numero_inventario
        """)
        
        equipos_laptop = cursor.fetchall()
        print(f"\n📱 EQUIPOS LAPTOP ({len(equipos_laptop)} total):")
        for num_inv, item, estado in equipos_laptop:
            disponible = "✅ Disponible" if estado == 'Disponible' else "❌ No disponible"
            print(f"   {item} ({num_inv}): {disponible}")
        
        # Verificar equipos ADA que están prestados
        cursor.execute("""
            SELECT numero_inventario, item, estado 
            FROM inventario 
            WHERE item ILIKE '%adaptador%' 
            ORDER BY numero_inventario
        """)
        
        equipos_adaptador = cursor.fetchall()
        print(f"\n🔌 EQUIPOS ADAPTADOR ({len(equipos_adaptador)} total):")
        for num_inv, item, estado in equipos_adaptador:
            disponible = "✅ Disponible" if estado == 'Disponible' else "❌ No disponible"
            print(f"   {item} ({num_inv}): {disponible}")
        
        # Verificar préstamos activos
        cursor.execute("""
            SELECT numero_inventario_equipo, equipo_prestado, estado
            FROM prestamos_equipos 
            WHERE estado = 'Prestado'
            ORDER BY id_prestamo DESC
            LIMIT 10
        """)
        
        prestamos_activos = cursor.fetchall()
        print(f"\n📋 PRÉSTAMOS ACTIVOS ({len(prestamos_activos)} recientes):")
        for num_inv, equipo, estado in prestamos_activos:
            print(f"   {equipo} ({num_inv}): {estado}")
        
        # Sugerir equipos disponibles para prueba
        cursor.execute("""
            SELECT numero_inventario, item, estado 
            FROM inventario 
            WHERE estado = 'Disponible'
            AND (item ILIKE '%laptop%' OR item ILIKE '%adaptador%')
            ORDER BY item
            LIMIT 5
        """)
        
        disponibles = cursor.fetchall()
        print(f"\n✅ EQUIPOS DISPONIBLES PARA PRUEBA:")
        for num_inv, item, estado in disponibles:
            print(f"   📌 {item} ({num_inv}) - ESTE DEBERÍA FUNCIONAR")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verificar_disponibilidad()
