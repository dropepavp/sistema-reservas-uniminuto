/**
 * Sistema de Notificaciones en Tiempo Real
 * Integración con Socket.IO para notificaciones push
 * Sistema de toast notifications mejorado con sonidos y badge
 */

class NotificationSystem {
    constructor() {
        this.socket = null;
        this.unreadCount = 0;
        this.notifications = [];
        this.soundEnabled = true;
        this.badgeElement = null;
        this.notificationPanel = null;
        this.init();
    }

    init() {
        // Inicializar Socket.IO
        if (typeof io !== 'undefined') {
            this.socket = io();
            this.setupSocketListeners();
        } else {
            console.warn('Socket.io no pudo ser cargado. Las notificaciones en tiempo real no estarán disponibles.');
        }

        // Crear elementos UI para notificaciones
        this.createNotificationUI();
        
        // Cargar configuración desde localStorage
        this.loadSettings();
        
        // Exponer interface global
        window.NotificationSystem = this;
    }

    setupSocketListeners() {
        if (!this.socket) return;

        // Evento de nueva reserva
        this.socket.on('nueva_reserva', (data) => {
            this.showNotification({
                title: '📅 Nueva Reserva Creada',
                message: `Reserva #${data.reserva_id} para ${data.recurso_nombre} - ${data.profesor}`,
                type: 'success',
                icon: 'bi-calendar-check',
                action: data.url || '/reservas',
                sound: 'success'
            });
        });

        // Evento de reserva cancelada
        this.socket.on('reserva_cancelada', (data) => {
            this.showNotification({
                title: '❌ Reserva Cancelada',
                message: `Reserva #${data.reserva_id} ha sido cancelada`,
                type: 'warning',
                icon: 'bi-calendar-x',
                action: data.url || '/reservas',
                sound: 'warning'
            });
        });

        // Evento de inventario modificado
        this.socket.on('inventario_cambiado', (data) => {
            const messages = {
                'crear': 'Nuevo equipo agregado al inventario',
                'editar': 'Equipo actualizado en el inventario',
                'eliminar': 'Equipo eliminado del inventario',
                'prestamo': 'Equipo prestado',
                'devolucion': 'Equipo devuelto'
            };
            
            this.showNotification({
                title: '📦 Inventario Actualizado',
                message: `${messages[data.accion] || 'Acción: ' + data.accion} - ${data.item_nombre}`,
                type: data.accion === 'eliminar' ? 'danger' : 'info',
                icon: 'bi-box-seam',
                action: data.url || '/inventario',
                sound: 'info'
            });
        });

        // Evento de préstamo vencido
        this.socket.on('prestamo_vencido', (data) => {
            this.showNotification({
                title: '⚠️ ¡Préstamo Vencido!',
                message: `El equipo ${data.equipo} debió devolverse el ${data.fecha_devolucion}`,
                type: 'danger',
                icon: 'bi-exclamation-triangle-fill',
                action: data.url || '/prestamos',
                sound: 'urgent',
                persistent: true
            });
        });

        // Evento de préstamo creado
        this.socket.on('prestamo_creado', (data) => {
            this.showNotification({
                title: '💻 Nuevo Préstamo Registrado',
                message: `Préstamo #${data.prestamo_id} - ${data.equipo} a ${data.profesor}`,
                type: 'success',
                icon: 'bi-laptop',
                action: data.url || '/prestamos',
                sound: 'success'
            });
        });

        // Evento de préstamo devuelto
        this.socket.on('prestamo_devuelto', (data) => {
            this.showNotification({
                title: '✅ Préstamo Devuelto',
                message: `El equipo ${data.equipo} ha sido devuelto correctamente`,
                type: 'success',
                icon: 'bi-check-circle',
                action: data.url || '/prestamos',
                sound: 'success'
            });
        });

        // Evento de alerta del sistema
        this.socket.on('alerta_sistema', (data) => {
            this.showNotification({
                title: '🔔 Alerta del Sistema',
                message: data.message,
                type: data.type || 'info',
                icon: 'bi-bell',
                sound: 'alert'
            });
        });

        // Evento de actualización de estadísticas
        this.socket.on('estadisticas_actualizadas', (data) => {
            this.showNotification({
                title: '📊 Estadísticas Actualizadas',
                message: `Datos actualizados: ${data.periodo}`,
                type: 'info',
                icon: 'bi-graph-up',
                action: '/estadisticas',
                sound: 'subtle'
            });
        });

        // Conexión establecida
        this.socket.on('connect', () => {
            console.log('🔌 Conectado al servidor de notificaciones');
            this.updateConnectionStatus(true);
        });

        // Desconexión
        this.socket.on('disconnect', () => {
            console.log('🔌 Desconectado del servidor de notificaciones');
            this.updateConnectionStatus(false);
        });
    }

    createNotificationUI() {
        // Crear botón de notificaciones en el navbar
        const navbar = document.querySelector('.app-topbar .d-flex.align-items-center');
        if (!navbar) return;

        // Insertar antes del menú de usuario
        const userMenu = navbar.querySelector('.dropdown');
        if (!userMenu) return;

        const notificationBtn = document.createElement('div');
        notificationBtn.className = 'dropdown me-2';
        notificationBtn.innerHTML = `
            <button class="nav-link dropdown-toggle d-flex align-items-center position-relative" 
                    id="notificationBtn" 
                    role="button" 
                    data-bs-toggle="dropdown" 
                    aria-expanded="false"
                    style="background: transparent; border: none; color: white; padding: 0.5rem;">
                <i class="bi bi-bell fs-5"></i>
                <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger notification-badge"
                      style="display: none; font-size: 0.65rem; padding: 0.25rem 0.4rem;">
                    0
                </span>
            </button>
            <ul class="dropdown-menu dropdown-menu-end dropdown-menu-dark notification-panel"
                aria-labelledby="notificationBtn"
                style="width: 320px; max-height: 400px; overflow-y: auto;">
                <li class="dropdown-header d-flex justify-content-between align-items-center">
                    <span>Notificaciones</span>
                    <button class="btn btn-sm btn-link text-white mark-all-read" style="font-size: 0.75rem;">
                        Marcar todas como leídas
                    </button>
                </li>
                <li><hr class="dropdown-divider"></li>
                <li class="notification-list-empty text-center py-3">
                    <small class="text-muted">No hay notificaciones nuevas</small>
                </li>
            </ul>
        `;

        navbar.insertBefore(notificationBtn, userMenu);
        
        this.badgeElement = notificationBtn.querySelector('.notification-badge');
        this.notificationPanel = notificationBtn.querySelector('.notification-panel');

        // Event listener para marcar todas como leídas
        notificationBtn.querySelector('.mark-all-read').addEventListener('click', () => {
            this.markAllAsRead();
        });
    }

    showNotification(options) {
        const defaults = {
            title: 'Notificación',
            message: '',
            type: 'info', // success, danger, warning, info
            icon: 'bi-bell',
            action: null,
            sound: 'default',
            persistent: false,
            duration: 4000
        };

        const config = { ...defaults, ...options };
        
        // Guardar notificación
        this.notifications.unshift({
            ...config,
            id: Date.now(),
            timestamp: new Date(),
            read: false
        });

        // Actualizar contador
        this.unreadCount++;
        this.updateBadge();

        // Mostrar toast
        this.showToast(config);

        // Reproducir sonido
        if (this.soundEnabled) {
            this.playSound(config.sound);
        }

        // Agregar al panel de notificaciones
        this.addNotificationToPanel(config);

        // Guardar en localStorage
        this.saveNotifications();
    }

    showToast(config) {
        // Usar el sistema existente LoadingUI.toast si está disponible
        if (window.LoadingUI && window.LoadingUI.toast) {
            window.LoadingUI.toast(`${config.title}: ${config.message}`, config.type, config.duration);
        } else {
            // Fallback a toast personalizado
            this.createCustomToast(config);
        }
    }

    createCustomToast(config) {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `ui-toast ${config.type}`;
        toast.innerHTML = `
            <i class="bi ${config.icon} toast-icon"></i>
            <div class="toast-content">
                <div class="toast-title fw-bold">${config.title}</div>
                <div class="toast-msg">${config.message}</div>
            </div>
            <button class="toast-close" aria-label="Cerrar">
                <i class="bi bi-x"></i>
            </button>
        `;

        // Agregar acción si existe
        if (config.action) {
            toast.style.cursor = 'pointer';
            toast.addEventListener('click', () => {
                window.location.href = config.action;
            });
        }

        container.appendChild(toast);

        // Remover después de la duración
        if (!config.persistent) {
            setTimeout(() => {
                toast.style.animation = 'toast-out 0.3s ease forwards';
                setTimeout(() => toast.remove(), 300);
            }, config.duration);
        }

        // Botón de cerrar
        toast.querySelector('.toast-close').addEventListener('click', (e) => {
            e.stopPropagation();
            toast.style.animation = 'toast-out 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        });
    }

    addNotificationToPanel(config) {
        if (!this.notificationPanel) return;

        // Remover mensaje de "no hay notificaciones"
        const emptyMessage = this.notificationPanel.querySelector('.notification-list-empty');
        if (emptyMessage) {
            emptyMessage.remove();
        }

        const notificationItem = document.createElement('li');
        notificationItem.className = 'notification-item dropdown-item';
        notificationItem.style.padding = '0.75rem 1rem';
        notificationItem.style.borderBottom = '1px solid rgba(255,255,255,0.1)';
        notificationItem.innerHTML = `
            <div class="d-flex align-items-start gap-2">
                <div class="notification-icon flex-shrink-0">
                    <i class="bi ${config.icon} fs-5 text-${config.type === 'danger' ? 'danger' : config.type === 'success' ? 'success' : 'info'}"></i>
                </div>
                <div class="flex-grow-1">
                    <div class="fw-bold small">${config.title}</div>
                    <div class="small text-muted" style="font-size: 0.8rem;">${config.message}</div>
                    <div class="small text-muted" style="font-size: 0.7rem; margin-top: 0.25rem;">
                        ${this.formatTime(new Date())}
                    </div>
                </div>
            </div>
        `;

        // Hacer clickeable si hay acción
        if (config.action) {
            notificationItem.style.cursor = 'pointer';
            notificationItem.addEventListener('click', () => {
                window.location.href = config.action;
            });
        }

        // Insertar después del header
        const divider = this.notificationPanel.querySelector('.dropdown-divider');
        if (divider) {
            this.notificationPanel.insertBefore(notificationItem, divider.nextSibling);
        } else {
            this.notificationPanel.appendChild(notificationItem);
        }
    }

    updateBadge() {
        if (!this.badgeElement) return;

        if (this.unreadCount > 0) {
            this.badgeElement.style.display = 'block';
            this.badgeElement.textContent = this.unreadCount > 9 ? '9+' : this.unreadCount;
        } else {
            this.badgeElement.style.display = 'none';
        }
    }

    markAllAsRead() {
        this.unreadCount = 0;
        this.notifications.forEach(n => n.read = true);
        this.updateBadge();
        this.saveNotifications();
        
        // Remover indicador visual de no leído en los items
        const items = this.notificationPanel.querySelectorAll('.notification-item');
        items.forEach(item => {
            item.style.opacity = '0.7';
        });
    }

    playSound(type) {
        const tones = {
            success: [800, 0.1], warning: [600, 0.15], danger: [400, 0.2],
            urgent: [300, 0.3], info: [1000, 0.08], alert: [500, 0.2],
            subtle: [1200, 0.05], default: [700, 0.1]
        };
        const [frequency, duration] = tones[type] || tones.default;
        try {
            this.createBeep(frequency, duration);
        } catch (err) {
            console.log('Audio play blocked:', err);
        }
    }

    createBeep(frequency, duration) {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!AudioContext) return;

            if (!this.audioCtx) {
                this.audioCtx = new AudioContext();
            }

            if (this.audioCtx.state === 'suspended') {
                this.audioCtx.resume().catch(() => {});
            }

            if (this.audioCtx.state !== 'running') return;

            const oscillator = this.audioCtx.createOscillator();
            const gainNode = this.audioCtx.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(this.audioCtx.destination);

            oscillator.frequency.value = frequency;
            oscillator.type = 'sine';

            gainNode.gain.setValueAtTime(0.08, this.audioCtx.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + duration);

            oscillator.start(this.audioCtx.currentTime);
            oscillator.stop(this.audioCtx.currentTime + duration);
        } catch (e) {
            // Silently ignore browser autoplay restrictions
        }
    }

    updateConnectionStatus(connected) {
        const statusIndicator = document.querySelector('.connection-status');
        if (statusIndicator) {
            statusIndicator.className = `connection-status ${connected ? 'connected' : 'disconnected'}`;
            statusIndicator.title = connected ? 'Conectado' : 'Desconectado';
        }
    }

    formatTime(date) {
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'Ahora mismo';
        if (diff < 3600000) return `Hace ${Math.floor(diff / 60000)} min`;
        if (diff < 86400000) return `Hace ${Math.floor(diff / 3600000)} h`;
        return date.toLocaleDateString('es-ES', { day: '2-digit', month: 'short' });
    }

    saveSettings() {
        localStorage.setItem('notificationSettings', JSON.stringify({
            soundEnabled: this.soundEnabled
        }));
    }

    loadSettings() {
        const settings = JSON.parse(localStorage.getItem('notificationSettings') || '{}');
        this.soundEnabled = settings.soundEnabled !== false;
    }

    saveNotifications() {
        // Guardar solo las últimas 50 notificaciones
        const recent = this.notifications.slice(0, 50);
        localStorage.setItem('notifications', JSON.stringify(recent));
    }

    loadNotifications() {
        const saved = JSON.parse(localStorage.getItem('notifications') || '[]');
        this.notifications = saved;
        this.unreadCount = saved.filter(n => !n.read).length;
        this.updateBadge();
    }

    // Método público para enviar notificaciones desde otros scripts
    notify(options) {
        this.showNotification(options);
    }

    // Método para alternar sonidos
    toggleSound() {
        this.soundEnabled = !this.soundEnabled;
        this.saveSettings();
        return this.soundEnabled;
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    window.notificationSystem = new NotificationSystem();
});