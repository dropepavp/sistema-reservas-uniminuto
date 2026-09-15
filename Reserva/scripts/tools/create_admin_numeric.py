#!/usr/bin/env python
"""
Crear usuario administrador con documento numérico válido
"""

import sqlite3
import hashlib
from werkzeug.security import generate_password_hash

def create_numeric_admin():
    """Crear usuario admin con documento numérico"""
    try:
        conn = sqlite3.connect('reserva.db')
        cursor = conn.cursor()
        
        # Crear tabla si no existe
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auxiliares (
                documento TEXT PRIMARY KEY,
                nombre_completo TEXT NOT NULL,
                correo TEXT NOT NULL,
                contraseña TEXT NOT NULL,
                rol TEXT DEFAULT 'auxiliar'
            )
        """)
        
        # Datos del administrador con documento numérico
        documento = "12345678"  # Documento numérico
        nombre = "Administrador Principal"
        email = "admin@sistema.com"
        password = "123456"  # Contraseña simple para pruebas
        rol = "admin"
        
        # Hash de la contraseña
        password_hash = generate_password_hash(password)
        
        # Verificar si ya existe
        cursor.execute("SELECT documento FROM auxiliares WHERE documento = ?", (documento,))
        if cursor.fetchone():
            print("⚠️ Actualizando usuario administrador existente...")
            # Actualizar usuario existente
            cursor.execute("""
                UPDATE auxiliares 
                SET nombre_completo = ?, correo = ?, contraseña = ?, rol = ?
                WHERE documento = ?
            """, (nombre, email, password_hash, rol, documento))
        else:
            print("✅ Creando nuevo usuario administrador...")
            # Insertar nuevo usuario
            cursor.execute("""
                INSERT INTO auxiliares (documento, nombre_completo, correo, contraseña, rol)
                VALUES (?, ?, ?, ?, ?)
            """, (documento, nombre, email, password_hash, rol))
        
        conn.commit()
        conn.close()
        
        print("🎉 Usuario administrador configurado exitosamente!")
        print("="*50)
        print("🔑 CREDENCIALES DE ACCESO:")
        print("="*50)
        print(f"👤 Usuario (Documento): {documento}")
        print(f"🔐 Contraseña: {password}")
        print(f"🎭 Rol: {rol}")
        print(f"📧 Email: {email}")
        print("="*50)
        print("🌐 Para acceder:")
        print("1. Ve a: http://127.0.0.1:5000/login")
        print(f"2. Usuario: {documento}")
        print(f"3. Contraseña: {password}")
        
    except Exception as e:
        print(f"❌ Error al crear usuario administrador: {e}")

def create_multiple_users():
    """Crear varios usuarios de prueba"""
    try:
        conn = sqlite3.connect('reserva.db')
        cursor = conn.cursor()
        
        usuarios = [
            {
                'documento': '87654321',
                'nombre': 'Usuario Auxiliar',
                'email': 'auxiliar@sistema.com',
                'password': '123456',
                'rol': 'auxiliar'
            },
            {
                'documento': '11111111',
                'nombre': 'Profesor Test',
                'email': 'profesor@sistema.com',
                'password': '123456',
                'rol': 'auxiliar'
            }
        ]
        
        for usuario in usuarios:
            password_hash = generate_password_hash(usuario['password'])
            
            # Insertar o actualizar
            cursor.execute("""
                INSERT OR REPLACE INTO auxiliares 
                (documento, nombre_completo, correo, contraseña, rol)
                VALUES (?, ?, ?, ?, ?)
            """, (usuario['documento'], usuario['nombre'], usuario['email'], 
                  password_hash, usuario['rol']))
        
        conn.commit()
        conn.close()
        
        print("\n✅ Usuarios adicionales creados:")
        for usuario in usuarios:
            print(f"  - {usuario['documento']} ({usuario['nombre']}) - {usuario['rol']}")
        
    except Exception as e:
        print(f"❌ Error al crear usuarios adicionales: {e}")

if __name__ == "__main__":
    print("🛠️ Configuración de Usuario Administrador")
    print("="*50)
    
    # Crear admin principal
    create_numeric_admin()
    
    # Crear usuarios adicionales
    create_multiple_users()
    
    print("\n🚀 ¡Listo! Ya puedes probar el sistema")