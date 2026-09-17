import sys
import os

# Añadir el directorio raíz al path para que los módulos del proyecto sean importables
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app import create_app

# Instancia WSGI expuesta para el runtime serverless de Vercel
app = create_app()
