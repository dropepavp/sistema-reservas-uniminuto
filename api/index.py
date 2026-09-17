import sys
import os

# Asegurar que el subdirectorio Reserva esté en sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
reserva_dir = os.path.join(root_dir, 'Reserva')
if reserva_dir not in sys.path:
    sys.path.insert(0, reserva_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import create_app

app = create_app()
handler = app
