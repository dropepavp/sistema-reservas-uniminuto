import sys
import os
import traceback

# Configurar sys.path para asegurar importaciones locales y en Vercel
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
reserva_dir = os.path.join(parent_dir, 'Reserva')

for d in (current_dir, parent_dir, reserva_dir):
    if os.path.exists(d) and d not in sys.path:
        sys.path.insert(0, d)

try:
    from app import create_app
    app = create_app()
    handler = app
except Exception as e:
    err_tb = traceback.format_exc()
    print("FATAL ERROR ON STARTUP:\n", err_tb, file=sys.stderr)
    
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def fallback_error(path):
        return f"""
        <html>
        <head><title>Error de Inicialización - UNIMINUTO Reservas</title></head>
        <body style="font-family: sans-serif; padding: 2rem; background: #0f172a; color: #f8fafc;">
            <h2 style="color: #ef4444;">Error al inicializar la aplicación en Vercel</h2>
            <p>Se produjo una excepción durante el arranque:</p>
            <pre style="background: #1e293b; padding: 1rem; border-radius: 8px; overflow-x: auto; color: #fca5a5;">{err_tb}</pre>
        </body>
        </html>
        """, 500
        
    handler = app
