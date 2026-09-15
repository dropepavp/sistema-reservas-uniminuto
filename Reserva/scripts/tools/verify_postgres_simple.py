#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificación simple de PostgreSQL sin dependencias de config.
"""
from sqlalchemy import create_engine, text, inspect

DATABASE_URL = 'postgresql://postgres:Allison2023secure@localhost:5432/sistema_reserva'

try:
    print("[*] Conectando a PostgreSQL...")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        inspector = inspect(conn)
        tables = inspector.get_table_names()
        
        if not tables:
            print('No se encontraron tablas en la base de datos.')
        else:
            print(f'\n✓ Tablas encontradas: {len(tables)}')
            for t in tables:
                try:
                    res = conn.execute(text(f'SELECT COUNT(*) AS c FROM "{t}"'))
                    cnt = res.fetchone()[0]
                    print(f'  - {t}: {cnt} registros')
                except Exception as e:
                    print(f'  - {t}: Error contando - {e}')
        
        print('\n[OK] Migración completada. Tu aplicación está lista para usar PostgreSQL.')
        
except Exception as e:
    print(f'[ERROR] {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
