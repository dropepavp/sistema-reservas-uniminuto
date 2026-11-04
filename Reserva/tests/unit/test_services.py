"""
Tests unitarios para servicios del sistema.

Prueba la lógica de negocio en:
- services/auth_service.py
- services/prestamo_service.py
- services/estadisticas_service.py
"""
import pytest
from datetime import datetime, date, time, timedelta
from services.auth_service import registrar_auxiliar, verificar_credenciales
from services.prestamo_service import PrestamoService
from database import Auxiliar, Profesor, PrestamoEquipo, Inventario
from werkzeug.security import check_password_hash


class TestAuthService:
    """Tests para servicios de autenticación."""
    
    @pytest.mark.unit
    def test_registrar_auxiliar_exitoso(self, app_context):
        """Registra un auxiliar nuevo exitosamente."""
        # Limpiar si ya existiera de una corrida previa
        existente = Auxiliar.query.filter((Auxiliar.documento == "99999999") | (Auxiliar.correo == "test_unit@uniminuto.edu")).first()
        if existente:
            db.session.delete(existente)
            db.session.commit()

        success, message = registrar_auxiliar(
            documento="99999999",
            nombre_completo="Test Usuario",
            correo="test_unit@uniminuto.edu",
            contraseña="TestPass123"
        )
        
        assert success is True
        assert "exitosamente" in message.lower()
        
        # Verificar que se creó en BD
        user = Auxiliar.query.get("99999999")
        assert user is not None
        assert user.nombre_completo == "Test Usuario"
        assert user.correo == "test_unit@uniminuto.edu"
    
    @pytest.mark.unit
    def test_registrar_auxiliar_documento_invalido(self, app_context):
        """Rechaza documento inválido."""
        success, message = registrar_auxiliar(
            documento="",
            nombre_completo="Test",
            correo="test@uniminuto.edu",
            contraseña="TestPass123"
        )
        
        assert success is False
        assert "identificador" in message.lower() or "requerido" in message.lower()
    
    @pytest.mark.unit
    def test_registrar_auxiliar_email_invalido(self, app_context):
        """Rechaza email inválido."""
        success, message = registrar_auxiliar(
            documento="88888888",
            nombre_completo="Test",
            correo="email_invalido",
            contraseña="TestPass123"
        )
        
        assert success is False
        assert "email" in message.lower() or "formato" in message.lower()
    
    @pytest.mark.unit
    def test_registrar_auxiliar_password_debil(self, app_context):
        """Rechaza contraseña muy corta."""
        success, message = registrar_auxiliar(
            documento="77777777",
            nombre_completo="Test",
            correo="test@uniminuto.edu",
            contraseña="short"
        )
        
        assert success is False
        assert "contraseña" in message.lower() or "caracteres" in message.lower()
    
    @pytest.mark.unit
    def test_registrar_auxiliar_duplicado(self, app_context, admin_user):
        """Rechaza documento duplicado."""
        success, message = registrar_auxiliar(
            documento="80140666",  # Ya existe admin_user
            nombre_completo="Test",
            correo="otro@uniminuto.edu",
            contraseña="TestPass123"
        )
        
        assert success is False
        assert "existe" in message.lower()
    
    @pytest.mark.unit
    def test_verificar_credenciales_validas(self, app_context, admin_user):
        """Verifica credenciales correctas."""
        is_valid = verificar_credenciales("80140666", "AdminPassword123")
        assert is_valid is True
    
    @pytest.mark.unit
    def test_verificar_credenciales_invalidas_password(self, app_context, admin_user):
        """Rechaza contraseña incorrecta."""
        is_valid = verificar_credenciales("80140666", "WrongPassword")
        assert is_valid is False
    
    @pytest.mark.unit
    def test_verificar_credenciales_usuario_inexistente(self, app_context):
        """Rechaza usuario que no existe."""
        is_valid = verificar_credenciales("00000000", "SomePassword123")
        assert is_valid is False
    
    @pytest.mark.unit
    def test_verificar_credenciales_documento_invalido(self, app_context):
        """Rechaza documento inválido."""
        is_valid = verificar_credenciales("", "SomePassword123")
        assert is_valid is False


class TestPrestamoService:
    """Tests para servicios de préstamos."""
    
    @pytest.mark.unit
    def test_calcular_jornada_manana(self):
        """Calcula jornada MAÑANA correctamente."""
        jornada = PrestamoService.calcular_jornada_desde_hora("08:00")
        assert jornada == "MAÑANA"
    
    @pytest.mark.unit
    def test_calcular_jornada_tarde(self):
        """Calcula jornada TARDE correctamente."""
        jornada = PrestamoService.calcular_jornada_desde_hora("14:00")
        assert jornada == "TARDE"
    
    @pytest.mark.unit
    def test_calcular_jornada_noche(self):
        """Calcula jornada NOCHE correctamente."""
        jornada = PrestamoService.calcular_jornada_desde_hora("19:00")
        assert jornada == "NOCHE"
    
    @pytest.mark.unit
    def test_calcular_jornada_invalida(self):
        """Retorna N/A para hora inválida."""
        jornada = PrestamoService.calcular_jornada_desde_hora("25:00")
        assert jornada == "N/A"
    
    @pytest.mark.unit
    def test_calcular_jornada_vacia(self):
        """Retorna N/A para hora vacía."""
        jornada = PrestamoService.calcular_jornada_desde_hora("")
        assert jornada == "N/A"
    
    @pytest.mark.unit
    def test_calcular_horas_academicas(self):
        """Calcula diferencia de horas correctamente."""
        horas = PrestamoService.calcular_horas_academicas("08:00", "12:00")
        assert horas == 4.0
    
    @pytest.mark.unit
    def test_calcular_horas_academicas_minutos(self):
        """Calcula horas con minutos correctamente."""
        horas = PrestamoService.calcular_horas_academicas("08:30", "12:45")
        # 4 horas 15 minutos = 4.25 horas
        assert abs(horas - 4.25) < 0.01
    
    @pytest.mark.unit
    def test_calcular_horas_academicas_vacio(self):
        """Retorna 0 para horas vacías."""
        horas = PrestamoService.calcular_horas_academicas("", "12:00")
        assert horas == 0
    
    @pytest.mark.unit
    def test_extraer_numero_corto_con_prefijo(self):
        """Extrae número de inventario con prefijo."""
        from services.prestamo_service import extraer_numero_corto
        resultado = extraer_numero_corto("LAP01")
        assert resultado == "01" or resultado == "1"
    
    @pytest.mark.unit
    def test_extraer_numero_corto_vacio(self):
        """Retorna string vacío para número vacío."""
        from services.prestamo_service import extraer_numero_corto
        resultado = extraer_numero_corto("")
        assert resultado == ""
    
    @pytest.mark.unit
    def test_normalizar_identificador(self):
        """Normaliza identificador correctamente."""
        from services.prestamo_service import normalizar_identificador
        resultado = normalizar_identificador("LAP05")
        assert "05" in resultado or "5" in resultado
    
    @pytest.mark.unit
    def test_normalizar_identificador_none(self):
        """Retorna vacío para None."""
        from services.prestamo_service import normalizar_identificador
        resultado = normalizar_identificador(None)
        assert resultado == ""


class TestPrestamoServiceIntegration:
    """Tests de integración para servicio de préstamos."""
    
    @pytest.mark.unit
    def test_jornada_valida_para_hora_limites(self):
        """Verifica límites de jornadas."""
        # Inicio MAÑANA
        jornada = PrestamoService.calcular_jornada_desde_hora("06:00")
        assert jornada == "MAÑANA"
        
        # Fin MAÑANA, inicio TARDE
        jornada = PrestamoService.calcular_jornada_desde_hora("12:30")
        assert jornada in ["TARDE", "MAÑANA"]  # Depende de la implementación
    
    @pytest.mark.unit
    def test_calcular_horas_rango_completo(self):
        """Calcula horas en rango de jornada laboral."""
        horas_manana = PrestamoService.calcular_horas_academicas("06:00", "12:30")
        assert horas_manana > 0
        
        horas_tarde = PrestamoService.calcular_horas_academicas("12:30", "19:00")
        assert horas_tarde > 0
        
        horas_noche = PrestamoService.calcular_horas_academicas("19:00", "22:00")
        assert horas_noche == 3.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
