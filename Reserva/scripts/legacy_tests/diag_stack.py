import sys
import os
import traceback
from flask import Flask

# Tentativa de bypass absoluto
os.environ['DATABASE_URL'] = '' # Clear it early

try:
    from database import db
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:' # SUPER SAFE
    
    print("Iniciando db.init_app(app)...")
    db.init_app(app)
    print("¡Éxito!")
    
except UnicodeDecodeError as e:
    print(f"CAPTURED UnicodeDecodeError: {e}")
    # Inspeccionar el stack
    tb = traceback.extract_tb(sys.exc_info()[2])
    for frame in tb:
        print(f"File {frame.filename}, line {frame.lineno}, in {frame.name}")
        # Intentar ver si el archivo tiene algo raro
except Exception as e:
    print(f"Other error: {e}")
    traceback.print_exc()
