#!/usr/bin/env python
"""
Script completo para gestión de usuarios del sistema
Incluye: verificar, crear, resetear contraseñas, cambiar roles
"""

import sqlite3
import hashlib

def check_users():
    """Verificar usuarios existentes"""
    try:
        conn = sqlite3.connect('sistema_prestamos.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT documento, nombre_completo, correo, rol FROM auxiliares")
        users = cursor.fetchall()
        
        print("👥 Usuarios registrados:")
        if users:
            for i, user in enumerate(users, 1):
                print(f"  {i}. 🔑 Documento: {user[0]}")
                print(f"     👤 Nombre: {user[1]}")
                print(f"     📧 Email: {user[2]}")
                print(f"     🎭 Rol: {user[3]}")
                print()
        else:
            print("  ⚠️ No hay usuarios registrados")
        
        conn.close()
        return users
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def reset_password():
    """Resetear contraseña de un usuario"""
    users = check_users()
    if not users:
        return
    
    print("🔄 Resetear Contraseña")
    documento = input("Ingresa el documento del usuario: ").strip()
    nueva_password = input("Ingresa la nueva contraseña: ").strip()
    
    if not documento or not nueva_password:
        print("❌ Documento y contraseña son requeridos")
        return
    
    try:
        conn = sqlite3.connect('sistema_prestamos.db')
        cursor = conn.cursor()
        
        # Verificar que el usuario existe
        cursor.execute("SELECT nombre_completo FROM auxiliares WHERE documento = ?", (documento,))
        user = cursor.fetchone()
        
        if not user:
            print(f"❌ Usuario {documento} no encontrado")
            conn.close()
            return
        
        # Hash de la nueva contraseña
        password_hash = hashlib.sha256(nueva_password.encode()).hexdigest()
        
        # Actualizar contraseña
        cursor.execute("""
            UPDATE auxiliares 
            SET contraseña = ? 
            WHERE documento = ?
        """, (password_hash, documento))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Contraseña actualizada exitosamente!")
        print(f"   👤 Usuario: {user[0]}")
        print(f"   🔑 Documento: {documento}")
        print(f"   🔐 Nueva contraseña: {nueva_password}")
        
    except Exception as e:
        print(f"❌ Error al resetear contraseña: {e}")

def create_user():
    """Crear un nuevo usuario"""
    print("👤 Crear Nuevo Usuario")
    documento = input("Documento: ").strip()
    nombre = input("Nombre completo: ").strip()
    email = input("Email: ").strip()
    password = input("Contraseña: ").strip()
    
    print("Roles disponibles:")
    print("1. admin (Administrador)")
    print("2. auxiliar (Usuario regular)")
    rol_opcion = input("Selecciona el rol (1-2): ").strip()
    
    rol = "admin" if rol_opcion == "1" else "auxiliar"
    
    if not all([documento, nombre, email, password]):
        print("❌ Todos los campos son requeridos")
        return
    
    try:
        conn = sqlite3.connect('sistema_prestamos.db')
        cursor = conn.cursor()
        
        # Verificar si ya existe
        cursor.execute("SELECT documento FROM auxiliares WHERE documento = ?", (documento,))
        if cursor.fetchone():
            print("❌ Ya existe un usuario con ese documento")
            conn.close()
            return
        
        # Hash de la contraseña
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Insertar usuario
        cursor.execute("""
            INSERT INTO auxiliares (documento, nombre_completo, correo, contraseña, rol)
            VALUES (?, ?, ?, ?, ?)
        """, (documento, nombre, email, password_hash, rol))
        
        conn.commit()
        conn.close()
        
        print("✅ Usuario creado exitosamente!")
        print(f"   🔑 Documento: {documento}")
        print(f"   👤 Nombre: {nombre}")
        print(f"   🎭 Rol: {rol}")
        
    except Exception as e:
        print(f"❌ Error al crear usuario: {e}")

def delete_user():
    """Eliminar un usuario"""
    users = check_users()
    if not users:
        return
    
    documento = input("Ingresa el documento del usuario a eliminar: ").strip()
    
    if not documento:
        print("❌ Documento requerido")
        return
    
    confirmacion = input(f"⚠️ ¿Estás seguro de eliminar el usuario {documento}? (si/no): ").strip().lower()
    
    if confirmacion not in ['si', 's', 'yes', 'y']:
        print("❌ Operación cancelada")
        return
    
    try:
        conn = sqlite3.connect('sistema_prestamos.db')
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM auxiliares WHERE documento = ?", (documento,))
        
        if cursor.rowcount > 0:
            conn.commit()
            print(f"✅ Usuario {documento} eliminado exitosamente")
        else:
            print(f"❌ Usuario {documento} no encontrado")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error al eliminar usuario: {e}")

def emergency_reset():
    """Reset de emergencia - crear usuario admin por defecto"""
    print("🚨 Reset de Emergencia")
    print("Esto creará un usuario administrador por defecto:")
    print("   Usuario: emergency")
    print("   Contraseña: emergency123")
    
    confirmacion = input("¿Continuar? (si/no): ").strip().lower()
    
    if confirmacion not in ['si', 's', 'yes', 'y']:
        print("❌ Operación cancelada")
        return
    
    try:
        conn = sqlite3.connect('sistema_prestamos.db')
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
        
        documento = "emergency"
        password = "emergency123"
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Insertar o actualizar usuario de emergencia
        cursor.execute("""
            INSERT OR REPLACE INTO auxiliares 
            (documento, nombre_completo, correo, contraseña, rol)
            VALUES (?, ?, ?, ?, ?)
        """, (documento, "Usuario Emergencia", "emergency@sistema.com", password_hash, "admin"))
        
        conn.commit()
        conn.close()
        
        print("✅ Usuario de emergencia creado!")
        print(f"   🔑 Usuario: {documento}")
        print(f"   🔐 Contraseña: {password}")
        
    except Exception as e:
        print(f"❌ Error en reset de emergencia: {e}")

def main_menu():
    """Menú principal"""
    while True:
        print("\n" + "="*50)
        print("🛠️ GESTIÓN DE USUARIOS - SISTEMA DE RESERVAS")
        print("="*50)
        print("1. Ver usuarios registrados")
        print("2. Crear nuevo usuario")
        print("3. Resetear contraseña")
        print("4. Eliminar usuario")
        print("5. Reset de emergencia")
        print("6. Salir")
        
        opcion = input("\n🔧 Selecciona una opción (1-6): ").strip()
        
        if opcion == "1":
            check_users()
        elif opcion == "2":
            create_user()
        elif opcion == "3":
            reset_password()
        elif opcion == "4":
            delete_user()
        elif opcion == "5":
            emergency_reset()
        elif opcion == "6":
            print("👋 ¡Hasta luego!")
            break
        else:
            print("❌ Opción inválida")

if __name__ == "__main__":
    main_menu()