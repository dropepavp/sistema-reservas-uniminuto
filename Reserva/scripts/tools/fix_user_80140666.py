#!/usr/bin/env python
"""Script para arreglar contraseña del usuario 80140666"""
import sys
from werkzeug.security import generate_password_hash
from app_improved import create_app
from database import db, Auxiliar

app = create_app()
with app.app_context():
    try:
        # Buscar usuario
        usuario = Auxiliar.query.filter_by(documento="80140666").first()
        
        if not usuario:
            print("Usuario no encontrado. Creando nuevo usuario admin...")
            nuevo_usuario = Auxiliar(
                documento="80140666",
                nombre_completo="Admin 80140666",
                correo="admin@sistema.com",
                contraseña=generate_password_hash("123456"),
                rol="admin"
            )
            db.session.add(nuevo_usuario)
            db.session.commit()
            print("✅ Usuario creado exitosamente")
            print("   Documento: 80140666")
            print("   Contraseña: 123456")
        else:
            # Actualizar contraseña
            usuario.contraseña = generate_password_hash("123456")
            db.session.commit()
            print("✅ Contraseña actualizada exitosamente")
            print("   Documento: 80140666")
            print("   Contraseña: 123456")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
