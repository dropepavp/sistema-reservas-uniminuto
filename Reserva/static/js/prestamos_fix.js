// ============================================
// SCRIPT DE CORRECCIÓN DE PRÉSTAMOS
// Versión: 2026-03-12 14:50:00 - VERSIÓN AGRESIVA
// ============================================

console.log('%c🔄 NUEVO SCRIPT CARGADO - Versión: 2026-03-12 14:50:00', 'background: #00ff00; color: #000; font-size: 20px; font-weight: bold; padding: 10px;');
console.log('⏰ Timestamp de carga:', new Date().toISOString());

// Esperar a que el DOM esté completamente cargado
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarBotones);
} else {
    // DOM ya está listo
    inicializarBotones();
}

function inicializarBotones() {
    console.log('%c✅ DOM Ready - Inicializando botones (VERSIÓN AGRESIVA)', 'background: #ffff00; color: #000; font-size: 16px; padding: 5px;');
    
    // ELIMINAR TODOS LOS EVENT LISTENERS ANTERIORES clonando los botones
    const botones = ['btnStdPortatil', 'btnStdCargador', 'btnStdHdmi', 'btnStdControl', 'btnStdTeclado'];
    
    botones.forEach(btnId => {
        const btnViejo = document.getElementById(btnId);
        if (btnViejo) {
            const btnNuevo = btnViejo.cloneNode(true);
            btnViejo.parentNode.replaceChild(btnNuevo, btnViejo);
            console.log(`🔄 Botón ${btnId} clonado para eliminar listeners antiguos`);
        }
    });
    
    // Ahora agregar los nuevos event listeners
    
    // BOTÓN PORTÁTIL
    const btnStdPortatil = document.getElementById('btnStdPortatil');
    if (btnStdPortatil) {
        console.log('✅ Botón Portátil encontrado y configurado');
        btnStdPortatil.addEventListener('click', function() {
            console.log('%c🔵 PORTÁTIL CLICKEADO', 'background: #0099ff; color: #fff; font-size: 14px; padding: 5px;');
            if (window.buscarEquiposDesdeInventario) {
                window.buscarEquiposDesdeInventario({ tipo_equipo: 'PORTATIL' });
            }
        });
    }
    
    // BOTÓN CARGADOR - CRÍTICO
    const btnStdCargador = document.getElementById('btnStdCargador');
    if (btnStdCargador) {
        console.log('%c✅ Botón Cargador encontrado y configurado', 'background: #00ff00; color: #000; font-size: 16px; padding: 5px;');
        btnStdCargador.addEventListener('click', function() {
            console.log('%c🔵 CARGADOR CLICKEADO - Buscando ADAPTADORES', 'background: #ff00ff; color: #fff; font-size: 20px; font-weight: bold; padding: 10px;');
            console.log('%cSi aparecen TECLADOS, tu navegador tiene CACHÉ ANTIGUO', 'background: #ff0000; color: #fff; font-size: 16px; padding: 5px;');
            console.log('📍 Timestamp:', new Date().toISOString());
            console.log('📦 Parámetro enviado: { tipo_equipo: "CARGADOR" }');
            
            if (window.buscarEquiposDesdeInventario) {
                window.buscarEquiposDesdeInventario({ tipo_equipo: 'CARGADOR' });
            } else {
                console.error('❌ Función buscarEquiposDesdeInventario no disponible');
                alert('❌ ERROR: Función no disponible - Recarga la página');
            }
        });
    } else {
        console.error('❌ Botón Cargador NO encontrado');
    }
    
    // BOTÓN HDMI
    const btnStdHdmi = document.getElementById('btnStdHdmi');
    if (btnStdHdmi) {
        console.log('✅ Botón HDMI encontrado y configurado');
        btnStdHdmi.addEventListener('click', function() {
            console.log('%c🔵 HDMI CLICKEADO', 'background: #0099ff; color: #fff; font-size: 14px; padding: 5px;');
            if (window.buscarEquiposDesdeInventario) {
                window.buscarEquiposDesdeInventario({ tipo_equipo: 'HDMI' });
            }
        });
    }
    
    // BOTÓN CONTROL
    const btnStdControl = document.getElementById('btnStdControl');
    if (btnStdControl) {
        console.log('✅ Botón Control encontrado y configurado');
        btnStdControl.addEventListener('click', function() {
            console.log('%c🔵 CONTROL CLICKEADO', 'background: #0099ff; color: #fff; font-size: 14px; padding: 5px;');
            if (window.buscarEquiposDesdeInventario && window.sugerirMarcaControl && window.getSalonDesdeUbicacion) {
                const marca = window.sugerirMarcaControl();
                const salon = window.getSalonDesdeUbicacion();
                const filtros = { tipo_equipo: 'CONTROL' };
                if (marca) filtros.marca = marca;
                if (salon) filtros.salon = salon;
                console.log('📦 Filtros para control:', filtros);
                window.buscarEquiposDesdeInventario(filtros);
            }
        });
    }
    
    // BOTÓN TECLADO
    const btnStdTeclado = document.getElementById('btnStdTeclado');
    if (btnStdTeclado) {
        console.log('✅ Botón Teclado encontrado y configurado');
        btnStdTeclado.addEventListener('click', function() {
            console.log('%c🔵 TECLADO CLICKEADO', 'background: #0099ff; color: #fff; font-size: 14px; padding: 5px;');
            if (window.buscarEquiposDesdeInventario) {
                window.buscarEquiposDesdeInventario({ tipo_equipo: 'TECLADO' });
            }
        });
    }
    
    console.log('%c✅ TODOS LOS BOTONES CONFIGURADOS CORRECTAMENTE', 'background: #00ff00; color: #000; font-size: 18px; font-weight: bold; padding: 10px;');
    console.log('%c👉 Haz clic en el botón CARGADOR para probar', 'background: #ffff00; color: #000; font-size: 16px; padding: 5px;');
}

console.log('📝 Fin del script prestamos_fix.js - Versión 14:50:00');
