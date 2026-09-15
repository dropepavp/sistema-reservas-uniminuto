#!/usr/bin/env python3
"""
Script de arranque: configura DATABASE_URL y arranca la aplicación con PostgreSQL.
Crea el engine con connect_args para evitar UnicodeDecodeError de psycopg2.
Uso en PowerShell:
    python .\run_with_postgres.py
"""
import os
import sys

# Configurar DATABASE_URL antes de cualquier otra cosa
# IMPORTANTE: Usa la contraseña correcta si el env var está mal
if not os.environ.get('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'postgresql://postgres:Allison2023secure@localhost:5432/sistema_reserva'
    print(f"✓ DATABASE_URL configurada: {os.environ['DATABASE_URL']}")
else:
    # Revalidate and fix if it contains bad characters
    db_url = os.environ.get('DATABASE_URL')
    if 'Allison2023*' in db_url:
        # Fix the password immediately
        db_url = db_url.replace('Allison2023*', 'Allison2023secure')
        os.environ['DATABASE_URL'] = db_url
        print(f"✓ DATABASE_URL corregida (se reemplazó Allison2023* por Allison2023secure)")
    else:
        print(f"✓ DATABASE_URL ya definida: {os.environ['DATABASE_URL'][:50]}...")

# Importar y ejecutar
try:
    # Create engine BEFORE importing app to bypass DSN parsing issues
    from sqlalchemy import create_engine, text
    from urllib.parse import urlparse
    
    # Get URL and fix it if needed
    db_url = os.environ.get('DATABASE_URL') or 'postgresql://postgres:Allison2023secure@localhost:5432/sistema_reserva'
    
    # Fix bad password if present
    if 'Allison2023*' in db_url:
        db_url = db_url.replace('Allison2023*', 'Allison2023secure')
        print(f"   (contraseña corregida de Allison2023* a Allison2023secure)")
    
    parsed = urlparse(db_url)
    
    # Build connect_args to avoid psycopg2 DSN parsing errors
    connect_args = {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'user': parsed.username or 'postgres',
        'password': parsed.password or 'Allison2023secure',
        'database': parsed.path.lstrip('/') or 'sistema_reserva',
        'client_encoding': 'utf8',
    }
    
    # Create engine with connect_args to bypass DSN parsing
    engine = create_engine('postgresql+psycopg2://', connect_args=connect_args, echo=False)
    
    # Verify connection works WITHOUT using Flask-SQLAlchemy's session
    print("✓ Probando conexión a PostgreSQL...")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Conexión a PostgreSQL verificada.\n")
    finally:
        engine.dispose()
    
    from app_improved import create_app
    from database import db
    
    app = create_app('development')
    print("✓ Aplicación creada exitosamente.")
    
    # IMPORTANT: Replace db.session.bind BEFORE app.run() so all queries use our engine
    with app.app_context():
        db.session.bind = engine

   
    print("=" * 60)
    print("🚀 Iniciando servidor Flask en http://localhost:5000")
    print("=" * 60)
    print("Presiona CTRL+C para detener.\n")
    
    app.run(debug=True, host='127.0.0.1', port=5000)
    
except Exception as e:
    print(f"❌ ERROR: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
