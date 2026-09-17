import sys
import os

# Configurar sys.path para asegurar importaciones locales y en Vercel
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
reserva_dir = os.path.join(parent_dir, 'Reserva')

for d in (current_dir, parent_dir, reserva_dir):
    if os.path.exists(d) and d not in sys.path:
        sys.path.insert(0, d)

from app import create_app

# Asignaciones directas en el nivel superior (top-level) requeridas por el analizador AST de @vercel/python
app = create_app()
application = app
handler = app
