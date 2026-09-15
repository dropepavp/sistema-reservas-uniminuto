"""
Script para listar todos los usuarios y resetear credenciales
"""
import os

os.environ['DATABASE_URL'] = 'postgresql://postgres:Allison2023secure@127.0.0.1:5432/sistema_reserva'

print("="*60)
print("LISTADO DE USUARIOS EN LA BASE DE DATOS")
print("="*60)

try:
    from app_improved import create_app
    from database import db, Auxiliar
    from werkzeug.security import generate_password_hash
    
    app = create_app()
    
    with app.app_context():
        # Listar todos los usuarios
        usuarios = Auxiliar.query.all()
        
        print(f"\nTotal de usuarios: {len(usuarios)}\n")
        
        for idx, user in enumerate(usuarios, 1):
            print(f"{idx}. {user.documento}")
            print(f"   Nombre: {user.nombre_completo}")
            print(f"   Correo: {user.correo}")
            print(f"   Rol: {user.rol}")
            print()
        
        # Encontrar o crear un usuario admin para pruebas
        print("="*60)
        print("PREPARANDO USUARIO PARA PRUEBAS")
        print("="*60)
        
        # Buscar un usuario con rol 'admin' o 'auxiliar'
        admin_user = Auxiliar.query.filter_by(rol='admin').first()
        if not admin_user:
            admin_user = Auxiliar.query.first()
        
        if admin_user:
            # Resetear su contraseña a algo simple
            password = 'Prueba123'
            admin_user.contraseña = generate_password_hash(password)
            db.session.commit()
            
            print(f"\n✓ Usuario de prueba preparado:")
            print(f"\n  Documento: {admin_user.documento}")
            print(f"  Contraseña: {password}")
            print(f"\nUsa estas credenciales para acceder a:")
            print(f"  http://127.0.0.1:5000/login")
        else:
            print("\n✗ No hay usuarios en la base de datos")
            print("\nCreando usuario de prueba...")
            
            new_user = Auxiliar(
                documento='80140666',
                nombre_completo='Usuario Prueba',
                correo='test@sistema.edu.co',
                contraseña=generate_password_hash('Prueba123'),
                rol='admin'
            )
            db.session.add(new_user)
            db.session.commit()
            
            print(f"✓ Usuario creado:")
            print(f"\n  Documento: 80140666")
            print(f"  Contraseña: Prueba123")
            
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
