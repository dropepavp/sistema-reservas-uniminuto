#!/usr/bin/env python
"""
Actualizar contraseña para el usuario numérico existente
"""

from flask import Flask
from database import db, Auxiliar
from config import config
from werkzeug.security import generate_password_hash
import os

# Configurar la aplicación
app = Flask(__name__)
config_name = os.getenv('FLASK_CONFIG', 'default')
app.config.from_object(config[config_name])
db.init_app(app)

def update_user_password():
    """Actualizar contraseña del usuario numérico existente"""
    with app.app_context():
        try:
            # Buscar el usuario numérico
            usuario = Auxiliar.query.filter_by(documento="80140666").first()
            
            if usuario:
                # Crear nueva contraseña válida (8+ caracteres)
                nueva_password = "12345678"  # Contraseña de 8 dígitos
                
                # Actualizar con hash
                usuario.contraseña = generate_password_hash(nueva_password)
                db.session.commit()
                
                print("✅ ¡Contraseña actualizada exitosamente!")
                print("=" * 60)
                print("🔑 CREDENCIALES PARA LOGIN:")
                print("=" * 60)
                print(f"👤 Usuario: {usuario.documento}")
                print(f"🔐 Contraseña: {nueva_password}")
                print(f"👥 Nombre: {usuario.nombre_completo}")
                print(f"🎭 Rol: {usuario.rol}")
                print("=" * 60)
                
                # También crear un usuario numérico adicional
                nuevo_usuario = Auxiliar.query.filter_by(documento="12345678").first()
                if not nuevo_usuario:
                    nuevo_usuario = Auxiliar(
                        documento="12345678",
                        nombre_completo="Usuario de Pruebas",
                        correo="pruebas@sistema.local",
                        contraseña=generate_password_hash("12345678"),
                        rol="admin"
                    )
                    db.session.add(nuevo_usuario)
                    db.session.commit()
                    
                    print("✅ Usuario adicional creado:")
                    print(f"👤 Usuario: 12345678")
                    print(f"🔐 Contraseña: 12345678")
                    print(f"🎭 Rol: admin")
                else:
                    # Actualizar contraseña si ya existe
                    nuevo_usuario.contraseña = generate_password_hash("12345678")
                    db.session.commit()
                    print("⚠️ Usuario 12345678 actualizado con nueva contraseña")
                
            else:
                print("❌ Usuario 80140666 no encontrado")
                
                # Crear usuario de respaldo
                usuario_respaldo = Auxiliar(
                    documento="99999999",
                    nombre_completo="Admin de Respaldo",
                    correo="respaldo@sistema.local",
                    contraseña=generate_password_hash("87654321"),
                    rol="admin"
                )
                db.session.add(usuario_respaldo)
                db.session.commit()
                
                print("✅ Usuario de respaldo creado:")
                print("👤 Usuario: 99999999")
                print("🔐 Contraseña: 87654321")
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: {e}")

def list_all_users():
    """Listar todos los usuarios con sus datos"""
    with app.app_context():
        try:
            usuarios = Auxiliar.query.all()
            print("\n📋 TODOS LOS USUARIOS DISPONIBLES:")
            print("=" * 60)
            
            for i, usuario in enumerate(usuarios, 1):
                print(f"{i}. 👤 Usuario: {usuario.documento}")
                print(f"   👥 Nombre: {usuario.nombre_completo}")
                print(f"   🎭 Rol: {usuario.rol}")
                print(f"   📧 Email: {usuario.correo}")
                print()
                
            if len(usuarios) > 0:
                print("🎯 CREDENCIALES ACTUALIZADAS PARA PROBAR:")
                print("   Usuario: 80140666 | Contraseña: 12345678")
                print("   Usuario: 12345678 | Contraseña: 12345678")
                
        except Exception as e:
            print(f"❌ Error al listar usuarios: {e}")

if __name__ == "__main__":
    print("🔧 Actualización de Credenciales")
    print("=" * 50)
    
    update_user_password()
    list_all_users()
    
    print("\n🌐 PARA PROBAR AHORA:")
    print("1. Ve a: http://127.0.0.1:5000/login")
    print("2. Usuario: 80140666")
    print("3. Contraseña: 12345678")
    print("\n🚀 ¡El servidor sigue corriendo - prueba ahora!")