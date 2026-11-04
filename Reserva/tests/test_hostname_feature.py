import sys, os
sys.path.insert(0, os.path.abspath('.'))

import unittest
from app import create_app
from database import db, Sede, Inventario

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True

with app.app_context():
    # 1. Test template compilation
    print("Testing template compilation...")
    app.jinja_env.get_template('inventario.html')
    app.jinja_env.get_template('hoja_vida_equipo.html')
    print("Templates compiled successfully!")

    client = app.test_client()
    sede = Sede.query.first()
    sede_id = sede.id if sede else 1
    sede_nombre = sede.nombre if sede else 'SEDE PRINCIPAL'

    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['usuario_id'] = 1
        sess['usuario'] = 'Admin'
        sess['rol'] = 'admin'
        sess['sede_id'] = sede_id
        sess['sede_nombre'] = sede_nombre

    # 2. Render inventario page
    res = client.get('/inventario/')
    assert res.status_code == 200, f"Expected 200 but got {res.status_code}"
    html = res.data.decode('utf-8')
    assert 'id="hostname"' in html, "Missing hostname input in formInventario"
    assert 'id="editHostname"' in html, "Missing editHostname input in editModal"
    assert 'data-hostname=' in html, "Missing data-hostname attribute in table rows"
    print("HTML checks passed for inventario.html!")

    # 3. Create a test equipment with hostname
    test_hostname = "PRUEBA-PC-NET01"
    nuevo_item = Inventario(
        categoria="Equipos Portátiles",
        item="PORTATIL HP TEST HOSTNAME",
        marca_modelo="HP PROBOOK 445 G9",
        serial="SN-TEST-HOST-999",
        numero_inventario="INV-TEST-HOST-999",
        hostname=test_hostname,
        procesador="AMD Ryzen 7 5825U",
        ram_gb="16 GB",
        almacenamiento="512 GB SSD",
        sistema_operativo="Windows 11 Pro",
        bodega_id=1
    )
    db.session.add(nuevo_item)
    db.session.commit()
    print(f"Created test equipment ID #{nuevo_item.id} with hostname '{nuevo_item.hostname}'")

    # 4. Test GET /inventario/editar/<id> returns hostname
    res_get = client.get(f'/inventario/editar/{nuevo_item.id}')
    assert res_get.status_code == 200
    item_json = res_get.get_json()['item']
    assert item_json['hostname'] == test_hostname, f"Expected {test_hostname} but got {item_json.get('hostname')}"
    print("GET /inventario/editar/<id> successfully returned hostname!")

    # 5. Test POST /inventario/editar/<id> updates hostname
    updated_hostname = "PRUEBA-PC-MOD02"
    res_edit = client.post(f'/inventario/editar/{nuevo_item.id}', data={
        'categoria': 'Equipos Portátiles',
        'item': 'PORTATIL HP TEST HOSTNAME',
        'marca_modelo': 'HP PROBOOK 445 G9',
        'serial': 'SN-TEST-HOST-999',
        'numero_inventario': 'INV-TEST-HOST-999',
        'hostname': updated_hostname,
        'procesador': 'AMD Ryzen 7 5825U'
    })
    assert res_edit.status_code == 200
    refreshed_item = db.session.get(Inventario, nuevo_item.id)
    assert refreshed_item.hostname == updated_hostname
    print(f"POST /inventario/editar/<id> updated hostname to '{refreshed_item.hostname}' successfully!")

    # 6. Test search by hostname in InventarioService
    res_search = client.get(f'/inventario/?busqueda={updated_hostname}')
    assert res_search.status_code == 200
    html_search = res_search.data.decode('utf-8')
    assert updated_hostname in html_search, "Search by hostname did not find the item!"
    print("Search by hostname verified successfully!")

    # 7. Test Hoja de Vida display and edit
    res_hv = client.get(f'/mantenimiento/hoja-de-vida/{nuevo_item.id}')
    assert res_hv.status_code == 200
    html_hv = res_hv.data.decode('utf-8')
    assert updated_hostname in html_hv, "Hostname not displayed on Hoja de Vida!"
    assert 'Hostname / Nombre de Red' in html_hv
    print("Hoja de Vida displays hostname correctly!")

    # Clean up test equipment
    db.session.delete(refreshed_item)
    db.session.commit()
    print("Test equipment cleaned up.")

    print("=== ALL HOSTNAME VERIFICATIONS PASSED SUCCESSFULLY! ===")

