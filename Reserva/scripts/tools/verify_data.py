#!/usr/bin/env python3
"""
Script para verificar datos agregados (inventario y usuarios).
"""
import os
import sys
from urllib.parse import urlparse
from sqlalchemy import create_engine, text

# Configurar URL
db_url = os.environ.get('DATABASE_URL') or 'postgresql://postgres:Allison2023secure@localhost:5432/sistema_reserva'
if 'Allison2023*' in db_url:
    db_url = db_url.replace('Allison2023*', 'Allison2023secure')

parsed = urlparse(db_url)

# Build engine con connect_args
connect_args = {
    'host': parsed.hostname or 'localhost',
    'port': parsed.port or 5432,
    'user': parsed.username or 'postgres',
    'password': parsed.password or 'Allison2023secure',
    'database': parsed.path.lstrip('/') or 'sistema_reserva',
    'client_encoding': 'utf8',
}

engine = create_engine('postgresql+psycopg2://', connect_args=connect_args, echo=False)

try:
    with engine.connect() as conn:
        print("=" * 60)
        print("📊 VERIFICACIÓN DE DATOS EN BASE DE DATOS")
        print("=" * 60)
        
        # Contar items de inventario
        result = conn.execute(text("SELECT COUNT(*) as total FROM inventario"))
        inv_count = result.scalar()
        print(f"\n✓ Items de Inventario: {inv_count}")
        
        # Mostrar inventario
        result = conn.execute(text("""
            SELECT numero_inventario, item, categoria, estado, 
                   CASE WHEN es_por_cantidad THEN CONCAT(cantidad_disponible, '/', cantidad_total) ELSE '-' END as cantidad
            FROM inventario 
            ORDER BY numero_inventario
        """))
        for row in result:
            print(f"  • {row[0]:<20} | {row[1]:<20} | {row[2]:<20} | {row[3]:<15} | Cant: {row[4]}")
        
        # Contar usuarios
        result = conn.execute(text("SELECT COUNT(*) as total FROM auxiliares"))
        user_count = result.scalar()
        print(f"\n✓ Usuarios Auxiliares: {user_count}")
        
        # Mostrar usuarios
        result = conn.execute(text("""
            SELECT documento, nombre_completo, correo, rol
            FROM auxiliares 
            ORDER BY documento
        """))
        for row in result:
            print(f"  • Doc: {row[0]:<12} | {row[1]:<25} | {row[2]:<20} | Rol: {row[3]}")
        
        # Tabla de resumen
        print("\n" + "=" * 60)
        print("📈 RESUMEN DE CONFIGURACIÓN")
        print("=" * 60)
        
        result = conn.execute(text("SELECT COUNT(*) FROM sedes"))
        sedes = result.scalar()
        
        result = conn.execute(text("SELECT COUNT(*) FROM bodegas"))
        bodegas = result.scalar()
        
        result = conn.execute(text("SELECT COUNT(*) FROM profesores"))
        profesores = result.scalar()
        
        result = conn.execute(text("SELECT COUNT(*) FROM prestamos_equipos"))
        prestamos = result.scalar()
        
        result = conn.execute(text("SELECT COUNT(*) FROM reservas"))
        reservas = result.scalar()
        
        print(f"Sedes: {sedes}")
        print(f"Bodegas: {bodegas}")
        print(f"Profesores: {profesores}")
        print(f"Préstamos Registrados: {prestamos}")
        print(f"Reservas Registradas: {reservas}")
        print(f"Items de Inventario: {inv_count}")
        print(f"Usuarios: {user_count}")
        
        print("\n" + "=" * 60)
        print("✅ SISTEMA LISTO PARA PRUEBAS")
        print("=" * 60)
        print("\n🌐 Acceso a la aplicación: http://127.0.0.1:5000")
        print("📝 Credenciales de prueba:")
        print("   Documento: 1234567890")
        print("   Contraseña: Admin123!")
        
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    engine.dispose()
