# Documento de Requisitos: Security Hardening

## Introducción

La aplicación Flask "Reserva" gestiona préstamos de equipos, reservas de salas e inventario
institucional. Actualmente presenta varios problemas de seguridad que deben corregirse antes
de operar en un entorno de producción: credenciales hardcodeadas, ausencia de protección CSRF,
cookies de sesión sin flags de seguridad, falta de rate limiting y ausencia de páginas de error
personalizadas. Este documento define los requisitos para endurecer la seguridad de la aplicación.

## Glosario

- **App**: La aplicación Flask "Reserva".
- **Config**: El módulo `config.py` y las clases de configuración de la aplicación.
- **Database_Module**: El módulo `database.py` y la clase `CustomSQLAlchemy`.
- **Session_Manager**: El componente de Flask que gestiona las cookies de sesión de usuario.
- **CSRF_Guard**: El mecanismo de protección contra Cross-Site Request Forgery (Flask-WTF o equivalente).
- **Rate_Limiter**: El componente que limita la frecuencia de peticiones por IP/usuario (Flask-Limiter o equivalente).
- **Error_Handler**: El componente que intercepta errores HTTP y renderiza páginas de error personalizadas.
- **Env_File**: El archivo `.env` que almacena variables de entorno sensibles fuera del código fuente.
- **Script_Util**: Cualquier archivo `check_*.py`, `test_*.py` o script de utilidad con acceso directo a la base de datos.
- **Auxiliar**: Usuario con rol `auxiliar` en el sistema.
- **Admin**: Usuario con rol `admin` o `superadmin` en el sistema.


## Requisitos

### Requisito 1: Eliminación de Credenciales Hardcodeadas

**User Story:** Como administrador del sistema, quiero que ninguna credencial sensible esté
escrita directamente en el código fuente, para que una exposición del repositorio no comprometa
la base de datos ni otros servicios.

#### Criterios de Aceptación

1. THE Config SHALL leer la URL de conexión a la base de datos exclusivamente desde la variable
   de entorno `DATABASE_URL`, sin ningún valor por defecto hardcodeado en el código fuente.
2. THE Config SHALL leer la clave secreta de Flask exclusivamente desde la variable de entorno
   `FLASK_SECRET_KEY`, sin ningún valor por defecto hardcodeado en el código fuente.
3. THE Database_Module SHALL obtener los parámetros de conexión a PostgreSQL exclusivamente
   desde variables de entorno, sin contraseñas literales en el código fuente.
4. WHEN la variable de entorno `DATABASE_URL` no está definida al iniciar la App,
   THE App SHALL registrar un error crítico en el log y detener el arranque.
5. THE Config SHALL proveer un archivo `.env.example` con todas las variables de entorno
   requeridas documentadas, sin valores reales.
6. IF el archivo `.env` existe en el repositorio, THEN THE App SHALL incluir `.env` en
   `.gitignore` para evitar su inclusión en el control de versiones.

---

### Requisito 2: Refactorización de CustomSQLAlchemy

**User Story:** Como desarrollador, quiero que la conexión a la base de datos use el mecanismo
estándar de SQLAlchemy con URL correctamente codificada, para eliminar el workaround frágil
de `CustomSQLAlchemy` y reducir la superficie de ataque.

#### Criterios de Aceptación

1. THE Database_Module SHALL usar `flask_sqlalchemy.SQLAlchemy` estándar sin subclases
   personalizadas que sobreescriban `init_app`.
2. THE Config SHALL construir la `SQLALCHEMY_DATABASE_URI` codificando correctamente los
   caracteres especiales de la contraseña mediante `urllib.parse.quote_plus` antes de
   asignarla a la configuración.
3. WHEN la `SQLALCHEMY_DATABASE_URI` es construida, THE Config SHALL validar que la URI
   resultante sea parseable por SQLAlchemy sin errores.
4. IF la construcción de la URI falla, THEN THE App SHALL registrar el error y detener
   el arranque en lugar de caer silenciosamente a SQLite.


---

### Requisito 3: Eliminación de Scripts de Utilidad del Repositorio

**User Story:** Como administrador de seguridad, quiero que los scripts de diagnóstico y prueba
con acceso directo a la base de datos no estén en el repositorio de producción, para evitar
que sean ejecutados accidentalmente o expongan credenciales.

#### Criterios de Aceptación

1. THE App SHALL incluir en `.gitignore` todos los archivos que coincidan con los patrones
   `check_*.py`, `test_*.py`, `add_*.py` y `actualizar_*.py` en la raíz del proyecto.
2. WHERE un Script_Util deba mantenerse para uso de desarrollo, THE Script_Util SHALL
   leer sus credenciales de conexión exclusivamente desde variables de entorno o desde
   un archivo `.env` local, nunca con valores hardcodeados.
3. THE App SHALL documentar en el `README` el procedimiento para ejecutar tareas de
   mantenimiento de base de datos de forma segura.

---

### Requisito 4: Protección CSRF en Formularios

**User Story:** Como usuario del sistema, quiero que todos los formularios estén protegidos
contra ataques Cross-Site Request Forgery, para que acciones maliciosas desde sitios externos
no puedan ejecutarse en mi nombre.

#### Criterios de Aceptación

1. THE CSRF_Guard SHALL estar habilitado globalmente en la App para todas las rutas que
   acepten métodos POST, PUT, PATCH o DELETE.
2. WHEN un formulario HTML es renderizado, THE CSRF_Guard SHALL incluir un token CSRF
   oculto en el formulario.
3. WHEN una petición POST, PUT, PATCH o DELETE es recibida sin un token CSRF válido,
   THE CSRF_Guard SHALL rechazar la petición con código HTTP 400.
4. WHEN una petición POST, PUT, PATCH o DELETE es recibida con un token CSRF válido,
   THE CSRF_Guard SHALL permitir que la petición continúe su procesamiento normal.
5. WHERE una ruta acepta peticiones JSON de una API interna, THE CSRF_Guard SHALL
   validar el token CSRF mediante el header `X-CSRFToken` en lugar del campo de formulario.

---

### Requisito 5: Flags de Seguridad en Cookies de Sesión

**User Story:** Como administrador del sistema, quiero que las cookies de sesión tengan
configurados los flags de seguridad apropiados, para mitigar ataques de robo de sesión
mediante XSS o intercepción de red.

#### Criterios de Aceptación

1. THE Session_Manager SHALL configurar el flag `HttpOnly` en `True` para todas las
   cookies de sesión, impidiendo su acceso desde JavaScript.
2. THE Session_Manager SHALL configurar el flag `Secure` en `True` cuando la App
   opera en entorno de producción, forzando la transmisión exclusiva por HTTPS.
3. THE Session_Manager SHALL configurar `SameSite` en `'Lax'` para todas las cookies
   de sesión, reduciendo el riesgo de CSRF basado en cookies.
4. THE Session_Manager SHALL configurar un tiempo de expiración de sesión no mayor a
   8 horas de inactividad.
5. WHERE la App opera en entorno de desarrollo, THE Session_Manager SHALL permitir
   `Secure=False` para facilitar pruebas locales sin HTTPS.


---

### Requisito 6: Rate Limiting en Rutas Críticas

**User Story:** Como administrador del sistema, quiero que las rutas de autenticación y las
operaciones sensibles tengan límites de frecuencia de peticiones, para dificultar ataques
de fuerza bruta y abuso de la API.

#### Criterios de Aceptación

1. THE Rate_Limiter SHALL limitar las peticiones al endpoint de login a un máximo de
   10 intentos por IP en un período de 1 minuto.
2. WHEN el límite de intentos de login es superado, THE Rate_Limiter SHALL responder
   con código HTTP 429 y un mensaje indicando el tiempo de espera restante.
3. THE Rate_Limiter SHALL limitar las peticiones a los endpoints de creación de recursos
   (nuevo préstamo, nueva reserva) a un máximo de 60 peticiones por IP por minuto.
4. THE Rate_Limiter SHALL limitar las peticiones globales a la App a un máximo de
   200 peticiones por IP por minuto.
5. IF una IP supera el límite global, THEN THE Rate_Limiter SHALL responder con
   código HTTP 429 sin revelar detalles internos del sistema.
6. WHERE la App opera en entorno de pruebas, THE Rate_Limiter SHALL poder ser
   deshabilitado mediante configuración para no interferir con los tests automatizados.

---

### Requisito 7: Manejo de Errores Personalizado

**User Story:** Como usuario del sistema, quiero ver páginas de error amigables cuando
algo falla, para no recibir trazas de código o información técnica interna que pueda
comprometer la seguridad.

#### Criterios de Aceptación

1. WHEN la App recibe una petición a una ruta inexistente, THE Error_Handler SHALL
   renderizar una página HTML personalizada con código HTTP 404 sin exponer rutas
   internas ni trazas de stack.
2. WHEN ocurre un error interno no controlado en la App, THE Error_Handler SHALL
   renderizar una página HTML personalizada con código HTTP 500 sin exponer trazas
   de stack ni detalles de la excepción al usuario.
3. WHEN ocurre un error HTTP 403 (acceso denegado), THE Error_Handler SHALL
   renderizar una página HTML personalizada con código HTTP 403.
4. WHEN ocurre cualquier error HTTP manejado, THE Error_Handler SHALL registrar
   el error completo (incluyendo traza) en el log del servidor para diagnóstico interno.
5. THE Error_Handler SHALL estar registrado para los códigos de error 400, 403, 404
   y 500 como mínimo.
6. IF la App opera en modo DEBUG, THEN THE Error_Handler SHALL mostrar la traza
   completa únicamente en el entorno de desarrollo, nunca en producción.

