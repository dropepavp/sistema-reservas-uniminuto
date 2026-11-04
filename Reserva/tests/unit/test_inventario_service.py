"""
Pruebas unitarias para InventarioService.
"""
import pytest
from services.inventario_service import InventarioService
from database import Inventario


@pytest.mark.unit
def test_calcular_estadisticas_inventario_vacio():
    stats = InventarioService.calcular_estadisticas_inventario([])
    assert stats['total_items'] == 0
    assert stats['disponibles_count'] == 0
    assert stats['prestados_count'] == 0
    assert stats['categorias_count'] == {}


@pytest.mark.unit
def test_calcular_estadisticas_inventario_con_items(app, sample_data):
    with app.app_context():
        item = sample_data['item']
        stats = InventarioService.calcular_estadisticas_inventario([item])

        assert stats['total_items'] == 1
        assert stats['disponibles_count'] == 1
        assert stats['prestados_count'] == 0
        assert stats['categorias_count']['Equipos Portátiles'] == 1
