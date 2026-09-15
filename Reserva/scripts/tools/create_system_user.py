#!/usr/bin/env python
"""
Crear usuario usando las funciones nativas del sistema
"""

# Importar las clases y funciones del sistema
from database import db, init_db, Auxiliar
from config import config
from flask import Flask
import os

# Configurar la aplicación temporal para crear usuarios
app = Flask(__name__)
config_name = os.getenv('FLASK_CONFIG', 'default')
app.config.from_object(config[config_name])
db.init_app(app)

def create_test_users():
    """Crear usuarios de prueba usando las clases del sistema"""
    
    with app.app_context():
        try:
            # Inicializar la base de datos si no existe
            db.create_all()
            
            # Usuario administrador principal
            admin_doc = "12345678"
            admin_user = Auxiliar.query.filter_by(documento=admin_doc).first()
            
            if not admin_user:
                from werkzeug.security import generate_password_hash
                
                # Crear usuario administrador
                admin_user = Auxiliar(
                    documento=admin_doc,
                    nombre_completo="Administrador Principal",
                    correo="admin@sistema.com",
                    contraseña=generate_password_hash("123456"),
                    rol="admin"
                )
                db.session.add(admin_user)
                print("✅ Usuario administrador creado")
            else:
                # Actualizar contraseña si ya existe
                from werkzeug.security import generate_password_hash
                admin_user.contraseña = generate_password_hash("123456")
                print("⚠️ Usuario administrador actualizado")
            
            # Usuario auxiliar
            aux_doc = "87654321"
            aux_user = Auxiliar.query.filter_by(documento=aux_doc).first()
            
            if not aux_user:
                from werkzeug.security import generate_password_hash
                
                aux_user = Auxiliar(
                    documento=aux_doc,
                    nombre_completo="Usuario Auxiliar",
                    correo="auxiliar@sistema.com",
                    contraseña=generate_password_hash("123456"),
                    rol="auxiliar"
                )
                db.session.add(aux_user)
                print("✅ Usuario auxiliar creado")
            else:
                from werkzeug.security import generate_password_hash
                aux_user.contraseña = generate_password_hash("123456")
                print("⚠️ Usuario auxiliar actualizado")
            
            # Guardar cambios
            db.session.commit()
            
            print("\n🎉 ¡Usuarios creados/actualizados exitosamente!")
            print("=" * 60)
            print("🔑 CREDENCIALES PARA PRUEBAS:")
            print("=" * 60)
            print("👤 ADMINISTRADOR:")
            print(f"   Usuario: {admin_doc}")
            print("   Contraseña: 123456")
            print("   Rol: admin")
            print()
            print("👤 AUXILIAR:")
            print(f"   Usuario: {aux_doc}")
            print("   Contraseña: 123456")
            print("   Rol: auxiliar")
            print("=" * 60)
            
            # Verificar que los usuarios fueron creados correctamente
            verify_users()
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error al crear usuarios: {e}")

def verify_users():
    """Verificar que los usuarios fueron creados correctamente"""
    try:
        usuarios = Auxiliar.query.all()
        print(f"\n📋 Total de usuarios en la base de datos: {len(usuarios)}")
        
        for usuario in usuarios:
            print(f"  - {usuario.documento} | {usuario.nombre_completo} | {usuario.rol}")
            
    except Exception as e:
        print(f"❌ Error al verificar usuarios: {e}")

def test_login_credentials():
    """Probar las credenciales como lo haría el sistema"""
    try:
        from werkzeug.security import check_password_hash
        
        print("\n🧪 PROBANDO CREDENCIALES:")
        print("=" * 40)
        
        # Probar usuario admin
        admin = Auxiliar.query.filter_by(documento="12345678").first()
        if admin:
            is_valid = check_password_hash(admin.contraseña, "123456")
            print(f"👤 Admin (12345678): {'✅ VÁLIDO' if is_valid else '❌ INVÁLIDO'}")
        else:
            print("👤 Admin (12345678): ❌ NO EXISTE")
        
        # Probar usuario auxiliar
        auxiliar = Auxiliar.query.filter_by(documento="87654321").first()
        if auxiliar:
            is_valid = check_password_hash(auxiliar.contraseña, "123456")
            print(f"👤 Auxiliar (87654321): {'✅ VÁLIDO' if is_valid else '❌ INVÁLIDO'}")
        else:
            print("👤 Auxiliar (87654321): ❌ NO EXISTE")
            
    except Exception as e:
        print(f"❌ Error al probar credenciales: {e}")

if __name__ == "__main__":
    print("🛠️ Creación de Usuarios del Sistema")
    print("=" * 50)
    
    create_test_users()
    test_login_credentials()
    
    print("\n🌐 PARA PROBAR:")
    print("1. Ve a: http://127.0.0.1:5000/login")
    print("2. Usuario: 12345678")
    print("3. Contraseña: 123456")
    print("\n🚀 ¡Listo para probar el sistema!")