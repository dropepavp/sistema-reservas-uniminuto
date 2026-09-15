#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Determinar la DATABASE_URL correcta o-encoding de caracteres especiales.
"""
from urllib.parse import quote

usuario = 'postgres'
password = 'Allison2.023*'
host = 'localhost'
puerto = 5432
base = 'sistema_reserva'

# URL-encode la contraseña para caracteres especiales
password_encoded = quote(password, safe='')

DATABASE_URL = f'postgresql://{usuario}:{password_encoded}@{host}:{puerto}/{base}'

print("DATABASE_URL (URL-encoded):")
print(DATABASE_URL)
print(f"\nEn PowerShell:")
print(f'$env:DATABASE_URL = "{DATABASE_URL}"')
