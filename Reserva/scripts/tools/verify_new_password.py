"""
Verificar que admin/Sistema2026 funciona
"""
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:Allison2023secure@127.0.0.1:5432/sistema_reserva'

from app_improved import create_app

app = create_app()

with app.test_client() as client:
    print("Probando login con:")
    print("  Usuario: admin")
    print("  Contraseña: Sistema2026")
    
    response = client.post('/login', data={
        'usuario': 'admin',
        'contraseña': 'Sistema2026'
    }, follow_redirects=False)
    
    if response.status_code == 302 and response.headers.get('Location') == '/':
        print("\n✓ LOGIN EXITOSO!")
    else:
        print(f"\n✗ LOGIN FALLÓ (Status: {response.status_code})")
