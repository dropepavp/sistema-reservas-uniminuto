"""
Script para debugger el problema de encoding en el usuario 80140666
"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Conectar directamente
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres:admin@localhost/reserva_equipos"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Obtener el usuario y revisar cada columna por separado
    print("="*60)
    print("REVISANDO CADA COLUMNA DEL USUARIO 80140666")
    print("="*60)
    
    # 1. Obtener documento
    cursor.execute('SELECT documento FROM auxiliares WHERE documento = %s', ('80140666',))
    result = cursor.fetchone()
    if result:
        print(f"✓ documento: {repr(result[0])}")
    
    # 2. Obtener nombre_completo
    try:
        cursor.execute('SELECT nombre_completo FROM auxiliares WHERE documento = %s', ('80140666',))
        result = cursor.fetchone()
        if result:
            print(f"✓ nombre_completo: {repr(result[0])}")
    except Exception as e:
        print(f"✗ Error en nombre_completo: {e}")
    
    # 3. Obtener correo
    try:
        cursor.execute('SELECT correo FROM auxiliares WHERE documento = %s', ('80140666',))
        result = cursor.fetchone()
        if result:
            print(f"✓ correo: {repr(result[0])}")
    except Exception as e:
        print(f"✗ Error en correo: {e}")
    
    # 4. Obtener contraseña
    try:
        cursor.execute('SELECT contraseña FROM auxiliares WHERE documento = %s', ('80140666',))
        result = cursor.fetchone()
        if result:
            print(f"✓ contraseña: {repr(result[0])}")
    except Exception as e:
        print(f"✗ Error en contraseña: {e}")
    
    # 5. Obtener rol
    try:
        cursor.execute('SELECT rol FROM auxiliares WHERE documento = %s', ('80140666',))
        result = cursor.fetchone()
        if result:
            print(f"✓ rol: {repr(result[0])}")
    except Exception as e:
        print(f"✗ Error en rol: {e}")
    
    # 6. Obtener sede_id
    try:
        cursor.execute('SELECT sede_id FROM auxiliares WHERE documento = %s', ('80140666',))
        result = cursor.fetchone()
        if result:
            print(f"✓ sede_id: {repr(result[0])}")
    except Exception as e:
        print(f"✗ Error en sede_id: {e}")
    
    print("\n" + "="*60)
    print("BUSCANDO TODOS LOS USUARIOS CON PROBLEMAS DE ENCODING")
    print("="*60)
    
    # Obtener todos los usuarios e intentar decodificar
    cursor.execute('SELECT COUNT(*) FROM auxiliares')
    total = cursor.fetchone()[0]
    print(f"Total de usuarios: {total}")
    
    # Obtener solo documentos
    cursor.execute('SELECT documento FROM auxiliares')
    usuarios = cursor.fetchall()
    
    problematic_users = []
    for user in usuarios:
        print(f"  - {user[0]}")
        try:
            # Intentar leer el usuario con la ORM
            from app_improved import db, Auxiliar
            aux = Auxiliar.query.get(user[0])
            print(f"    ✓ ORM access OK")
        except Exception as e:
            print(f"    ✗ ORM error: {str(e)[:80]}")
            problematic_users.append(user[0])
    
    if problematic_users:
        print(f"\n⚠️  Usuarios con problemas: {problematic_users}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
