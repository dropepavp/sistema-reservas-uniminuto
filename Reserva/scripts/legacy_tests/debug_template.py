"""Debug del template"""
from app import app
from flask import render_template_string

with app.app_context():
    # Template simple para probar
    template = """
    <h1>Test Stats</h1>
    <p>Total: {{ stats.total or 0 }}</p>
    <p>Disponibles: {{ disponibles_count }}</p>
    <p>Por categoría: {{ stats.por_categoria }}</p>
    <p>Stock por tipo: {{ stats.stock_por_tipo }}</p>
    """
    
    # Simular datos
    stats = {
        'total': 144,
        'por_categoria': {'Equipos': 46, 'Periféricos': 48},
        'stock_por_tipo': {'Cable HDMI': {'total': 50, 'disponible': 50, 'items': []}}
    }
    
    result = render_template_string(template, stats=stats, disponibles_count=144)
    print(result)
