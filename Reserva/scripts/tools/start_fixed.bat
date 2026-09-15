@echo off
REM Fix DATABASE_URL with correct password
set DATABASE_URL=postgresql://postgres:Allison2023secure@127.0.0.1:5432/sistema_reserva
echo DATABASE_URL fixed: %DATABASE_URL%
python app.py
