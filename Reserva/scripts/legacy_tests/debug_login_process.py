"""
Script para debuggear exactamente qué pasa cuando se intenta login
"""
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:Allison2023secure@127.0.0.1:5432/sistema_reserva'

from app_improved import create_app
from database import db, Auxiliar
from validators import DataValidator
from werkzeug.security import check_password_hash

app = create_app()

with app.app_context():
    print("="*60)
    print("DEBUGGING EXACTO DEL PROCESO DE LOGIN")
    print("="*60)
    
    # Simular lo que hace el login
    documento_input = 'admin'
    contraseña_input = 'Prueba123'
    
    print(f"\nEntrada del formulario:")
    print(f"  usuario (documento_input): '{documento_input}'")
    print(f"  contraseña_input: '{contraseña_input}'")
    
    # Paso 1: Validar documento
    print(f"\nPaso 1: Validar documento con DataValidator.validate_cedula()")
    doc_valid, doc_value, doc_error = DataValidator.validate_cedula(documento_input)
    print(f"  Válido: {doc_valid}")
    print(f"  Valor procesado: {repr(doc_value)} (tipo: {type(doc_value).__name__})")
    print(f"  Error: '{doc_error}'")
    
    if not doc_valid:
        print("\n✗ FALLO: Documento no válido")
        exit(1)
    
    # Paso 2: Convertir a string
    print(f"\nPaso 2: Convertir a string")
    documento_str = str(doc_value)
    print(f"  documento_str: '{documento_str}' (tipo: {type(documento_str).__name__})")
    
    # Paso 3: Buscar usuario
    print(f"\nPaso 3: Buscar usuario en BD")
    print(f"  Ejecutando: Auxiliar.query.get('{documento_str}')")
    usuario = Auxiliar.query.get(documento_str)
    
    if not usuario:
        print(f"  ✗ Usuario no encontrado")
        exit(1)
    
    print(f"  ✓ Usuario encontrado:")
    print(f"    documento: {usuario.documento}")
    print(f"    nombre: {usuario.nombre_completo}")
    print(f"    hash: {usuario.contraseña[:50]}...")
    
    # Paso 4: Verificar contraseña
    print(f"\nPaso 4: Verificar contraseña")
    print(f"  Ejecutando: check_password_hash(usuario.contraseña, '{contraseña_input}')")
    
    try:
        is_valid = check_password_hash(usuario.contraseña, contraseña_input)
        print(f"  Resultado: {is_valid}")
        
        if is_valid:
            print(f"\n✓ LOGIN EXITOSO")
        else:
            print(f"\n✗ CONTRASEÑA INCORRECTA")
            print(f"  Probando otras contraseñas comunes:")
            
            for pwd in ['Prueba123', 'prueba123', 'Admin123', 'admin123', 'Aux123', '123456']:
                result = check_password_hash(usuario.contraseña, pwd)
                print(f"    '{pwd}': {result}")
                
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
