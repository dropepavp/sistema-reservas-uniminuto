"""
Script para verificar y corregir contraseña de admin
"""
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:Allison2023secure@127.0.0.1:5432/sistema_reserva'

from app_improved import create_app
from database import db, Auxiliar
from werkzeug.security import generate_password_hash, check_password_hash

app = create_app()

with app.app_context():
    print("="*60)
    print("VERIFICACIÓN Y CORRECCIÓN DE CONTRASEÑA ADMIN")
    print("="*60)
    
    # Buscar usuario admin
    admin = Auxiliar.query.get('admin')
    
    if not admin:
        print("\n✗ Usuario 'admin' no encontrado")
        print("Creando usuario admin...")
        
        admin = Auxiliar(
            documento='admin',
            nombre_completo='Administrador',
            correo='admin@sistema.com',
            contraseña=generate_password_hash('Prueba123'),
            rol='admin'
        )
        db.session.add(admin)
        db.session.commit()
        
        print("✓ Usuario admin creado")
    else:
        print(f"\n✓ Usuario encontrado:")
        print(f"  Documento: {admin.documento}")
        print(f"  Nombre: {admin.nombre_completo}")
        print(f"  Rol: {admin.rol}")
        
        # Probar contraseña actual
        test_password = 'Prueba123'
        is_valid = check_password_hash(admin.contraseña, test_password)
        print(f"\n  Contraseña '{test_password}' válida: {is_valid}")
        
        if not is_valid:
            print("\n  ⚠️ Contraseña no coincide, actualizando...")
            admin.contraseña = generate_password_hash('Prueba123')
            db.session.commit()
            
            # Verificar nuevamente
            is_valid = check_password_hash(admin.contraseña, test_password)
            print(f"  ✓ Contraseña actualizada: {is_valid}")
    
    print("\n" + "="*60)
    print("CREDENCIALES PARA LOGIN")
    print("="*60)
    print(f"\nUsuario: admin")
    print(f"Contraseña: Prueba123")
    print(f"\nAccede a: http://127.0.0.1:5000/login")
