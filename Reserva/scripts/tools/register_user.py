#!/usr/bin/env python
"""
Script simple para registrar usuarios usando la función nativa del sistema
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importar la aplicación y sus funciones
from flask import Flask
from database import db
from config import config

# Crear una instancia de la aplicación
app = Flask(__name__)
config_name = os.getenv('FLASK_CONFIG', 'default')
app.config.from_object(config[config_name])
db.init_app(app)

def register_admin_user():
    """Registrar usuario administrador usando la función del sistema"""
    with app.app_context():
        try:
            # Importar la función de registro del sistema
            from app import registrar_auxiliar
            
            # Datos del usuario administrador
            documento = "12345678"
            nombre_completo = "Administrador de Pruebas"
            correo = "admin.pruebas@sistema.com"  # Email único
            contraseña = "123456"
            rol = "admin"
            
            # Intentar registrar el usuario
            resultado, mensaje = registrar_auxiliar(documento, nombre_completo, correo, contraseña, rol)
            
            if resultado:
                print("✅ Usuario administrador registrado exitosamente!")
                print("=" * 60)
                print("🔑 CREDENCIALES PARA LOGIN:")
                print("=" * 60)
                print(f"👤 Usuario: {documento}")
                print(f"🔐 Contraseña: {contraseña}")
                print(f"🎭 Rol: {rol}")
                print(f"📧 Email: {correo}")
                print("=" * 60)
                
                # Registrar también un usuario auxiliar
                aux_resultado, aux_mensaje = registrar_auxiliar(
                    "87654321", 
                    "Usuario Auxiliar de Pruebas", 
                    "auxiliar.pruebas@sistema.com", 
                    "123456", 
                    "auxiliar"
                )
                
                if aux_resultado:
                    print("✅ Usuario auxiliar también registrado!")
                    print(f"👤 Auxiliar: 87654321 | Contraseña: 123456")
                else:
                    print(f"⚠️ Usuario auxiliar: {aux_mensaje}")
                
            else:
                print(f"❌ Error al registrar usuario: {mensaje}")
                
                # Si ya existe, intentar con otro email
                if "ya existe" in mensaje.lower():
                    print("🔄 Intentando con credenciales diferentes...")
                    
                    # Probar con documento diferente
                    resultado2, mensaje2 = registrar_auxiliar(
                        "99999999", 
                        "Admin Sistema", 
                        "admin.sistema@test.com", 
                        "123456", 
                        "admin"
                    )
                    
                    if resultado2:
                        print("✅ Usuario creado con documento alternativo!")
                        print("🔑 USA ESTAS CREDENCIALES:")
                        print("👤 Usuario: 99999999")
                        print("🔐 Contraseña: 123456")
                    else:
                        print(f"❌ También falló: {mensaje2}")
                
        except Exception as e:
            print(f"❌ Error durante el registro: {e}")
            import traceback
            traceback.print_exc()

def test_existing_users():
    """Verificar usuarios existentes en la base de datos"""
    with app.app_context():
        try:
            from database import Auxiliar
            usuarios = Auxiliar.query.all()
            
            print(f"\n📋 Usuarios existentes en la base de datos ({len(usuarios)}):")
            for i, usuario in enumerate(usuarios, 1):
                print(f"  {i}. 🔑 {usuario.documento} | {usuario.nombre_completo} | {usuario.rol}")
                
            if len(usuarios) > 0:
                print("\n🎯 PRUEBA CON ALGUNO DE ESTOS USUARIOS:")
                print("Contraseña probablemente: 123456 o admin123")
                
        except Exception as e:
            print(f"❌ Error al verificar usuarios: {e}")

if __name__ == "__main__":
    print("🛠️ Registro de Usuario del Sistema")
    print("=" * 50)
    
    # Primero verificar usuarios existentes
    test_existing_users()
    
    print("\n" + "=" * 50)
    print("Registrando nuevo usuario administrador...")
    
    # Registrar nuevo usuario
    register_admin_user()
    
    print("\n🌐 PARA PROBAR EL SISTEMA:")
    print("1. Ve a: http://127.0.0.1:5000/login")
    print("2. Usa una de las credenciales mostradas arriba")
    print("3. ¡Explora las nuevas funcionalidades!")