import os
from sqlalchemy import create_engine, text
from urllib.parse import urlparse

# Get URL and fix it if needed
db_url = os.environ.get('DATABASE_URL') or 'postgresql://postgres:Allison2023secure@localhost:5432/sistema_reserva'

parsed = urlparse(db_url)
connect_args = {
    'host': parsed.hostname or 'localhost',
    'port': parsed.port or 5432,
    'user': parsed.username or 'postgres',
    'password': parsed.password or 'Allison2023secure',
    'database': parsed.path.lstrip('/') or 'sistema_reserva',
    'client_encoding': 'utf8',
}

engine = create_engine('postgresql+psycopg2://', connect_args=connect_args, echo=False)

with engine.connect() as conn:
    result = conn.execute(text("SELECT count(*) FROM profesores"))
    count = result.scalar()
    print(f"Count: {count}")
    
    if count > 0:
        result = conn.execute(text("SELECT cedula, nombre_completo FROM profesores LIMIT 5"))
        for row in result:
            print(f"{row[0]}: {row[1]}")
