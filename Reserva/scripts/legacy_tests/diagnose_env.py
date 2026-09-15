#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico del entorno y dependencias.
"""
import sys
import os
print("=" * 60)
print("DIAGNÓSTICO DEL ENTORNO")
print("=" * 60)

# Python version
print(f"\n[Python]")
print(f"  Versión: {sys.version}")
print(f"  Encoding: {sys.getdefaultencoding()}")

# psycopg2
try:
    import psycopg2
    print(f"\n[psycopg2]")
    print(f"  Versión: {psycopg2.__version__}")
    print(f"  Adaptado correctamente")
except Exception as e:
    print(f"  ERROR: {e}")

# SQLAlchemy
try:
    import sqlalchemy
    print(f"\n[SQLAlchemy]")
    print(f"  Versión: {sqlalchemy.__version__}")
except Exception as e:
    print(f"  ERROR: {e}")

# Flask-SQLAlchemy
try:
    import flask_sqlalchemy
    print(f"\n[Flask-SQLAlchemy]")
    print(f"  Versión: {flask_sqlalchemy.__version__}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n" + "=" * 60)
print("\nPara contactar a PostgreSQL, asegúrese de:")
print("1. PostgreSQL está corriendo (Services en Windows)")
print("2. El puerto 5432 está accesible")
print("3. Las credenciales son correctas")
print("4. pgAdmin o psql pueden conectar")
print("\nPor favor, verifique con pgAdmin que la base 'sistema_reserva' existe")
print("y que puede conectar con usuario 'postgres'.")

# Verificar si la URL de la base de datos necesita codificación
from urllib.parse import urlparse, unquote

db_url = os.environ.get('DATABASE_URL')
if db_url:
    parsed = urlparse(db_url)
    pwd = parsed.password or ''
    # si el password contiene caracteres ilegales y no está codificado
    if any(c in pwd for c in ["@", ":", "#", "%", "?", "/", "\"", "\\"]):
        print("\n[AVISO] La variable DATABASE_URL contiene caracteres especiales en la")
        print(" contraseña y puede provocar errores al iniciar. Use gen_database_url.py")
        print(" para obtener una versión codificada o edítela manualmente.")

