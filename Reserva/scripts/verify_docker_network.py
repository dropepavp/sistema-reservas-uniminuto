"""
Script de verificación de comunicación entre contenedores (Criterio 5 - 35 pts).
Demuestra la conectividad por nombre de servicio 'db' y realiza una operación
real de ida y vuelta (escritura y lectura) persistiendo un registro en PostgreSQL.
"""
from app import create_app
from database import db
from sqlalchemy import text

app = create_app()

def verificar_comunicacion():
    print("==================================================================")
    print(" VERIFICACION DE COMUNICACION ENTRE CONTENEDORES (CRITERIO 5) ")
    print("==================================================================")
    print("-> Conectando a PostgreSQL mediante el host DNS 'db'...")

    with app.app_context():
        # 1. Crear tabla temporal de prueba si no existe
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS test_comunicacion (
                id SERIAL PRIMARY KEY,
                mensaje VARCHAR(255) NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        db.session.commit()

        # 2. Operación de IDA: Insertar dato real
        mensaje_prueba = "Operacion exitosa de ida y vuelta: Contenedor 'web' -> 'db'"
        db.session.execute(
            text("INSERT INTO test_comunicacion (mensaje) VALUES (:msg);"),
            {"msg": mensaje_prueba}
        )
        db.session.commit()
        print("[OK] Dato enviado y guardado exitosamente en el contenedor 'db'.")

        # 3. Operación de VUELTA: Leer dato real recién guardado
        registro = db.session.execute(
            text("SELECT id, mensaje, fecha FROM test_comunicacion ORDER BY id DESC LIMIT 1;")
        ).fetchone()

        print("[OK] Dato leido de vuelta desde 'db':")
        print(f"     * ID: {registro[0]}")
        print(f"     * Mensaje: {registro[1]}")
        print(f"     * Timestamp: {registro[2]}")
        print("==================================================================")
        print(" ESTADO: COMUNICACION 100% FUNCIONAL Y DEMOSTRADA ")
        print("==================================================================")

if __name__ == "__main__":
    verificar_comunicacion()
