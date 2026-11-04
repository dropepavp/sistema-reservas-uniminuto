import sys, os
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from database import db, Sede, Ubicacion, Recurso, Reserva

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True

with app.app_context():
    # 1. Test Jinja2 compilation
    print("Testing template compilation...")
    app.jinja_env.get_template('reservas.html')
    app.jinja_env.get_template('salas_computo.html')
    print("Templates compiled successfully!")

    client = app.test_client()

    # 2. Test Sede Perdomo (Sede ID = 1)
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['usuario'] = 'Admin'
        sess['rol'] = 'admin'
        sess['sede_id'] = 1
        sess['sede_nombre'] = 'PERDOMO'

    res_perdomo = client.get('/reservas/recursos/1')
    assert res_perdomo.status_code == 200
    data_perdomo = res_perdomo.get_json()
    recs_perdomo = data_perdomo['ubicaciones'][0]['recursos']
    nombres_perdomo = [r['nombre'] for r in recs_perdomo]
    tipos_perdomo = set(r['tipo'] for r in recs_perdomo)

    print("PERDOMO Recursos verificados:")
    print(" - Total Aulas en Perdomo:", len(nombres_perdomo))
    print(" - Tipos encontrados:", tipos_perdomo)
    assert tipos_perdomo == {'Aula'}, f"Expected only Aula but got {tipos_perdomo}"
    assert '508' in nombres_perdomo, "Aula normal 508 not found in Perdomo"
    assert '703LS5' in nombres_perdomo, "Laboratorio 703LS5 not found in Perdomo"
    assert '704LS1' in nombres_perdomo, "Laboratorio 704LS1 not found in Perdomo"

    # 3. Test Sede Engativa (Sede ID = 2)
    res_eng = client.get('/reservas/recursos/2')
    assert res_eng.status_code == 200
    data_eng = res_eng.get_json()
    all_eng_recs = []
    for u in data_eng['ubicaciones']:
        all_eng_recs.extend(u['recursos'])
    
    nombres_eng = [r['nombre'] for r in all_eng_recs]
    tipos_eng = set(r['tipo'] for r in all_eng_recs)

    print("\nENGATIVÁ Recursos verificados:")
    print(" - Total Recursos en Engativá:", len(nombres_eng))
    print(" - Tipos encontrados:", tipos_eng)
    assert 'Aula' in tipos_eng
    assert 'A502' in nombres_eng, "Aula normal A502 not found in Engativa"
    assert 'B502' in nombres_eng, "Aula normal B502 not found in Engativa"
    assert 'C503' in nombres_eng, "Aula normal C503 not found in Engativa"
    assert 'A207LS' in nombres_eng, "Sala de computo A207LS not found in Engativa Bloque A"
    assert 'A207LS12' in nombres_eng, "Sala de computo A207LS12 not found in Engativa Bloque A"

    # 4. Test rendering reservas page for both sedes
    res_page_perdomo = client.get('/reservas/?sede=1')
    assert res_page_perdomo.status_code == 200
    html_perdomo = res_page_perdomo.data.decode('utf-8')
    assert 'Aula' in html_perdomo

    res_page_eng = client.get('/reservas/?sede=2')
    assert res_page_eng.status_code == 200
    html_eng = res_page_eng.data.decode('utf-8')
    assert 'Aula' in html_eng

    # 5. Test salas de computo endpoint
    res_salas = client.get('/salas-computo/')
    assert res_salas.status_code == 200

    print("\n=== ALL AULAS & SEDE ISOLATION TESTS PASSED SUCCESSFULLY! ===")

