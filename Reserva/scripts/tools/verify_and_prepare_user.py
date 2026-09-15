"""
Script para verificar y preparar el usuario 80140666
"""
import os
import sys

os.environ['DATABASE_URL'] = 'postgresql://postgres:Allison2023secure@127.0.0.1:5432/sistema_reserva'

print("="*60)
print("VERIFICACIÓN DEL USUARIO 80140666")
print("="*60)

try:
    # Importar después de establecer el env
    from app_improved import create_app
    from database import db, Auxiliar
    from werkzeug.security import generate_password_hash
    
    app = create_app()
    
    with app.app_context():
        # Verificar que el usuario existe
        user = Auxiliar.query.get('80140666')
        
        if user:
            print(f"\n✓ Usuario encontrado:")
            print(f"  Documento: {user.documento}")
            print(f"  Nombre: {user.nombre_completo}")
            print(f"  Correo: {user.correo}")
            print(f"  Rol: {user.rol}")
            print(f"  Sede: {user.sede_id}")
            
            # Opcional: resetear la contraseña a una conocida
            new_password = 'Admin123'
            user.contraseña = generate_password_hash(new_password)
            db.session.commit()
            
            print(f"\n✓ Contraseña actualizada a: {new_password}")
            print(f"\n✓ Usuario listo para login")
            
        else:
            print(f"\n✗ Usuario 80140666 no encontrado")
            print(f"\nCreando nuevo usuario...")
            
            new_user = Auxiliar(
                documento='80140666',
                nombre_completo='Admin Sistema',
                correo='admin@reserva.edu.co',
                contraseña=generate_password_hash('Admin123'),
                rol='auxiliar'
            )
            db.session.add(new_user)
            db.session.commit()
            
            print(f"✓ Usuario creado exitosamente")
            print(f"  Documento: 80140666")
            print(f"  Contraseña: Admin123")
    
    print("\n" + "="*60)
    print("✓ SISTEMA LISTO PARA LOGIN")
    print("="*60)
    print(f"\nAccede a: http://127.0.0.1:5000/login")
    print(f"Usuario: 80140666")
    print(f"Contraseña: Admin123")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
