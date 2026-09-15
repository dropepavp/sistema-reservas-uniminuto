#!/usr/bin/env python3
"""
Script para verificar los datos en la base de datos que usa la aplicación.
"""

import sqlite3
from datetime import date

def verificar_datos_aplicacion():
    db_path = 'instance/sistema_integrado.db'
    print(f'Verificando datos en: {db_path}')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar estructura de prestamos_equipos
        cursor.execute("PRAGMA table_info(prestamos_equipos);")
        columns = cursor.fetchall()
        print('\nEstructura de prestamos_equipos:')
        for col in columns:
            print(f'  - {col[1]} ({col[2]})')
        
        # Verificar todos los préstamos
        cursor.execute("SELECT * FROM prestamos_equipos")
        prestamos = cursor.fetchall()
        print(f'\nTodos los préstamos: {len(prestamos)}')
        for prestamo in prestamos:
            print(f'  - {prestamo}')
        
        # Verificar estructura de reservas
        cursor.execute("PRAGMA table_info(reservas);")
        columns = cursor.fetchall()
        print('\nEstructura de reservas:')
        for col in columns:
            print(f'  - {col[1]} ({col[2]})')
        
        # Verificar todas las reservas
        cursor.execute("SELECT * FROM reservas")
        reservas = cursor.fetchall()
        print(f'\nTodas las reservas: {len(reservas)}')
        for reserva in reservas:
            print(f'  - {reserva}')
        
        # Verificar datos de hoy en prestamos_equipos
        today = date.today().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT * FROM prestamos_equipos 
            WHERE date(fecha_prestamo) = ?
        """, (today,))
        
        prestamos_hoy = cursor.fetchall()
        print(f'\nPréstamos para hoy ({today}): {len(prestamos_hoy)}')
        for prestamo in prestamos_hoy:
            print(f'  - {prestamo}')
        
        # Verificar datos de hoy en reservas
        cursor.execute("""
            SELECT * FROM reservas 
            WHERE date(fecha_inicio) = ?
        """, (today,))
        
        reservas_hoy = cursor.fetchall()
        print(f'\nReservas para hoy ({today}): {len(reservas_hoy)}')
        for reserva in reservas_hoy:
            print(f'  - {reserva}')
            
        conn.close()
        
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    verificar_datos_aplicacion()