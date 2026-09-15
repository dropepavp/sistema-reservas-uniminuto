#!/usr/bin/env python3
"""
Script para verificar qué tablas y datos tiene la base de datos de la aplicación.
"""

import sqlite3
from datetime import date
import os

def verificar_base_datos():
    # Verificar qué base de datos está usando la aplicación
    db_path = 'instance/sistema_integrado.db'
    print(f'Verificando base de datos: {db_path}')
    print(f'Archivo existe: {os.path.exists(db_path)}')
    
    if not os.path.exists(db_path):
        print('La base de datos no existe. Creando nueva...')
        # Crear el directorio instance si no existe
        os.makedirs('instance', exist_ok=True)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Obtener todas las tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if tables:
            print('\nTablas encontradas:')
            for table in tables:
                table_name = table[0]
                print(f'  - {table_name}')
                
                # Contar registros en cada tabla
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f'    Registros: {count}')
        else:
            print('\nNo hay tablas en la base de datos.')
        
        # Si hay tablas, verificar datos de hoy específicamente
        if tables and any('prestamos' in str(table) for table in tables):
            today = date.today().strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT id, docente_id, item_inventario, fecha_prestamo, estado 
                FROM prestamos 
                WHERE date(fecha_prestamo) = ? AND estado = 'Prestado'
            """, (today,))
            
            prestamos_hoy = cursor.fetchall()
            print(f'\nPréstamos activos para hoy ({today}): {len(prestamos_hoy)}')
            
            for prestamo in prestamos_hoy[:3]:
                print(f'  - ID: {prestamo[0]}, Docente: {prestamo[1]}, Item: {prestamo[2]}, Estado: {prestamo[4]}')
        
        conn.close()
        
    except Exception as e:
        print(f'Error al verificar la base de datos: {e}')

if __name__ == '__main__':
    verificar_base_datos()