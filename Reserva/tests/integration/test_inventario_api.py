"""
Pruebas de integración para los endpoints de inventario.
"""
import pytest


@pytest.mark.integration
def test_inventario_page_redirect_without_login(client):
    response = client.get('/inventario/')
    assert response.status_code in (302, 401)


@pytest.mark.integration
def test_inventario_page_with_login(client, sample_data):
    with client.session_transaction() as sess:
        sess['usuario'] = sample_data['auxiliar'].documento
        sess['nombre_completo'] = sample_data['auxiliar'].nombre_completo
        sess['rol'] = 'admin'
        sess['sede_id'] = sample_data['sede'].id
        sess['sede_nombre'] = sample_data['sede'].nombre

    response = client.get('/inventario/')
    assert response.status_code == 200
    assert b"Inventario" in response.data or b"inventario" in response.data.lower()
    assert b"Foto del Elemento" in response.data or b"foto" in response.data.lower()


@pytest.mark.integration
def test_agregar_item_con_ficha_tecnica_y_sede_automatica(client, sample_data):
    """Verifica que al agregar un equipo no se pide la sede y se asigna la sede de la sesión activa."""
    from database import Inventario, CategoriaInventario, db

    with client.session_transaction() as sess:
        sess['usuario'] = sample_data['auxiliar'].documento
        sess['nombre_completo'] = sample_data['auxiliar'].nombre_completo
        sess['rol'] = 'admin'
        sess['sede_id'] = sample_data['sede'].id
        sess['sede_nombre'] = sample_data['sede'].nombre

    # Asegurar categoría válida
    cat = CategoriaInventario.query.filter_by(nombre="Equipos de Cómputo").first()
    if not cat:
        cat = CategoriaInventario(nombre="Equipos de Cómputo")
        db.session.add(cat)
        db.session.commit()

    payload = {
        'categoria': 'Equipos de Cómputo',
        'item': 'Laptop HP ProBook 440 G9',
        'marca_modelo': 'HP ProBook',
        'serial': '5CD2345678',
        'numero_inventario': 'LAP-PRUEBA-01',
        'activo_fijo': 'AF-98765',
        # No enviamos sede_id: debe tomarse de la sesión
        'procesador': 'Intel Core i7-1255U',
        'ram_gb': '16 GB',
        'almacenamiento': '512 GB SSD',
        'sistema_operativo': 'Windows 11 Pro',
        'especificaciones_tecnicas': 'Pantalla 14 pulgadas FHD, WiFi 6',
        'proveedor': 'Proveedor TI Colombia'
    }

    response = client.post('/inventario/agregar', json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    item_id = data['id']

    # Verificar en la base de datos
    item_creado = Inventario.query.get(item_id)
    assert item_creado is not None
    assert item_creado.procesador == 'Intel Core i7-1255U'
    assert item_creado.ram_gb == '16 GB'
    assert item_creado.almacenamiento == '512 GB SSD'
    assert item_creado.sistema_operativo == 'Windows 11 Pro'
    assert item_creado.proveedor == 'Proveedor TI Colombia'
    # Sede debe ser la de la sesión
    assert item_creado.bodega is not None
    assert item_creado.bodega.sede_id == sample_data['sede'].id


@pytest.mark.integration
def test_editar_item_hoja_vida_get_y_post(client, sample_data):
    """Verifica que el endpoint de edición retorne y actualice la ficha técnica."""
    from database import Inventario, CategoriaInventario, db
    import io

    with client.session_transaction() as sess:
        sess['usuario'] = sample_data['auxiliar'].documento
        sess['nombre_completo'] = sample_data['auxiliar'].nombre_completo
        sess['rol'] = 'admin'
        sess['sede_id'] = sample_data['sede'].id

    cat = CategoriaInventario.query.filter_by(nombre="Audiovisuales").first()
    if not cat:
        cat = CategoriaInventario(nombre="Audiovisuales")
        db.session.add(cat)
        db.session.commit()

    nuevo = Inventario(
        categoria='Audiovisuales',
        item='Videoproyector Epson',
        marca_modelo='Epson PowerLite',
        numero_inventario='PROY-01',
        bodega_id=sample_data['bodega'].id,
        procesador='N/A',
        especificaciones_tecnicas='3600 lúmenes HDMI'
    )
    db.session.add(nuevo)
    db.session.commit()

    # Probar GET
    res_get = client.get(f'/inventario/editar/{nuevo.id}')
    assert res_get.status_code == 200
    item_json = res_get.get_json()['item']
    assert item_json['item'] == 'Videoproyector Epson'
    assert item_json['especificaciones_tecnicas'] == '3600 lúmenes HDMI'

    # Probar actualización con POST
    edit_payload = {
        'categoria': 'Audiovisuales',
        'item': 'Videoproyector Epson 4K',
        'marca_modelo': 'Epson PowerLite Pro',
        'numero_inventario': 'PROY-01',
        'especificaciones_tecnicas': '4000 lúmenes 4K HDR',
        'procesador': 'Chip 3LCD',
        'ram_gb': 'N/A',
        'almacenamiento': 'N/A',
        'sistema_operativo': 'Embedded OS'
    }

    res_post = client.post(f'/inventario/editar/{nuevo.id}', data=edit_payload)
    assert res_post.status_code == 200
    assert res_post.get_json()['success'] is True

    # Verificar actualización
    db.session.refresh(nuevo)
    assert nuevo.item == 'Videoproyector Epson 4K'
    assert nuevo.especificaciones_tecnicas == '4000 lúmenes 4K HDR'
    assert nuevo.procesador == 'Chip 3LCD'


@pytest.mark.integration
def test_subir_y_eliminar_foto_item(client, sample_data):
    """Verifica la carga de foto única y posterior eliminación."""
    from database import Inventario, db
    import io

    with client.session_transaction() as sess:
        sess['usuario'] = sample_data['auxiliar'].documento
        sess['nombre_completo'] = sample_data['auxiliar'].nombre_completo
        sess['rol'] = 'admin'
        sess['sede_id'] = sample_data['sede'].id

    item_foto = Inventario(
        categoria='Audiovisuales',
        item='Cámara Web Logitech',
        numero_inventario='CAM-LOGI-01',
        bodega_id=sample_data['bodega'].id,
        estado='Disponible'
    )
    db.session.add(item_foto)
    db.session.commit()

    # Subir imagen simulada (PNG mínimo de 1x1 pixel)
    # Minimal 1x1 transparent PNG bytes
    png_bytes = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02'
        b'\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    file_data = {
        'foto': (io.BytesIO(png_bytes), 'webcam.png', 'image/png'),
        'categoria': 'Audiovisuales',
        'item': 'Cámara Web Logitech C920',
        'numero_inventario': 'CAM-LOGI-01'
    }

    res_upload = client.post(
        f'/inventario/editar/{item_foto.id}',
        data=file_data,
        content_type='multipart/form-data'
    )
    assert res_upload.status_code == 200
    db.session.refresh(item_foto)
    assert item_foto.foto_url is not None
    assert 'equipos' in item_foto.foto_url

    # Probar eliminar foto
    del_data = {
        'categoria': 'Audiovisuales',
        'item': 'Cámara Web Logitech C920',
        'numero_inventario': 'CAM-LOGI-01',
        'eliminar_foto': 'true'
    }
    res_del = client.post(f'/inventario/editar/{item_foto.id}', data=del_data)
    assert res_del.status_code == 200
    db.session.refresh(item_foto)
    assert item_foto.foto_url is None

