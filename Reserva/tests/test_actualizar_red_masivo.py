import sys, os
sys.path.insert(0, os.path.abspath('.'))

import io
import pandas as pd
from app import create_app
from database import db, Sede, Bodega, Inventario

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True

with app.app_context():
    # 1. Test template compilation
    print("Testing template compilation...")
    app.jinja_env.get_template('planillas.html')
    app.jinja_env.get_template('inventario.html')
    print("Templates compiled successfully!")

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['usuario_id'] = 1
        sess['usuario'] = 'Admin'
        sess['rol'] = 'admin'
        sess['sede_id'] = 1
        sess['sede_nombre'] = 'Principal'

    # 2. Test downloading both templates
    res_inv_tmpl = client.get('/planillas/plantilla/inventario')
    assert res_inv_tmpl.status_code == 200, f"Expected 200 but got {res_inv_tmpl.status_code}"
    df_inv_tmpl = pd.read_excel(io.BytesIO(res_inv_tmpl.data))
    assert 'hostname' in df_inv_tmpl.columns, "Column 'hostname' not found in full inventory template!"
    print("Full inventory template has 'hostname' column verified!")

    res_red_tmpl = client.get('/planillas/descargar_plantilla_actualizacion_red')
    assert res_red_tmpl.status_code == 200, f"Expected 200 but got {res_red_tmpl.status_code}"
    df_red_tmpl = pd.read_excel(io.BytesIO(res_red_tmpl.data))
    assert 'hostname' in df_red_tmpl.columns
    assert 'numero_inventario' in df_red_tmpl.columns
    assert 'ubicacion_permanente' in df_red_tmpl.columns
    print("Dedicated Red/Hostname template generated and columns verified!")

    # 3. Create 3 test items in database
    items_test = [
        Inventario(
            categoria="Equipos Portátiles",
            item="PORTATIL MASIVO RED 1",
            marca_modelo="HP PROBOOK 445 G9",
            serial="SN-TEST-MASIV-01",
            numero_inventario="INV-RED-001",
            ubicacion_permanente="Estante A",
            bodega_id=1
        ),
        Inventario(
            categoria="Equipos Portátiles",
            item="PORTATIL MASIVO RED 2",
            marca_modelo="HP PROBOOK 445 G9",
            serial="SN-TEST-MASIV-02",
            numero_inventario="INV-RED-002",
            ubicacion_permanente="Estante A",
            bodega_id=1
        ),
        Inventario(
            categoria="Pantallas Digitales Interactivas",
            item="ONE SCREEN TEST 3",
            marca_modelo="ONE SCREEN",
            serial="SN-TEST-MASIV-03",
            numero_inventario="INV-RED-003",
            ubicacion_permanente="Sala 1",
            bodega_id=1
        )
    ]
    for it in items_test:
        db.session.add(it)
    db.session.commit()
    print("3 Test equipment inserted into database.")

    # 4. Prepare upload Excel to update hostnames and locations without touching other fields
    upload_data = [
        {
            'numero_inventario': 'INV-RED-001',
            'serial': 'SN-TEST-MASIV-01',
            'hostname': 'LAB101-PC01',
            'ubicacion_permanente': 'Laboratorio 101, Puesto 01'
        },
        {
            'numero_inventario': 'INV-RED-002',
            'serial': 'SN-TEST-MASIV-02',
            'hostname': 'LAB101-PC02',
            'ubicacion_permanente': 'Laboratorio 101, Puesto 02'
        },
        {
            # Test lookup purely by serial!
            'numero_inventario': '',
            'serial': 'SN-TEST-MASIV-03',
            'hostname': 'ONESCREEN-SALA-B',
            'ubicacion_permanente': 'Auditorio Principal'
        }
    ]
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        pd.DataFrame(upload_data).to_excel(writer, sheet_name='Actualizacion_Red', index=False)
    excel_buffer.seek(0)

    # 5. POST to /planillas/actualizar_red_masivo
    res_upload = client.post(
        '/planillas/actualizar_red_masivo',
        data={'archivo_excel': (excel_buffer, 'carga_red_test.xlsx')},
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    print("actualizar_red_masivo status code:", res_upload.status_code)
    assert res_upload.status_code == 200
    upload_res_json = res_upload.get_json()
    print("Upload response:", upload_res_json)
    assert upload_res_json['actualizados'] == 3

    # 6. Verify in database
    it1 = Inventario.query.filter_by(numero_inventario='INV-RED-001').first()
    assert it1.hostname == 'LAB101-PC01'
    assert it1.ubicacion_permanente == 'Laboratorio 101, Puesto 01'
    assert it1.item == 'PORTATIL MASIVO RED 1'  # Not altered!
    assert it1.marca_modelo == 'HP PROBOOK 445 G9'  # Not altered!

    it2 = Inventario.query.filter_by(numero_inventario='INV-RED-002').first()
    assert it2.hostname == 'LAB101-PC02'
    assert it2.ubicacion_permanente == 'Laboratorio 101, Puesto 02'

    it3 = Inventario.query.filter_by(serial='SN-TEST-MASIV-03').first()
    assert it3.hostname == 'ONESCREEN-SALA-B'
    assert it3.ubicacion_permanente == 'Auditorio Principal'
    print("Database verification confirmed: Hostnames and Locations updated without touching any other fields!")

    # Clean up test items
    for it in [it1, it2, it3]:
        if it:
            db.session.delete(it)
    db.session.commit()
    print("Cleaned up test items.")

    print("=== ALL PLANILLAS & BULK UPDATE TESTS PASSED! ===")
