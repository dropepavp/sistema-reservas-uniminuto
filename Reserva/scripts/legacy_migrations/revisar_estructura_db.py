#!/usr/bin/env python3
"""
Script para revisar la estructura completa de la base de datos.
"""

import sqlite3
import json

def revisar_estructura():
    """Revisa la estructura completa de todas las tablas."""
    db_path = 'instance/sistema_integrado.db'
    print("=" * 70)
    print("REVISIÓN ESTRUCTURA DE BASE DE DATOS")
    print("=" * 70)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Obtener todas las tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [t[0] for t in cursor.fetchall()]
        
        estructura_completa = {}
        
        for table in tables:
            print(f"\n📋 TABLA: {table.upper()}")
            print("-" * 50)
            
            # Obtener estructura de la tabla
            cursor.execute(f"PRAGMA table_info({table});")
            columns = cursor.fetchall()
            
            estructura_tabla = {
                'columnas': [],
                'indices': [],
                'foreign_keys': [],
                'sample_data': []
            }
            
            print("📊 COLUMNAS:")
            for col in columns:
                col_info = {
                    'nombre': col[1],
                    'tipo': col[2],
                    'not_null': bool(col[3]),
                    'default': col[4],
                    'primary_key': bool(col[5])
                }
                estructura_tabla['columnas'].append(col_info)
                
                pk_indicator = " 🔑" if col[5] else ""
                null_indicator = " ⚠️ NOT NULL" if col[3] else ""
                default_info = f" (default: {col[4]})" if col[4] else ""
                
                print(f"   - {col[1]}: {col[2]}{pk_indicator}{null_indicator}{default_info}")
            
            # Obtener índices
            cursor.execute(f"PRAGMA index_list({table});")
            indices = cursor.fetchall()
            
            if indices:
                print("\n🔍 ÍNDICES:")
                for idx in indices:
                    estructura_tabla['indices'].append({
                        'nombre': idx[1],
                        'unique': bool(idx[2]),
                        'origin': idx[3]
                    })
                    unique_indicator = " (UNIQUE)" if idx[2] else ""
                    print(f"   - {idx[1]}{unique_indicator}")
            
            # Obtener foreign keys
            cursor.execute(f"PRAGMA foreign_key_list({table});")
            foreign_keys = cursor.fetchall()
            
            if foreign_keys:
                print("\n🔗 FOREIGN KEYS:")
                for fk in foreign_keys:
                    estructura_tabla['foreign_keys'].append({
                        'from_column': fk[3],
                        'to_table': fk[2],
                        'to_column': fk[4]
                    })
                    print(f"   - {fk[3]} → {fk[2]}.{fk[4]}")
            
            # Obtener datos de muestra (primeros 3 registros)
            cursor.execute(f"SELECT * FROM {table} LIMIT 3")
            sample_data = cursor.fetchall()
            
            if sample_data:
                print(f"\n📝 DATOS DE MUESTRA (primeros 3 registros):")
                column_names = [col[1] for col in columns]
                for i, row in enumerate(sample_data, 1):
                    print(f"   Registro {i}:")
                    for j, value in enumerate(row):
                        if j < len(column_names):
                            # Truncar valores largos para mejor visualización
                            display_value = str(value)
                            if len(display_value) > 50:
                                display_value = display_value[:47] + "..."
                            print(f"     {column_names[j]}: {display_value}")
                    print()
                
                # Guardar datos de muestra en la estructura (solo nombres de columnas)
                estructura_tabla['sample_data'] = {
                    'columns': column_names,
                    'count': len(sample_data)
                }
            
            # Contar total de registros
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            total_records = cursor.fetchone()[0]
            print(f"📊 TOTAL DE REGISTROS: {total_records}")
            
            estructura_completa[table] = estructura_tabla
        
        # Generar resumen general
        print("\n" + "=" * 70)
        print("📋 RESUMEN DE LA BASE DE DATOS")
        print("=" * 70)
        
        total_tables = len(tables)
        total_records = 0
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            total_records += count
            print(f"📊 {table}: {count} registros")
        
        print(f"\n🎯 ESTADÍSTICAS GENERALES:")
        print(f"   - Total de tablas: {total_tables}")
        print(f"   - Total de registros: {total_records}")
        
        # Verificar integridad referencial básica
        print(f"\n🔍 VERIFICACIONES DE INTEGRIDAD:")
        
        # Verificar si hay profesores en préstamos que no existen
        cursor.execute("""
            SELECT COUNT(*) FROM prestamos_equipos p
            WHERE NOT EXISTS (
                SELECT 1 FROM profesores pr WHERE pr.cedula = p.cedula_profesor
            )
        """)
        prof_huerfanos = cursor.fetchone()[0]
        
        # Verificar si hay equipos en préstamos que no existen en inventario
        cursor.execute("""
            SELECT COUNT(*) FROM prestamos_equipos p
            WHERE NOT EXISTS (
                SELECT 1 FROM inventario i WHERE i.numero_inventario = p.numero_inventario_equipo
            )
        """)
        equipos_huerfanos = cursor.fetchone()[0]
        
        if prof_huerfanos == 0 and equipos_huerfanos == 0:
            print("   ✅ Integridad referencial: OK")
        else:
            if prof_huerfanos > 0:
                print(f"   ⚠️ Profesores huérfanos en préstamos: {prof_huerfanos}")
            if equipos_huerfanos > 0:
                print(f"   ⚠️ Equipos huérfanos en préstamos: {equipos_huerfanos}")
        
        conn.close()
        
        # Guardar estructura en archivo JSON para referencia
        try:
            with open('estructura_bd.json', 'w', encoding='utf-8') as f:
                json.dump(estructura_completa, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n💾 Estructura guardada en: estructura_bd.json")
        except Exception as e:
            print(f"⚠️ No se pudo guardar estructura: {e}")
        
        print("\n" + "=" * 70)
        print("✅ REVISIÓN DE ESTRUCTURA COMPLETADA")
        print("=" * 70)
        
    except Exception as e:
        print(f'❌ ERROR: {e}')

if __name__ == '__main__':
    revisar_estructura()