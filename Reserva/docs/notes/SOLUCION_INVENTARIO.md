# Solución al Problema de Inventario Vacío

## Problema
Las estadísticas muestran 0 y no aparecen items en la tabla.

## Causa Probable
La URL tiene parámetros de filtro que están bloqueando los resultados, especialmente el parámetro `?sede=X` donde la sede no tiene bodegas asignadas.

## Solución Inmediata

### Opción 1: Acceder sin filtros
Usa esta URL exacta (sin parámetros):
```
http://127.0.0.1:5000/inventario/
```

### Opción 2: Limpiar caché del navegador
1. Presiona Ctrl+Shift+Delete
2. Selecciona "Caché" o "Archivos temporales"
3. Limpia el caché
4. Recarga la página con Ctrl+F5

### Opción 3: Usar modo incógnito
1. Abre una ventana de incógnito (Ctrl+Shift+N en Chrome)
2. Ve a http://127.0.0.1:5000
3. Inicia sesión
4. Ve a inventario

## Verificación
Si accedes correctamente, deberías ver:
- Total Items: 144
- Disponibles: 144
- Una tabla con 144 items

## Si Aún No Funciona
Dime exactamente qué URL ves en la barra de direcciones cuando estás en la página de inventario.
