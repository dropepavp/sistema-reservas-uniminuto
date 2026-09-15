"""
Script para resetear todas las contraseñas a un estándar
"""
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:Allison2023secure@127.0.0.1:5432/sistema_reserva'

from app_improved import create_app
from database import db, Auxiliar
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    print("="*60)
    print("RESETEANDO TODAS LAS CONTRASEÑAS")
    print("="*60)
    
    # Nueva contraseña estándar
    new_password = 'Sistema2026'
    hashed = generate_password_hash(new_password)
    
    # Obtener todos los usuarios
    usuarios = Auxiliar.query.all()
    
    print(f"\nActualizando {len(usuarios)} usuarios...")
    
    for user in usuarios:
        user.contraseña = hashed
        print(f"  ✓ {user.documento}: {user.nombre_completo}")
    
    db.session.commit()
    
    print("\n" + "="*60)
    print("✓ TODAS LAS CONTRASEÑAS ACTUALIZADAS")
    print("="*60)
    print(f"\nNueva contraseña para TODOS los usuarios: {new_password}")
    print(f"\nIntenta login con cualquier usuario:")
    
    for user in usuarios:
        print(f"  - Usuario: {user.documento}")
    
    print(f"\nURL: http://127.0.0.1:5000/login")
