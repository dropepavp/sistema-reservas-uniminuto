#!/usr/bin/env python
"""
Diagnóstico y corrección de contraseñas en el sistema.
Verifica usuarios en SQLite y PostgreSQL, y resetea contraseñas si es necesario.
"""
import os
import sys

print("=" * 60)
print("DIAGNÓSTICO DE CONTRASEÑAS - SISTEMA RESERVA")
print("=" * 60)

# ---- 1. Verificar SQLite ----
import sqlite3
db_path = os.path.join(os.path.dirname(__file__), 'sistema_prestamos.db')

if os.path.exists(db_path):
    print(f"\n[SQLite] Archivo encontrado: {db_path}")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in c.fetchall()]
    print(f"[SQLite] Tablas: {tables}")

    if 'auxiliares' in tables:
        c.execute("SELECT documento, nombre_completo, correo, rol, contraseña FROM auxiliares")
        users = c.fetchall()
        print(f"\n[SQLite] Usuarios en tabla 'auxiliares': {len(users)}")
        for u in users:
            doc, nombre, correo, rol, pwd = u
            print(f"  Documento: {doc}")
            print(f"  Nombre   : {nombre}")
            print(f"  Correo   : {correo}")
            print(f"  Rol      : {rol}")
            print(f"  Hash(30) : {str(pwd)[:30] if pwd else 'NULL'}")
            print()
    conn.close()
else:
    print(f"\n[SQLite] No encontrado: {db_path}")

# ---- 2. Verificar y corregir con PostgreSQL (via app) ----
print("\n" + "=" * 60)
print("VERIFICANDO POSTGRESQL...")
print("=" * 60)

try:
    from werkzeug.security import generate_password_hash, check_password_hash
    from app_improved import create_app
    from database import db, Auxiliar

    app = create_app()
    with app.app_context():
        users = Auxiliar.query.all()
        print(f"\n[PostgreSQL] Total de usuarios: {len(users)}")
        for u in users:
            print(f"\n  Documento: {u.documento}")
            print(f"  Nombre   : {u.nombre_completo}")
            print(f"  Correo   : {u.correo}")
            print(f"  Rol      : {u.rol}")
            print(f"  Hash(40) : {str(u.contraseña)[:40] if u.contraseña else 'NULL'}")

            # Probar contraseñas comunes
            contraseñas_prueba = ['Prueba123', 'admin123', 'Admin123', '123456', 'password1', 'Uniminuto1']
            for pwd_test in contraseñas_prueba:
                try:
                    if check_password_hash(u.contraseña, pwd_test):
                        print(f"  ✓ Contraseña correcta: '{pwd_test}'")
                        break
                except Exception:
                    pass
            else:
                print(f"  ✗ Ninguna contraseña de prueba coincide")

        print("\n" + "=" * 60)
        print("¿Desea resetear la contraseña de un usuario? (s/n): ", end="")
        respuesta = input().strip().lower()

        if respuesta == 's':
            print("Documento del usuario a resetear: ", end="")
            doc = input().strip()
            usuario = Auxiliar.query.get(doc)
            if not usuario:
                print(f"  ✗ Usuario '{doc}' no encontrado")
            else:
                print(f"  Usuario encontrado: {usuario.nombre_completo}")
                print("Nueva contraseña (mín. 8 chars, debe tener letra y número): ", end="")
                nueva_pwd = input().strip()
                if len(nueva_pwd) >= 8 and any(c.isdigit() for c in nueva_pwd) and any(c.isalpha() for c in nueva_pwd):
                    usuario.contraseña = generate_password_hash(nueva_pwd)
                    db.session.commit()
                    print(f"  ✓ Contraseña actualizada para '{doc}'")
                    print(f"  ✓ Verificación: {check_password_hash(usuario.contraseña, nueva_pwd)}")
                else:
                    print("  ✗ Contraseña no cumple los requisitos (mín. 8 chars, letra y número)")

except Exception as e:
    print(f"[PostgreSQL] Error: {e}")
    import traceback
    traceback.print_exc()

print("\n[Fin del diagnóstico]")
