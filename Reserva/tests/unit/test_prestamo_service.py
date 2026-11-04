"""
Pruebas unitarias para PrestamoService y utilidades de préstamos.
"""
import pytest
from services.prestamo_service import PrestamoService, extraer_numero_corto, normalizar_identificador


@pytest.mark.unit
def test_extraer_numero_corto():
    assert extraer_numero_corto("LAP01") == "01"
    assert extraer_numero_corto("ADA05") == "05"
    assert extraer_numero_corto("123") == "123"


@pytest.mark.unit
def test_normalizar_identificador():
    assert normalizar_identificador("LAP01") == "01"
    assert normalizar_identificador("HDMI02") == "02"


@pytest.mark.unit
def test_calcular_jornada_manana():
    jornada = PrestamoService.calcular_jornada_desde_hora("08:30")
    assert jornada == "MAÑANA"


@pytest.mark.unit
def test_calcular_jornada_tarde():
    jornada = PrestamoService.calcular_jornada_desde_hora("15:00")
    assert jornada == "TARDE"


@pytest.mark.unit
def test_calcular_jornada_noche():
    jornada = PrestamoService.calcular_jornada_desde_hora("19:30")
    assert jornada == "NOCHE"
