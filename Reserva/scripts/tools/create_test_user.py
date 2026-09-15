#!/usr/bin/env python3
"""
Crear usuario de prueba con contraseña sencilla.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['DATABASE_URL'] = 'postgresql://postgres:Allison2023secure@localhost:5432/sistema_reserva'
os.environ['FLASK_ENV'] = 'development'

from app_improved import create_app
from werkzeug.security import generate_password_hash
from database import db, Auxiliar

app = create_app('development')

with app.app_context():
    # Borrar usuario de prueba anterior si existe
    user = Auxiliar.query.filter_by(documento='9999999999').first()
    if user:
        db.session.delete(user)
        db.session.commit()
        print("✓ Usuario anterior eliminado")
    
    # Crear usuario de prueba con contraseña simple
    hashed = generate_password_hash('test123')
    new_user = Auxiliar(
        documento='9999999999',
        nombre_completo='Usuario de Prueba',
        correo='prueba@test.com',
        contraseña=hashed,
        rol='admin'
    )
    db.session.add(new_user)
    db.session.commit()
    
    print("✅ Usuario creado:")
    print(f"   Documento: 9999999999")
    print(f"   Nombre: Usuario de  Prueba")
    print(f"   Rol: admin")
    print(f"   Contraseña: test123")
