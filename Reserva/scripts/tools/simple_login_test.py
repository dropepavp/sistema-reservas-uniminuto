from werkzeug.security import check_password_hash
from validators import DataValidator
from app_improved import create_app
from database import db, Auxiliar

app = create_app()

try:
    with app.app_context():
        documento = "80140666"
        contraseña = "123456"
        
        doc_valid, doc_value, doc_error = DataValidator.validate_cedula(documento)
        documento_str = str(doc_value) if doc_valid else ""
        usuario = Auxiliar.query.get(documento_str) if doc_valid else None
        
        result = "ERROR"
        if usuario:
            try:
                is_valid = check_password_hash(usuario.contraseña, contraseña)
                result = "LOGIN OK" if is_valid else "PASSWORD WRONG"
            except:
                result = "HASH ERROR"
        else:
            result = "USER NOT FOUND"
        
        with open("login_test.txt", "w") as f:
            f.write(result)
            
except Exception as e:
    with open("login_test.txt", "w") as f:
        f.write(f"EXCEPTION: {str(e)}")
