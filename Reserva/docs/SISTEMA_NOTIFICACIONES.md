# 🚀 Sistema de Notificaciones en Tiempo Real

## 📋 Descripción General

El Sistema de Notificaciones en Tiempo Real es una implementación completa que permite a los usuarios recibir alertas instantáneas sobre eventos importantes en el sistema de reservas UNIMINUTO.

## ✨ Características Principales

### 1. **Notificaciones Toast en Tiempo Real**
- Alertas visuales elegantes que aparecen en la esquina inferior derecha
- 4 tipos de notificaciones: success, danger, warning, info
- Animaciones suaves de entrada y salida
- Configuración de duración personalizable
- Soporte para notificaciones persistentes

### 2. **Panel de Notificaciones en Navbar**
- Badge con contador de notificaciones no leídas
- Panel desplegable con historial de notificaciones
- Acciones directas a través de las notificaciones
- Opción para marcar todas como leídas
- Diseño responsive para móviles

### 3. **Sonidos Sutiles**
- Alertas sonoras discretas usando Web Audio API
- Diferentes tonos según el tipo de notificación
- No requiere archivos externos
- Opción para activar/desactivar sonidos

### 4. **Eventos Socket.IO Integrados**
- `nueva_reserva` - Cuando se crea una nueva reserva
- `reserva_cancelada` - Cuando se cancela una reserva
- `prestamo_creado` - Cuando se registra un nuevo préstamo
- `prestamo_devuelto` - Cuando se devuelve un equipo
- `prestamo_vencido` - Cuando un préstamo está vencido
- `inventario_cambiado` - Cuando se modifica el inventario
- `alerta_sistema` - Alertas generales del sistema
- `estadisticas_actualizadas` - Actualización de estadísticas

## 🛠️ Arquitectura del Sistema

### Componentes Principales

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (Cliente)                        │
├─────────────────────────────────────────────────────────────┤
│  • notifications.js        - Lógica cliente de notificaciones │
│  • notifications.css       - Estilos visuales               │
│  • Socket.IO Client        - Conexión WebSocket             │
└─────────────────────────────────────────────────────────────┘
                              ↕ Socket.IO
┌─────────────────────────────────────────────────────────────┐
│                   BACKEND (Servidor)                         │
├─────────────────────────────────────────────────────────────┤
│  • notification_service.py - Servicio de notificaciones      │
│  • Socket.IO Server         - Servidor WebSocket            │
│  • Blueprints              - Integración en módulos         │
└─────────────────────────────────────────────────────────────┘
```

### Archivos Creados/Modificados

**Nuevos Archivos:**
- `static/js/notifications.js` - Sistema de notificaciones cliente
- `static/css/notifications.css` - Estilos mejorados
- `services/notification_service.py` - Servicio centralizado

**Archivos Modificados:**
- `templates/components/footer.html` - Integración del script
- `templates/components/header.html` - Inclusión de estilos
- `blueprints/reservas.py` - Notificaciones de reservas
- `blueprints/prestamos.py` - Notificaciones de préstamos
- `blueprints/inventario.py` - Notificaciones de inventario
- `services/prestamo_service.py` - Notificaciones en servicio de préstamos

## 📖 Uso del Sistema

### Para Desarrolladores

#### 1. **Emitir una Notificación**

```python
from services.notification_service import NotificationService

# Notificación simple
NotificationService.notify_nueva_reserva(
    reserva_id=123,
    recurso_nombre="A501",
    profesor="Juan Pérez",
    url="/reservas/123"
)

# Notificación con destino específico
NotificationService.notify_alerta_sistema(
    mensaje="Mantenimiento programado",
    tipo='info',
    target_role='admin'  # Solo para administradores
)
```

#### 2. **Agregar Nueva Notificación en el Frontend**

```javascript
// En notifications.js, agregar listener para nuevo evento
socket.on('nuevo_evento', (data) => {
    this.showNotification({
        title: 'Título de la Notificación',
        message: data.message,
        type: 'info',
        icon: 'bi-icon-name',
        action: data.url,
        sound: 'success'
    });
});
```

#### 3. **Usar el Sistema en JavaScript**

```javascript
// Notificar desde cualquier parte del frontend
if (window.notificationSystem) {
    window.notificationSystem.notify({
        title: 'Mi Notificación',
        message: 'Mensaje personalizado',
        type: 'success',
        icon: 'bi-check-circle',
        sound: 'success'
    });
}
```

### Para Usuarios

#### 1. **Ver Notificaciones**
- Las notificaciones aparecen automáticamente como toast
- Revisar el badge en el navbar (🔔)
- Hacer clic en el icono de campana para ver el historial

#### 2. **Gestionar Notificaciones**
- Clic en una notificación para navegar a la acción relacionada
- Usar "Marcar todas como leídas" para limpiar el badge
- Las notificaciones se guardan en localStorage

#### 3. **Configurar Sonidos**
- Los sonidos están activados por defecto
- Para desactivar: `window.notificationSystem.toggleSound()`

## 🧪 Pruebas del Sistema

### Prueba Manual

1. **Iniciar la aplicación:**
   ```bash
   python run.py
   ```

2. **Abrir el navegador:**
   - Navegar a `http://localhost:5000`
   - Iniciar sesión

3. **Probar notificaciones:**
   - Crear una nueva reserva → Debería aparecer notificación
   - Registrar un préstamo → Notificación de préstamo creado
   - Modificar inventario → Notificación de cambio
   - Cancelar una reserva → Notificación de cancelación

### Prueba con Consola del Navegador

```javascript
// En la consola del navegador:
window.notificationSystem.notify({
    title: 'Prueba Manual',
    message: 'Esta es una notificación de prueba',
    type: 'success',
    icon: 'bi-check-circle',
    sound: 'success'
});

// Probar sonidos
window.notificationSystem.toggleSound(); // Alternar sonidos
```

## 🔧 Configuración

### Variables de Entorno
No se requieren variables de entorno adicionales. El sistema utiliza la configuración existente de Socket.IO.

### Personalización

#### **Colores y Estilos**
Editar `static/css/notifications.css`:
```css
.ui-toast.success {
    border-left-color: #16a34a; /* Color verde personalizado */
    background: linear-gradient(135deg, rgba(22, 163, 74, 0.05) 0%, rgba(255, 255, 255, 0.95) 100%);
}
```

#### **Sonidos**
Editar en `static/js/notifications.js`:
```javascript
createBeep(frequency, duration) {
    // Personalizar frecuencia y duración
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    // ... código existente
}
```

#### **Duración de Toasts**
```javascript
toast(msg, type = 'info', duration = 4000) {
    // Cambiar duración predeterminada
}
```

## 🎯 Eventos Soportados

| Evento | Descripción | Datos Requeridos |
|--------|-------------|------------------|
| `nueva_reserva` | Nueva reserva creada | `reserva_id`, `recurso_nombre`, `profesor`, `url` |
| `reserva_cancelada` | Reserva cancelada | `reserva_id`, `recurso_nombre`, `url` |
| `prestamo_creado` | Nuevo préstamo registrado | `prestamo_id`, `equipo`, `profesor`, `url` |
| `prestamo_devuelto` | Equipo devuelto | `prestamo_id`, `equipo`, `url` |
| `prestamo_vencido` | Préstamo vencido | `prestamo_id`, `equipo`, `fecha_devolucion`, `url` |
| `inventario_cambiado` | Inventario modificado | `accion`, `item_id`, `item_nombre`, `url` |
| `alerta_sistema` | Alerta general | `message`, `type` |
| `estadisticas_actualizadas` | Estadísticas actualizadas | `periodo` |

## 🐛 Solución de Problemas

### **Las notificaciones no aparecen**

1. **Verificar conexión Socket.IO:**
   ```javascript
   // En consola del navegador
   console.log(window.notificationSystem.socket.connected);
   ```

2. **Revisar consola del servidor:**
   - Buscar errores de Socket.IO
   - Verificar que el servidor Socket.IO esté iniciado

3. **Verificar JavaScript:**
   - Abrir consola del navegador (F12)
   - Buscar errores de JavaScript
   - Verificar que `notifications.js` esté cargado

### **Sonidos no funcionan**

1. **Verificar permisos del navegador:**
   - Algunos navegadores bloquean audio automático
   - El usuario debe interactuar con la página primero

2. **Probar manualmente:**
   ```javascript
   window.notificationSystem.toggleSound();
   window.notificationSystem.notify({
       title: 'Prueba de Sonido',
       message: 'Deberías escuchar un sonido',
       type: 'info',
       sound: 'success'
   });
   ```

### **Badge no se actualiza**

1. **Verificar localStorage:**
   ```javascript
   console.log(localStorage.getItem('notifications'));
   ```

2. **Limpiar caché:**
   ```javascript
   localStorage.clear();
   location.reload();
   ```

## 📊 Métricas de Uso

El sistema registra automáticamente:
- Timestamp de cada notificación
- Usuario que generó la notificación
- Tipo de notificación
- Estado (leída/no leída)

## 🚀 Próximas Mejoras

1. **Notificaciones Push del Navegador**
   - Integración con Service Workers
   - Notificaciones cuando el navegador está cerrado

2. **Canales de Notificación Personalizados**
   - Suscripción a tipos específicos de notificaciones
   - Preferencias por usuario

3. **Analytics de Notificaciones**
   - Tasas de apertura
   - Tiempo de respuesta
   - Notificaciones más populares

4. **Integración con Email**
   - Resumen diario de notificaciones
   - Alertas críticas por email

## 📝 Notas Técnicas

- **Compatibilidad:** Funciona en todos los navegadores modernos
- **Performance:** Uso mínimo de recursos, conexiones eficientes
- **Seguridad:** Validación de datos en servidor y cliente
- **Escalabilidad:** Arquitectura preparada para alto volumen

## 👥 Contribución

Para agregar nuevas notificaciones:

1. **Backend:** Agregar método en `NotificationService`
2. **Frontend:** Agregar listener en `notifications.js`
3. **Integración:** Llamar al servicio en el blueprint correspondiente
4. **Pruebas:** Verificar funcionamiento en desarrollo

---

**Versión:** 1.0.0  
**Fecha de Implementación:** 15/08/2026  
**Autor:** Sistema UNIMINUTO