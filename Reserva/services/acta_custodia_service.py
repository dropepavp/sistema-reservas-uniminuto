"""
Servicio para la generación del Acta Oficial de Custodia y Asignación de Activos en PDF
utilizando ReportLab con estética institucional UNIMINUTO.
"""
import io
from datetime import datetime
from typing import List, Optional
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas
from database import InventarioCustodia


class NumberedCanvas(canvas.Canvas):
    """Canvas que numera las páginas automáticamente en formato 'Página X de Y'."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        footer_text = "UNIMINUTO — Corporación Universitaria Minuto de Dios | Control de Activos Fijos y Custodias"
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawString(36, 20, footer_text)
        self.drawRightString(self._pagesize[0] - 36, 20, page_text)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(36, 30, self._pagesize[0] - 36, 30)
        self.restoreState()


class ActaCustodiaService:
    """Generador institucional de Actas de Asignación y Custodia de Bienes en PDF."""

    @staticmethod
    def _obtener_categoria_item(c: InventarioCustodia) -> str:
        """Determina la categoría institucional para organizar los bienes en el acta."""
        if c.inventario_item and c.inventario_item.categoria:
            return c.inventario_item.categoria.strip()
        
        desc = (c.descripcion or '').upper()
        if any(k in desc for k in ['PORTATIL', 'LAPTOP', 'COMPUTADOR', 'TODO EN UNO', 'AIO', 'PC', 'TORRE', 'CPU']):
            return 'Equipos de Cómputo'
        if any(k in desc for k in ['CONSOLA', 'SONIDO', 'AUDIO', 'MICROFONO', 'PARLANTE', 'CABINA', 'AMPLIFICADOR', 'MEZCLADOR']):
            return 'Equipos de Audio y Sonido'
        if any(k in desc for k in ['GUITARRA', 'BAJO', 'BATERIA', 'TECLADO', 'PIANO', 'SAXOFON', 'VIOLIN', 'INSTRUMENTO']):
            return 'Instrumentos Musicales'
        if any(k in desc for k in ['PROYECTOR', 'VIDEO BEAM', 'PANTALLA', 'TELEVISOR', 'TV', 'MONITOR', 'SMART']):
            return 'Pantallas y Proyección'
        if any(k in desc for k in ['CABLE', 'HDMI', 'VGA', 'ADAPTADOR', 'CONTROL', 'MOUSE', 'TECLADO']):
            return 'Periféricos y Accesorios'
        if any(k in desc for k in ['CAMARA', 'TRIPODE', 'LENTE', 'LUCES', 'ILUMINACION', 'REFLECTOR']):
            return 'Fotografía y Video'
        if c.programa_area and c.programa_area.strip():
            return f"Área: {c.programa_area.strip()}"
        return c.tipo_inventario or "Otros / General"

    @staticmethod
    def generar_acta_pdf(
        custodias: List[InventarioCustodia],
        consecutivo: Optional[str] = None,
        usuario_emisor: Optional[str] = None,
        sede_nombre: str = "PERDOMO",
        organizar_por_categoria: bool = True
    ) -> io.BytesIO:
        buffer = io.BytesIO()

        # Documento apaisado (Landscape Letter) para dar espacio a la tabla de activos
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=40
        )

        styles = getSampleStyleSheet()

        # Paleta institucional UNIMINUTO
        COLOR_PRIMARY = colors.HexColor("#1e3a5f")   # Azul institucional oscuro
        COLOR_SECONDARY = colors.HexColor("#2d6a9f") # Azul intermedio
        COLOR_BG_LIGHT = colors.HexColor("#f8fafc")  # Gris/azul muy suave
        COLOR_BORDER = colors.HexColor("#cbd5e1")    # Borde sutil
        COLOR_MUTED = colors.HexColor("#475569")
        COLOR_CAT_BG = colors.HexColor("#e0e7ff")   # Fondo tenue azul índigo para categorías

        # Estilos de párrafos tipográficos
        style_header_title = ParagraphStyle(
            'HeaderTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=COLOR_PRIMARY
        )
        style_header_sub = ParagraphStyle(
            'HeaderSub',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=11,
            textColor=COLOR_MUTED
        )
        style_acta_ref = ParagraphStyle(
            'ActaRef',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            alignment=2,
            textColor=COLOR_PRIMARY
        )
        style_acta_meta = ParagraphStyle(
            'ActaMeta',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            alignment=2,
            textColor=COLOR_MUTED
        )
        style_meta_label = ParagraphStyle(
            'MetaLabel',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=COLOR_PRIMARY
        )
        style_meta_val = ParagraphStyle(
            'MetaVal',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0f172a")
        )
        style_th = ParagraphStyle(
            'TableHead',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9,
            alignment=1,
            textColor=colors.white
        )
        style_td = ParagraphStyle(
            'TableData',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#1e293b")
        )
        style_td_center = ParagraphStyle(
            'TableDataCenter',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9,
            alignment=1,
            textColor=colors.HexColor("#1e293b")
        )
        style_td_bold = ParagraphStyle(
            'TableDataBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#0f172a")
        )
        style_cat_banner = ParagraphStyle(
            'CategoryBanner',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=COLOR_PRIMARY
        )
        style_legal = ParagraphStyle(
            'LegalText',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=7.5,
            leading=10,
            alignment=4,  # Justificado
            textColor=colors.HexColor("#334155")
        )
        style_firmas_title = ParagraphStyle(
            'FirmasTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            alignment=1,
            textColor=COLOR_PRIMARY
        )
        style_firmas_sub = ParagraphStyle(
            'FirmasSub',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9,
            alignment=1,
            textColor=COLOR_MUTED
        )

        elements = []
        ahora = datetime.now()
        consecutivo_real = consecutivo or f"ACTA-{sede_nombre[:4].upper()}-{ahora.strftime('%Y%m%d%H%M')}"

        # -------------------------------------------------------------
        # 1. ENCABEZADO INSTITUCIONAL
        # -------------------------------------------------------------
        header_data = [
            [
                Paragraph("<b>CORPORACIÓN UNIVERSITARIA MINUTO DE DIOS - UNIMINUTO</b><br/>"
                          f"<font size='8' color='#64748b'>Vicerrectoría Regional Bogotá Sur • Sede {sede_nombre.upper()}<br/>"
                          "Dirección Administrativa y Financiera • Gestión de Activos y Laboratorios</font>", style_header_title),
                Paragraph("<b>ACTA DE ASIGNACIÓN Y CUSTODIA DE BIENES</b><br/>"
                          f"<b>N° Consecutivo:</b> {consecutivo_real}<br/>"
                          f"<b>Fecha de Emisión:</b> {ahora.strftime('%d/%m/%Y %H:%M')}<br/>"
                          f"<b>Generado por:</b> {usuario_emisor or 'Sistema de Gestión'}", style_acta_ref)
            ]
        ]
        t_header = Table(header_data, colWidths=[450, 270])
        t_header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(t_header)
        elements.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_PRIMARY, spaceAfter=8, spaceBefore=4))

        # -------------------------------------------------------------
        # 2. METADATA RESUMEN DE CUSTODIA Y CENTRO DE COSTO
        # -------------------------------------------------------------
        primero = custodias[0] if custodias else None
        responsables_set = set(c.responsable_custodia for c in custodias if c.responsable_custodia)
        cedulas_set = set(c.cedula_custodio for c in custodias if c.cedula_custodio)
        cargos_set = set(c.cargo_custodio for c in custodias if c.cargo_custodio)
        centros_set = set(c.centro_costo for c in custodias if c.centro_costo)
        nombres_cc_set = set(c.nombre_centro_costo for c in custodias if c.nombre_centro_costo)
        edificios_set = set(c.edificio for c in custodias if c.edificio)
        programas_set = set(c.programa_area for c in custodias if c.programa_area)

        txt_responsable = ", ".join(responsables_set) if len(responsables_set) <= 2 else f"{len(responsables_set)} Custodios Asignados"
        txt_cedula = ", ".join(cedulas_set) if len(cedulas_set) <= 2 else "Varios Documentos"
        txt_cargo = ", ".join(cargos_set) if len(cargos_set) <= 2 else "Varios Cargos"
        txt_cc = ", ".join(centros_set) if len(centros_set) <= 2 else f"{len(centros_set)} C.C. Asociados"
        txt_nombre_cc = ", ".join(nombres_cc_set) if len(nombres_cc_set) <= 2 else "Varios Centros de Costo"
        txt_edificio = ", ".join(edificios_set) if len(edificios_set) <= 2 else f"{len(edificios_set)} Edificios"
        txt_programa = ", ".join(programas_set) if len(programas_set) <= 2 else "Múltiples Programas/Áreas"

        info_box = [
            [
                Paragraph("<b>RESPONSABLE (CUSTODIO):</b>", style_meta_label),
                Paragraph(txt_responsable or "Sin custodio individual", style_meta_val),
                Paragraph("<b>CENTRO DE COSTO:</b>", style_meta_label),
                Paragraph(f"<b>{txt_cc}</b> - {txt_nombre_cc}", style_meta_val),
            ],
            [
                Paragraph("<b>CÉDULA / DOCUMENTO:</b>", style_meta_label),
                Paragraph(txt_cedula or "N/A", style_meta_val),
                Paragraph("<b>EDIFICIO / SEDE:</b>", style_meta_label),
                Paragraph(txt_edificio or sede_nombre, style_meta_val),
            ],
            [
                Paragraph("<b>CARGO DEL RESPONSABLE:</b>", style_meta_label),
                Paragraph(txt_cargo or "N/A", style_meta_val),
                Paragraph("<b>PROGRAMA / ÁREA:</b>", style_meta_label),
                Paragraph(txt_programa or "N/A", style_meta_val),
            ]
        ]
        t_info = Table(info_box, colWidths=[140, 220, 140, 220])
        t_info.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
            ('BOX', (0, 0), (-1, -1), 0.75, COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(t_info)
        elements.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # 3. TABLA DE ACTIVOS EN CUSTODIA (Agrupación por Categoría)
        # -------------------------------------------------------------
        table_rows = [
            [
                Paragraph("N°", style_th),
                Paragraph("PLACA / INV.", style_th),
                Paragraph("SERIE", style_th),
                Paragraph("DESCRIPCIÓN DEL ACTIVO", style_th),
                Paragraph("MARCA", style_th),
                Paragraph("CANT.", style_th),
                Paragraph("ESTADO", style_th),
                Paragraph("UBICACIÓN", style_th),
                Paragraph("OBSERVACIONES", style_th),
            ]
        ]

        # Agrupar por categoría
        grupos_categoria = {}
        if organizar_por_categoria:
            for c in custodias:
                cat = ActaCustodiaService._obtener_categoria_item(c)
                grupos_categoria.setdefault(cat, []).append(c)
        else:
            grupos_categoria = {"General": custodias}

        total_unidades = 0
        correlativo = 1
        banner_indices = []
        data_row_indices = []

        for cat_nombre, items_cat in grupos_categoria.items():
            # Si se organiza por categoría y hay ítems, insertar fila destacada de categoría
            if organizar_por_categoria:
                current_banner_idx = len(table_rows)
                banner_indices.append(current_banner_idx)
                banner_text = f"<b>CATEGORÍA: {cat_nombre.upper()} &nbsp;&nbsp;({len(items_cat)} {'activo' if len(items_cat) == 1 else 'activos'})</b>"
                table_rows.append([
                    Paragraph(banner_text, style_cat_banner),
                    Paragraph("", style_th),
                    Paragraph("", style_th),
                    Paragraph("", style_th),
                    Paragraph("", style_th),
                    Paragraph("", style_th),
                    Paragraph("", style_th),
                    Paragraph("", style_th),
                    Paragraph("", style_th),
                ])

            for c in items_cat:
                data_row_indices.append(len(table_rows))
                total_unidades += (c.cantidad or 1)
                obs_clean = (c.observaciones or '').strip()
                if len(obs_clean) > 80:
                    obs_clean = obs_clean[:77] + '...'

                table_rows.append([
                    Paragraph(str(correlativo), style_td_center),
                    Paragraph(f"<b>{c.placa or 'S/P'}</b>", style_td_bold),
                    Paragraph(c.serie or 'N/A', style_td),
                    Paragraph(c.descripcion, style_td_bold),
                    Paragraph(c.marca or 'N/A', style_td),
                    Paragraph(str(c.cantidad or 1), style_td_center),
                    Paragraph(c.estado or 'Configurado', style_td_center),
                    Paragraph(c.ubicacion or 'N/A', style_td),
                    Paragraph(obs_clean or '--', style_td),
                ])
                correlativo += 1

        col_widths = [25, 80, 75, 165, 65, 35, 70, 95, 110]
        t_activos = Table(table_rows, colWidths=col_widths, repeatRows=1)
        
        table_style_commands = [
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ]

        # Estilo para las filas de categoría (SPAN y fondo destacado)
        for b_idx in banner_indices:
            table_style_commands.extend([
                ('SPAN', (0, b_idx), (-1, b_idx)),
                ('BACKGROUND', (0, b_idx), (-1, b_idx), COLOR_CAT_BG),
                ('TOPPADDING', (0, b_idx), (-1, b_idx), 4),
                ('BOTTOMPADDING', (0, b_idx), (-1, b_idx), 4),
                ('LEFTPADDING', (0, b_idx), (-1, b_idx), 6),
            ])

        # Estilo zebra para filas de datos
        for idx, row_i in enumerate(data_row_indices):
            bg = colors.white if idx % 2 == 0 else COLOR_BG_LIGHT
            table_style_commands.append(('BACKGROUND', (0, row_i), (-1, row_i), bg))

        t_activos.setStyle(TableStyle(table_style_commands))
        elements.append(t_activos)
        elements.append(Spacer(1, 8))

        # Resumen cuantitativo y desglose por categorías
        desglose_partes = [f"<b>{k}:</b> {len(v)}" for k, v in grupos_categoria.items()]
        desglose_str = " &nbsp;|&nbsp; ".join(desglose_partes)
        resumen_p = Paragraph(
            f"<b>Total de bienes / renglones asignados:</b> {len(custodias)} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Total de unidades físicas:</b> {total_unidades} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Sede:</b> {sede_nombre.upper()}<br/>"
            f"<font size='7' color='#475569'><b>Desglose por Categoría:</b> {desglose_str}</font>",
            style_meta_val
        )
        elements.append(resumen_p)
        elements.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 4. CLÁUSULA DE RESPONSABILIDAD Y COMPROMISO
        # -------------------------------------------------------------
        clausula_texto = (
            "<b>COMPROMISO DE CUSTODIA Y RESPONSABILIDAD:</b> "
            "El(la) custodio(a) declara haber recibido a entera satisfacción los bienes descritos en la presente acta, "
            "en las condiciones físicas y operativas relacionadas. Se compromete a destinarlos exclusivamente para los fines "
            "misionales de la institución, velar por su adecuado mantenimiento, custodia y preservación. Cualquier traslado, "
            "daño, pérdida o desconfiguración deberá ser notificada de inmediato a la Coordinación de Laboratorios e Inventarios "
            "de UNIMINUTO, dando cumplimiento al Reglamento Interno y a la Política Institucional de Gestión de Activos Fijos."
        )
        t_legal = Table([[Paragraph(clausula_texto, style_legal)]], colWidths=[720])
        t_legal.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t_legal)
        elements.append(Spacer(1, 14))

        # -------------------------------------------------------------
        # 5. BLOQUE DE FIRMAS (CUSTODIO, INVENTARIOS, COORDINACIÓN)
        # -------------------------------------------------------------
        firmas_data = [
            [
                Paragraph("____________________________________________<br/>"
                          f"<b>FIRMA CUSTODIO / RESPONSABLE</b><br/>"
                          f"{txt_responsable}<br/>"
                          f"C.C. {txt_cedula}<br/>"
                          f"<font size='7'>{txt_cargo}</font>", style_firmas_sub),
                Paragraph("____________________________________________<br/>"
                          "<b>FUNCIONARIO DE INVENTARIOS</b><br/>"
                          f"{usuario_emisor or 'Gestión de Inventario'}<br/>"
                          "Revisado y Verificado en Sede<br/>"
                          "<font size='7'>Área de Activos Fijos</font>", style_firmas_sub),
                Paragraph("____________________________________________<br/>"
                          "<b>COORDINACIÓN / V°B° ADMINISTRATIVO</b><br/>"
                          f"Dirección de Sede {sede_nombre.upper()}<br/>"
                          "UNIMINUTO Bogotá Sur<br/>"
                          "<font size='7'>Aprobación Oficial</font>", style_firmas_sub)
            ]
        ]
        t_firmas = Table(firmas_data, colWidths=[240, 240, 240])
        t_firmas.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(KeepTogether([t_firmas]))

        # Construir el documento con NumberedCanvas
        doc.build(elements, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer
