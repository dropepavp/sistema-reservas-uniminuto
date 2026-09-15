#!/usr/bin/env python
"""Debug the inventory API through the Flask app"""

from app import app
from flask import session as flask_session
from database import db, Inventario, Bodega

with app.app_context():
    # Simulate the session of admin user
    with app.test_request_context():
        # Set session variables
        flask_session['rol'] = 'admin'
        flask_session['sede_id'] = None
        flask_session['usuario'] = '9999999999'
        
        print("=== Simulando Sesión ===")
        print(f"Rol: {flask_session.get('rol')}")
        print(f"Sede ID: {flask_session.get('sede_id')}")
        
        # Test the query logic from api_items_disponibles
        print("\n=== Testeando lógica de API ===")
        
        try:
            query = Inventario.query.filter_by(estado='Disponible')
            print(f"Items con estado Disponible: {query.count()}")
            
            # Filtro por sede (como hace la API)
            if flask_session.get('rol') != 'admin' and flask_session.get('sede_id'):
                print("Aplicando filtro de sede (usuario no admin)")
                query = query.join(Inventario.bodega).filter(Bodega.sede_id == flask_session.get('sede_id'))
            else:
                print("NO aplicar filtro de sede (usuario admin o sin sede)")
            
            items = query.all()
            print(f"Items después del filtro: {len(items)}")
            
            if items:
                print(f"\nPrimer item: ID={items[0].numero_inventario}, Item={items[0].item}")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
