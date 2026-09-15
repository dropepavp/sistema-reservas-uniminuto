import os
import sys
from sqlalchemy import create_engine, inspect, text

# Asegurar que el directorio del proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar configuración para obtener la URI correcta
from config import config

def ver_estructura_postgres():
    # Usar la configuración de desarrollo por defecto
    env_config = os.getenv('FLASK_CONFIG', 'development')
    uri = config[env_config].SQLALCHEMY_DATABASE_URI
    
    print("=" * 60)
    print("VISUALIZADOR DE ESTRUCTURA POSTGRESQL")
    print("=" * 60)
    
    # Ocultar contraseña para mostrar en consola
    if '@' in uri:
        uri_safe = uri.split('@')[-1]
        print(f"🔌 Conectando a: ...@{uri_safe}")
    
    try:
        engine = create_engine(uri)
        inspector = inspect(engine)
        
        tables = inspector.get_table_names()
        print(f"✅ Tablas encontradas: {len(tables)}\n")
        
        for table in tables:
            print(f"📋 TABLA: {table.upper()}")
            print("-" * 60)
            
            columns = inspector.get_columns(table)
            print(f"{'CAMPO':<30} {'TIPO':<15} {'DETALLES'}")
            print("-" * 60)
            
            for col in columns:
                attrs = []
                if col.get('primary_key'): attrs.append("PK")
                if not col.get('nullable'): attrs.append("NOT NULL")
                
                attrs_str = ", ".join(attrs)
                print(f"{col['name']:<30} {str(col['type']):<15} {attrs_str}")
            
            # Obtener conteo de registros
            with engine.connect() as conn:
                count = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                print(f"\n📊 Total registros: {count}")
            print("\n" + "="*60 + "\n")
            
    except Exception as e:
        print(f"\n❌ Error conectando a la base de datos:\n{e}")
        print("\nVerifica que PostgreSQL esté corriendo y las credenciales en config.py sean correctas.")

if __name__ == "__main__":
    ver_estructura_postgres()
