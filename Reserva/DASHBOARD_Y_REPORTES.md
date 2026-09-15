# 📊 Dashboard y Reportes Avanzados

## Estado Actual

```python
# blueprints/estadisticas.py existe pero es básico
# Necesita:
# - KPIs en tiempo real
# - Gráficos interactivos
# - Exportación mejorada
# - Dashboard ejecutivo
```

---

## 1. Dashboard Ejecutivo - KPIs Principales

### Modelos de KPI

```python
# database.py - Agregar tabla de KPIs

class KPI(db.Model):
    """Indicadores de performance."""
    __tablename__ = 'kpis'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String, index=True)
    valor: Mapped[float] = mapped_column(Float)
    valor_meta: Mapped[float] = mapped_column(Float)
    unidad: Mapped[str] = mapped_column(String)  # "%", "registros", "horas"
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    
    @property
    def porcentaje_cumplimiento(self):
        """Calcula % de cumplimiento de meta."""
        if self.valor_meta == 0:
            return 0
        return (self.valor / self.valor_meta) * 100


class KPIHistorico(db.Model):
    """Histórico de KPIs para tendencias."""
    __tablename__ = 'kpis_historicos'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey('kpis.id'))
    valor: Mapped[float] = mapped_column(Float)
    fecha: Mapped[date] = mapped_column(Date, index=True)
```

### Servicio de KPIs

```python
# services/kpi_service.py

from datetime import datetime, date, timedelta
from database import db, KPI, KPIHistorico
from database import (
    PrestamoEquipo, Reserva, Inventario, Profesor, Auxiliar, AuditLog
)

class KPIService:
    """Calcula y gestiona KPIs del sistema."""
    
    @staticmethod
    def calcular_todos_kpis():
        """Calcula todos los KPIs diarios."""
        hoy = date.today()
        
        kpis_hoy = {
            'prestamos_hoy': KPIService.contar_prestamos_hoy(),
            'reservas_hoy': KPIService.contar_reservas_hoy(),
            'disponibilidad': KPIService.calcular_disponibilidad(),
            'tasa_devolucion': KPIService.calcular_tasa_devolucion(),
            'utilizacion_salas': KPIService.calcular_utilizacion_salas(),
            'usuarios_activos': KPIService.contar_usuarios_activos(),
            'promedio_horas_prestamo': KPIService.calcular_promedio_horas(),
        }
        
        # Guardar KPIs
        for nombre, valor in kpis_hoy.items():
            kpi = KPI(
                nombre=nombre,
                valor=valor['valor'],
                valor_meta=valor['meta'],
                unidad=valor['unidad'],
                fecha=datetime.now()
            )
            db.session.add(kpi)
            
            # Guardar en histórico
            historico = KPIHistorico(
                kpi_id=kpi.id,
                valor=valor['valor'],
                fecha=hoy
            )
            db.session.add(historico)
        
        db.session.commit()
    
    @staticmethod
    def contar_prestamos_hoy():
        """Préstamos iniciados hoy."""
        hoy = date.today()
        count = PrestamoEquipo.query.filter(
            PrestamoEquipo.fecha_inicio == hoy
        ).count()
        
        return {
            'valor': count,
            'meta': 50,  # Meta diaria
            'unidad': 'préstamos'
        }
    
    @staticmethod
    def contar_reservas_hoy():
        """Reservas hechas hoy."""
        hoy = date.today()
        count = Reserva.query.filter(
            Reserva.fecha == hoy
        ).count()
        
        return {
            'valor': count,
            'meta': 30,
            'unidad': 'reservas'
        }
    
    @staticmethod
    def calcular_disponibilidad():
        """% de equipos disponibles."""
        total = Inventario.query.filter_by(es_por_cantidad=False).count()
        disponibles = Inventario.query.filter_by(
            estado='Disponible',
            es_por_cantidad=False
        ).count()
        
        porcentaje = (disponibles / total * 100) if total > 0 else 0
        
        return {
            'valor': porcentaje,
            'meta': 80,  # Meta: 80% disponibilidad
            'unidad': '%'
        }
    
    @staticmethod
    def calcular_tasa_devolucion():
        """% de préstamos devueltos a tiempo."""
        semana_pasada = date.today() - timedelta(days=7)
        
        total_devueltos = PrestamoEquipo.query.filter(
            PrestamoEquipo.estado == 'Devuelto',
            PrestamoEquipo.fecha_devolucion >= semana_pasada
        ).count()
        
        devueltos_tiempo = PrestamoEquipo.query.filter(
            PrestamoEquipo.estado == 'Devuelto',
            PrestamoEquipo.fecha_devolucion >= semana_pasada,
            PrestamoEquipo.fecha_devolucion <= PrestamoEquipo.fecha_esperada
        ).count()
        
        tasa = (devueltos_tiempo / total_devueltos * 100) if total_devueltos > 0 else 100
        
        return {
            'valor': tasa,
            'meta': 95,  # Meta: 95% a tiempo
            'unidad': '%'
        }
    
    @staticmethod
    def calcular_utilizacion_salas():
        """Tasa de utilización de salas."""
        hoy = date.today()
        semana = [hoy - timedelta(days=i) for i in range(7)]
        
        total_posibles = 0
        total_utilizadas = 0
        
        for fecha in semana:
            # Salas x jornadas
            salones_count = Recurso.query.filter_by(tipo='Salón', activo=True).count()
            jornadas = 3  # MAÑANA, TARDE, NOCHE
            
            total_posibles += (salones_count * jornadas)
            
            reservadas = Reserva.query.filter(
                Reserva.fecha == fecha,
                Reserva.estado == 'activa'
            ).count()
            total_utilizadas += reservadas
        
        utilizacion = (total_utilizadas / total_posibles * 100) if total_posibles > 0 else 0
        
        return {
            'valor': utilizacion,
            'meta': 60,  # Meta: 60% utilización
            'unidad': '%'
        }
    
    @staticmethod
    def contar_usuarios_activos():
        """Usuarios con sesión activa en últimas 24h."""
        hace_24h = datetime.now() - timedelta(hours=24)
        
        usuarios_activos = AuditLog.query.filter(
            AuditLog.accion == 'LOGIN',
            AuditLog.fecha_cambio >= hace_24h
        ).distinct(AuditLog.usuario_documento).count()
        
        return {
            'valor': usuarios_activos,
            'meta': 10,
            'unidad': 'usuarios'
        }
    
    @staticmethod
    def calcular_promedio_horas():
        """Promedio de horas en préstamos esta semana."""
        semana_pasada = date.today() - timedelta(days=7)
        
        prestamos = PrestamoEquipo.query.filter(
            PrestamoEquipo.fecha_inicio >= semana_pasada,
            PrestamoEquipo.estado == 'Devuelto'
        ).all()
        
        if not prestamos:
            return {'valor': 0, 'meta': 4, 'unidad': 'horas'}
        
        total_horas = sum(p.horas_duracion for p in prestamos if p.horas_duracion)
        promedio = total_horas / len(prestamos)
        
        return {
            'valor': promedio,
            'meta': 4,
            'unidad': 'horas'
        }
```

### Template - Dashboard

```html
<!-- templates/dashboard.html -->
{% extends "base.html" %}

{% block content %}
<div class="container-fluid py-4">
    <h1 class="mb-4">📊 Dashboard Ejecutivo</h1>
    
    <!-- KPIs Row -->
    <div class="row mb-4">
        <!-- KPI 1: Préstamos -->
        <div class="col-md-3">
            <div class="card border-left-primary">
                <div class="card-body">
                    <h6 class="text-uppercase text-muted">Préstamos Hoy</h6>
                    <h2 class="font-weight-bold">{{ kpis.prestamos_hoy }}</h2>
                    <p class="text-muted">Meta: 50</p>
                    <div class="progress">
                        <div class="progress-bar bg-primary" 
                             style="width: {{ (kpis.prestamos_hoy / 50 * 100)|int }}%"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- KPI 2: Reservas -->
        <div class="col-md-3">
            <div class="card border-left-success">
                <div class="card-body">
                    <h6 class="text-uppercase text-muted">Reservas Hoy</h6>
                    <h2 class="font-weight-bold">{{ kpis.reservas_hoy }}</h2>
                    <p class="text-muted">Meta: 30</p>
                    <div class="progress">
                        <div class="progress-bar bg-success" 
                             style="width: {{ (kpis.reservas_hoy / 30 * 100)|int }}%"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- KPI 3: Disponibilidad -->
        <div class="col-md-3">
            <div class="card border-left-warning">
                <div class="card-body">
                    <h6 class="text-uppercase text-muted">Disponibilidad</h6>
                    <h2 class="font-weight-bold">{{ kpis.disponibilidad|int }}%</h2>
                    <p class="text-muted">Meta: 80%</p>
                    <div class="progress">
                        <div class="progress-bar bg-warning" 
                             style="width: {{ kpis.disponibilidad }}%"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- KPI 4: Devoluciones a Tiempo -->
        <div class="col-md-3">
            <div class="card border-left-info">
                <div class="card-body">
                    <h6 class="text-uppercase text-muted">Devoluciones a Tiempo</h6>
                    <h2 class="font-weight-bold">{{ kpis.tasa_devolucion|int }}%</h2>
                    <p class="text-muted">Meta: 95%</p>
                    <div class="progress">
                        <div class="progress-bar bg-info" 
                             style="width: {{ kpis.tasa_devolucion }}%"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Gráficos -->
    <div class="row">
        <!-- Gráfico 1: Tendencia Préstamos -->
        <div class="col-lg-6">
            <div class="card">
                <div class="card-header">
                    <h6 class="m-0">Tendencia Préstamos (Últimos 30 días)</h6>
                </div>
                <div class="card-body">
                    <canvas id="chartPrestamos"></canvas>
                </div>
            </div>
        </div>
        
        <!-- Gráfico 2: Disponibilidad por Equipo -->
        <div class="col-lg-6">
            <div class="card">
                <div class="card-header">
                    <h6 class="m-0">Disponibilidad por Tipo</h6>
                </div>
                <div class="card-body">
                    <canvas id="chartDisponibilidad"></canvas>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Chart.js -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
    // Gráfico de tendencias
    const ctx = document.getElementById('chartPrestamos').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: {{ dates|safe }},
            datasets: [{
                label: 'Préstamos',
                data: {{ prestamos_data|safe }},
                borderColor: '#4e73df',
                backgroundColor: 'rgba(78, 115, 223, 0.05)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
</script>
{% endblock %}
```

---

## 2. Reportes Avanzados

### Generador de Reportes

```python
# services/report_service.py

from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import date
import io

class ReportService:
    """Generador de reportes PDF/Excel."""
    
    @staticmethod
    def generar_reporte_prestamos_mensual(mes, año):
        """Genera reporte PDF de préstamos mensuales."""
        from database import PrestamoEquipo
        
        # Obtener datos
        prestamos = PrestamoEquipo.query.filter(
            extract('month', PrestamoEquipo.fecha_inicio) == mes,
            extract('year', PrestamoEquipo.fecha_inicio) == año
        ).all()
        
        # Crear PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            title=f"Reporte Préstamos {mes}/{año}"
        )
        
        story = []
        
        # Título
        styles = getSampleStyleSheet()
        title = Paragraph(
            f"<b>Reporte de Préstamos - {mes}/{año}</b>",
            styles['Heading1']
        )
        story.append(title)
        story.append(Spacer(1, 0.5*inch))
        
        # Tabla de datos
        data = [['Profesor', 'Equipo', 'Fecha', 'Estado', 'Horas']]
        for p in prestamos:
            data.append([
                p.nombre_profesor,
                p.inventario.item,
                p.fecha_inicio.strftime('%d/%m/%Y'),
                p.estado,
                f"{p.horas_duracion:.1f}h"
            ])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        
        # Resumen
        story.append(Spacer(1, 0.3*inch))
        total_prestamos = len(prestamos)
        total_horas = sum(p.horas_duracion for p in prestamos if p.horas_duracion)
        
        resumen = Paragraph(
            f"<b>Resumen:</b><br/>"
            f"Total de Préstamos: {total_prestamos}<br/>"
            f"Total de Horas: {total_horas:.1f}<br/>",
            styles['Normal']
        )
        story.append(resumen)
        
        # Generar PDF
        doc.build(story)
        buffer.seek(0)
        
        return buffer
    
    @staticmethod
    def generar_reporte_disponibilidad():
        """Genera reporte de disponibilidad actual."""
        from database import Inventario
        
        inventario = Inventario.query.all()
        
        datos = []
        for item in inventario:
            datos.append({
                'item': item.item,
                'categoria': item.categoria,
                'estado': item.estado,
                'bodega': item.bodega.nombre if item.bodega else 'N/A'
            })
        
        return {
            'fecha': date.today().strftime('%d/%m/%Y'),
            'total_items': len(datos),
            'disponibles': len([d for d in datos if d['estado'] == 'Disponible']),
            'en_prestamo': len([d for d in datos if d['estado'] == 'En Préstamo']),
            'datos': datos
        }
```

### Endpoint de Reportes

```python
# blueprints/reportes.py

@app.route('/reportes/prestamos/<int:mes>/<int:año>')
@login_required
@admin_required
def reporte_prestamos(mes, año):
    """Descarga reporte PDF de préstamos."""
    from services.report_service import ReportService
    
    try:
        pdf_buffer = ReportService.generar_reporte_prestamos_mensual(mes, año)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'prestamos_{mes}_{año}.pdf'
        )
    except Exception as e:
        current_app.logger.error(f"Error generando reporte: {e}")
        flash('Error al generar reporte', 'danger')
        return redirect('/reportes')
```

---

## 3. Exportación Mejorada

```python
# Mejorar export_helpers.py

def exportar_con_formato_avanzado(df, formato, titulo, incluir_resumen=True):
    """Exporta con resumen y formato mejorado."""
    
    if formato == 'excel':
        buffer = io.BytesIO()
        
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Hoja 1: Datos
            df.to_excel(writer, sheet_name='Datos', index=False)
            
            # Hoja 2: Resumen
            if incluir_resumen:
                resumen = pd.DataFrame({
                    'Métrica': ['Total', 'Promedio', 'Máximo'],
                    'Valor': [len(df), df.select_dtypes(float).mean().mean(), 
                             df.select_dtypes(float).max().max()]
                })
                resumen.to_excel(writer, sheet_name='Resumen', index=False)
            
            # Formato
            workbook = writer.book
            worksheet = writer.sheets['Datos']
            
            # Headers con color
            from openpyxl.styles import PatternFill, Font
            header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
            header_font = Font(color='FFFFFF', bold=True)
            
            for cell in worksheet[1]:
                cell.fill = header_fill
                cell.font = header_font
        
        buffer.seek(0)
        return buffer
```

---

## ✅ Checklist de Implementación

```
KPIs:
- [ ] Crear tabla KPI y KPIHistorico
- [ ] Implementar KPIService
- [ ] Crear dashboard.html
- [ ] Agregar endpoint en blueprints

Reportes:
- [ ] Instalar reportlab
- [ ] Crear ReportService
- [ ] Endpoints de descarga
- [ ] Plantillas de reportes

Exportación:
- [ ] Mejorar export_helpers.py
- [ ] Agregar resumen en exports
- [ ] Formateo de Excel
- [ ] Tests de exportación
```

---

**Guía de Dashboard y Reportes**  
ROI: Alto | Implementación: 8-10 horas | Impacto: Visibilidad del negocio
