import sys, os
sys.path.insert(0, os.path.abspath('.'))

import unittest
from app import create_app
from database import db, Sede, Inventario

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True

with app.app_context():
    # 1. Test Jinja2 compilation and rendering
    print("Testing template compilation...")
    app.jinja_env.get_template('inventario.html')
    print("Template compiled successfully!")

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

    res = client.get('/inventario/')
    assert res.status_code == 200, f"Expected 200 but got {res.status_code}"

    html = res.data.decode('utf-8')
    assert 'bulkEditModelModal' in html, "Missing bulkEditModelModal"
    assert 'btnOpenBulkEditModel' in html, "Missing btnOpenBulkEditModel"
    assert 'editPropagarFoto' in html, "Missing editPropagarFoto"
    assert 'btnReplicarFotoModeloDirecto' in html, "Missing btnReplicarFotoModeloDirecto"
    assert 'addPropagarFoto' in html, "Missing addPropagarFoto"
    assert 'formBulkEditModelo' in html, "Missing formBulkEditModelo"
    assert 'data-modelo=' in html, "Missing data-modelo in table rows"
    print("All UI elements present in /inventario/ HTML!")

    # 2. Test propagar_foto_modelo endpoint
    # Find items with the same valid model (ignoring 'nan', 'none')
    items_hp = Inventario.query.filter(Inventario.marca_modelo.ilike('%HP%')).all()
    if items_hp and len(items_hp) > 1:
        item1 = items_hp[0]
        modelo = item1.marca_modelo
        items_mismo_modelo = Inventario.query.filter(Inventario.marca_modelo == modelo).all()
        print(f"Found {len(items_mismo_modelo)} items with model '{modelo}'")

        # Assign test photo to item1
        test_url = '/static/uploads/equipos/test_modelo_prop.webp'
        item1.foto_url = test_url
        db.session.commit()

        # Call propagar_foto_modelo
        res_prop = client.post('/inventario/propagar_foto_modelo', json={'item_id': item1.id})
        print("propagar_foto_modelo status:", res_prop.status_code)
        assert res_prop.status_code == 200
        prop_data = res_prop.get_json()
        print("Response:", prop_data)
        assert prop_data['success'] is True

        # Verify other items with same model received the photo
        for it in items_mismo_modelo:
            it_refreshed = Inventario.query.get(it.id)
            assert it_refreshed.foto_url == test_url, f"Item {it.id} does not have propagated foto_url"
        print(f"Verified all {len(items_mismo_modelo)} items received the propagated image!")

    # 3. Test bulk_edit_modelo endpoint
    items_to_edit = Inventario.query.limit(3).all()
    if items_to_edit:
        ids = [i.id for i in items_to_edit]
        serials_antes = {i.id: i.serial for i in items_to_edit}
        num_inv_antes = {i.id: i.numero_inventario for i in items_to_edit}

        payload = {
            'item_ids': ','.join(map(str, ids)),
            'procesador': 'AMD Ryzen 7 PRO 5850U',
            'ram_gb': '32 GB DDR4',
            'almacenamiento': '1 TB SSD NVMe',
            'sistema_operativo': 'Windows 11 Pro Edu',
            'observaciones': 'Actualización masiva de prueba'
        }

        res_bulk = client.post('/inventario/bulk_edit_modelo', data=payload)
        print("bulk_edit_modelo status:", res_bulk.status_code)
        assert res_bulk.status_code == 200
        bulk_data = res_bulk.get_json()
        print("Response:", bulk_data)
        assert bulk_data['success'] is True
        assert bulk_data['count'] == len(ids)

        # Verify DB updates
        for it_id in ids:
            it = Inventario.query.get(it_id)
            assert it.procesador == 'AMD Ryzen 7 PRO 5850U'
            assert it.ram_gb == '32 GB DDR4'
            assert it.almacenamiento == '1 TB SSD NVMe'
            assert it.sistema_operativo == 'Windows 11 Pro Edu'
            assert it.observaciones == 'Actualización masiva de prueba'
            # Verify unique identifiers remained untouched!
            assert it.serial == serials_antes[it_id]
            assert it.numero_inventario == num_inv_antes[it_id]

        print("Verified all items updated and unique serials/inventory numbers remained completely intact!")

    print("=== ALL BULK EDIT MODEL & PHOTO PROPAGATION TESTS PASSED! ===")
