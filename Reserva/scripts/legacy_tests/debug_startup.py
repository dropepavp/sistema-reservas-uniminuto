from config import build_database_uri, config
from app_improved import create_app

db_url = build_database_uri('postgresql://postgres:Allison2023*@127.0.0.1:5432/sistema_reserva')
print('build_database_uri result:', repr(db_url))
print('Config SQLALCHEMY_DATABASE_URI:', repr(config['development'].SQLALCHEMY_DATABASE_URI))

try:
    app = create_app('development')
    print('✓ App created successfully')
except Exception as e:
    print('Error:', type(e), e)
