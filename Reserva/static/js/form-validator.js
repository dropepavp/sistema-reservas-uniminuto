/**
 * Sistema de Validación en Tiempo Real para Formularios
 * Proporciona validación instantánea con feedback visual
 * Autocompletado inteligente y guardado automático de borradores
 */

class FormValidator {
    constructor(options = {}) {
        this.forms = new Map();
        this.validators = new Map();
        this.autocompleteProviders = new Map();
        this.draftStorage = new Map();
        this.debounceTimers = new Map();
        
        this.options = {
            validateOnBlur: options.validateOnBlur !== false,
            validateOnInput: options.validateOnInput !== false,
            showSuccess: options.showSuccess !== false,
            debounceTime: options.debounceTime || 300,
            enableDrafts: options.enableDrafts !== false,
            draftAutoSave: options.draftAutoSave || 5000,
            ...options
        };
        
        this.init();
    }
    
    init() {
        // Inicializar validadores predeterminados
        this.registerDefaultValidators();
        
        // Inicializar autocompletado de profesores
        this.setupProfessorAutocomplete();
        
        // Inicializar guardado de borradores
        if (this.options.enableDrafts) {
            this.setupDraftAutoSave();
        }
        
        // Exponer al contexto global
        window.FormValidator = this;
    }
    
    registerDefaultValidators() {
        // Validador de cédula
        this.registerValidator('cedula', (value) => {
            if (!value) return { valid: false, message: 'La cédula es requerida' };
            
            const cleanValue = value.toString().trim();
            
            // Solo dígitos
            if (!/^\d+$/.test(cleanValue)) {
                return { valid: false, message: 'La cédula debe contener solo números' };
            }
            
            // Longitud razonable (entre 5 y 15 dígitos)
            if (cleanValue.length < 5 || cleanValue.length > 15) {
                return { valid: false, message: 'La cédula debe tener entre 5 y 15 dígitos' };
            }
            
            return { valid: true, message: 'Cédula válida' };
        });
        
        // Validador de email
        this.registerValidator('email', (value) => {
            if (!value) return { valid: false, message: 'El email es requerido' };
            
            const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
            if (!emailRegex.test(value)) {
                return { valid: false, message: 'Formato de email inválido' };
            }
            
            return { valid: true, message: 'Email válido' };
        });
        
        // Validador de teléfono
        this.registerValidator('telefono', (value) => {
            if (!value) return { valid: true, message: '' }; // Campo opcional
            
            const cleanPhone = value.replace(/[\s\-\(\)]/g, '');
            if (!/^\d{7,15}$/.test(cleanPhone)) {
                return { valid: false, message: 'El teléfono debe tener entre 7 y 15 dígitos' };
            }
            
            return { valid: true, message: 'Teléfono válido' };
        });
        
        // Validador de hora (HH:MM)
        this.registerValidator('hora', (value) => {
            if (!value) return { valid: false, message: 'La hora es requerida' };
            
            const timeRegex = /^([01]\d|2[0-3]):([0-5]\d)$/;
            if (!timeRegex.test(value)) {
                return { valid: false, message: 'Formato inválido. Use HH:MM (ej: 14:30)' };
            }
            
            return { valid: true, message: 'Hora válida' };
        });
        
        // Validador de fecha futura
        this.registerValidator('fecha_futura', (value) => {
            if (!value) return { valid: false, message: 'La fecha es requerida' };
            
            const inputDate = new Date(value);
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            
            if (inputDate < today) {
                return { valid: false, message: 'La fecha debe ser futura o actual' };
            }
            
            // Limitar a 1 año en el futuro
            const maxDate = new Date();
            maxDate.setFullYear(maxDate.getFullYear() + 1);
            if (inputDate > maxDate) {
                return { valid: false, message: 'La fecha no puede ser más de 1 año en el futuro' };
            }
            
            return { valid: true, message: 'Fecha válida' };
        });
        
        // Validador de nombre
        this.registerValidator('nombre', (value) => {
            if (!value) return { valid: false, message: 'El nombre es requerido' };
            
            if (value.trim().length < 2) {
                return { valid: false, message: 'El nombre debe tener al menos 2 caracteres' };
            }
            
            if (value.trim().length > 100) {
                return { valid: false, message: 'El nombre es demasiado largo' };
            }
            
            return { valid: true, message: 'Nombre válido' };
        });
        
        // Validador de contraseña
        this.registerValidator('password', (value) => {
            if (!value) return { valid: false, message: 'La contraseña es requerida' };
            
            if (value.length < 8) {
                return { valid: false, message: 'La contraseña debe tener al menos 8 caracteres' };
            }
            
            if (!/[A-Za-z]/.test(value) || !/[0-9]/.test(value)) {
                return { valid: false, message: 'La contraseña debe contener letras y números' };
            }
            
            return { valid: true, message: 'Contraseña válida' };
        });
        
        // Validador de NRC
        this.registerValidator('nrc', (value) => {
            if (!value) return { valid: true, message: '' }; // Campo opcional
            
            const nrcRegex = /^[A-Za-z0-9\-]{3,20}$/;
            if (!nrcRegex.test(value)) {
                return { valid: false, message: 'NRC inválido (3-20 caracteres alfanuméricos)' };
            }
            
            return { valid: true, message: 'NRC válido' };
        });
    }
    
    registerValidator(name, validatorFn) {
        this.validators.set(name, validatorFn);
    }
    
    validateField(input, validatorName, options = {}) {
        const value = input.value;
        const validator = this.validators.get(validatorName);
        
        if (!validator) {
            console.warn(`Validator "${validatorName}" not found`);
            return { valid: true, message: '' };
        }
        
        const result = validator(value);
        this.showValidationFeedback(input, result, options);
        
        return result;
    }
    
    showValidationFeedback(input, result, options = {}) {
        const formGroup = input.closest('.form-group') || input.closest('.col-md-6') || input.closest('.col-12');
        if (!formGroup) return;
        
        // Remover feedback anterior
        const existingFeedback = formGroup.querySelector('.validation-feedback');
        if (existingFeedback) existingFeedback.remove();
        
        // Remover clases de validación
        input.classList.remove('is-valid', 'is-invalid');
        
        if (result.valid) {
            if (this.options.showSuccess) {
                input.classList.add('is-valid');
            }
        } else {
            input.classList.add('is-invalid');
            
            // Crear mensaje de error
            const feedback = document.createElement('div');
            feedback.className = 'invalid-feedback validation-feedback';
            feedback.textContent = result.message;
            feedback.style.display = 'block';
            formGroup.appendChild(feedback);
        }
        
        // Trigger evento personalizado
        input.dispatchEvent(new CustomEvent('validation', {
            detail: { valid: result.valid, message: result.message }
        }));
    }
    
    setupForm(formElement, config = {}) {
        const formId = formElement.id || `form-${Date.now()}`;
        this.forms.set(formId, { element: formElement, config });
        
        // Configurar validación para cada campo
        config.fields?.forEach(fieldConfig => {
            const input = formElement.querySelector(`[name="${fieldConfig.name}"]`) || 
                         formElement.querySelector(`#${fieldConfig.name}`);
            
            if (!input) return;
            
            // Validación en input (con debounce)
            if (this.options.validateOnInput) {
                input.addEventListener('input', (e) => {
                    this.debounceValidation(input, fieldConfig.validator);
                });
            }
            
            // Validación en blur
            if (this.options.validateOnBlur) {
                input.addEventListener('blur', () => {
                    this.validateField(input, fieldConfig.validator);
                });
            }
            
            // Validación inicial si tiene valor
            if (input.value) {
                this.validateField(input, fieldConfig.validator);
            }
        });
        
        // Validación del formulario completo
        formElement.addEventListener('submit', (e) => {
            if (!this.validateForm(formElement, config)) {
                e.preventDefault();
            }
        });
        
        return formId;
    }
    
    debounceValidation(input, validatorName) {
        const inputId = input.id || input.name;
        
        // Limpiar timer anterior
        if (this.debounceTimers.has(inputId)) {
            clearTimeout(this.debounceTimers.get(inputId));
        }
        
        // Crear nuevo timer
        const timer = setTimeout(() => {
            this.validateField(input, validatorName);
            this.debounceTimers.delete(inputId);
        }, this.options.debounceTime);
        
        this.debounceTimers.set(inputId, timer);
    }
    
    validateForm(formElement, config) {
        let isValid = true;
        const firstInvalidInput = null;
        
        config.fields?.forEach(fieldConfig => {
            const input = formElement.querySelector(`[name="${fieldConfig.name}"]`) || 
                         formElement.querySelector(`#${fieldConfig.name}`);
            
            if (!input) return;
            
            const result = this.validateField(input, fieldConfig.validator, { immediate: true });
            
            if (!result.valid) {
                isValid = false;
                if (!firstInvalidInput) {
                    firstInvalidInput = input;
                }
            }
        });
        
        if (!isValid && firstInvalidInput) {
            firstInvalidInput.focus();
            firstInvalidInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        
        return isValid;
    }
    
    setupProfessorAutocomplete() {
        const professorInputs = document.querySelectorAll('#busqueda_profesor');
        
        professorInputs.forEach(input => {
            const hiddenInput = document.getElementById('cedula_profesor');
            const suggestionsDiv = document.getElementById('sugerenciasProfesores');
            
            if (!hiddenInput || !suggestionsDiv) return;
            
            // Configurar autocompletado
            input.addEventListener('input', (e) => {
                const query = e.target.value.trim();
                
                if (query.length < 2) {
                    suggestionsDiv.style.display = 'none';
                    return;
                }
                
                this.searchProfessors(query, suggestionsDiv, hiddenInput, input);
            });
            
            // Cerrar sugerencias al hacer clic fuera
            document.addEventListener('click', (e) => {
                if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
                    suggestionsDiv.style.display = 'none';
                }
            });
        });
    }
    
    async searchProfessors(query, suggestionsDiv, hiddenInput, input) {
        try {
            const response = await fetch(`/profesores/buscar?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            if (data.success && data.results.length > 0) {
                this.showSuggestions(data.results, suggestionsDiv, hiddenInput, input);
            } else {
                suggestionsDiv.style.display = 'none';
            }
        } catch (error) {
            console.error('Error al buscar profesores:', error);
        }
    }
    
    showSuggestions(professors, suggestionsDiv, hiddenInput, input) {
        suggestionsDiv.innerHTML = '';
        
        professors.forEach(prof => {
            const item = document.createElement('button');
            item.className = 'list-group-item list-group-item-action';
            item.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${prof.nombre_completo}</strong>
                        <small class="text-muted d-block">Cédula: ${prof.cedula}</small>
                    </div>
                    <small class="text-muted">${prof.programa || 'N/A'}</small>
                </div>
            `;
            
            item.addEventListener('click', () => {
                input.value = prof.nombre_completo;
                hiddenInput.value = prof.cedula;
                suggestionsDiv.style.display = 'none';
                
                // Trigger evento de selección
                input.dispatchEvent(new CustomEvent('professorSelected', {
                    detail: prof
                }));
                
                // Mostrar información del profesor si existe el contenedor
                this.showProfessorInfo(prof);
            });
            
            suggestionsDiv.appendChild(item);
        });
        
        suggestionsDiv.style.display = 'block';
    }
    
    showProfessorInfo(prof) {
        const infoDiv = document.getElementById('infoProfesor');
        if (!infoDiv || !prof) return;
        
        const elNombre = document.getElementById('profesorNombre');
        const elCedula = document.getElementById('profesorCedulaText');
        const elCorreo = document.getElementById('profesorCorreo');
        const elPrograma = document.getElementById('profesorPrograma');

        if (elNombre) elNombre.textContent = prof.nombre_completo || '';
        if (elCedula) elCedula.textContent = prof.cedula || '';
        if (elCorreo) elCorreo.textContent = prof.correo || 'N/A';
        if (elPrograma) elPrograma.textContent = prof.programa || 'N/A';
        
        infoDiv.style.display = 'block';
    }
    
    setupDraftAutoSave() {
        // Configurar autoguardado para formularios importantes
        const formsToSave = ['#formReserva', '#formPrestamo', '#formProfesor'];
        
        formsToSave.forEach(formSelector => {
            const form = document.querySelector(formSelector);
            if (!form) return;
            
            const formId = formSelector.replace('#', '');
            
            // Cargar borrador existente
            this.loadDraft(formId, form);
            
            // Configurar autoguardado
            let saveTimer;
            form.addEventListener('input', () => {
                clearTimeout(saveTimer);
                saveTimer = setTimeout(() => {
                    this.saveDraft(formId, form);
                }, this.options.draftAutoSave);
            });
            
            // Limpiar borrador al enviar
            form.addEventListener('submit', () => {
                this.clearDraft(formId);
            });
        });
    }
    
    saveDraft(formId, form) {
        const formData = new FormData(form);
        const draftData = {};
        
        formData.forEach((value, key) => {
            draftData[key] = value;
        });
        
        localStorage.setItem(`draft_${formId}`, JSON.stringify(draftData));
        
        // Mostrar indicador visual de guardado
        this.showDraftSavedIndicator(form);
    }
    
    loadDraft(formId, form) {
        const draftData = localStorage.getItem(`draft_${formId}`);
        if (!draftData) return;
        
        try {
            const data = JSON.parse(draftData);
            
            Object.keys(data).forEach(key => {
                const input = form.querySelector(`[name="${key}"]`) || form.querySelector(`#${key}`);
                if (input) {
                    input.value = data[key];
                    // Trigger eventos de cambio
                    input.dispatchEvent(new Event('input'));
                    input.dispatchEvent(new Event('change'));
                }
            });
            
            // Mostrar notificación de borrador recuperado
            this.showDraftRestoredNotification(formId);
        } catch (error) {
            console.error('Error al cargar borrador:', error);
        }
    }
    
    clearDraft(formId) {
        localStorage.removeItem(`draft_${formId}`);
    }
    
    showDraftSavedIndicator(form) {
        const existingIndicator = form.querySelector('.draft-saved-indicator');
        if (existingIndicator) existingIndicator.remove();
        
        const indicator = document.createElement('div');
        indicator.className = 'draft-saved-indicator alert alert-info py-1 px-2 mt-2';
        indicator.innerHTML = '<small><i class="bi bi-check-circle"></i> Borrador guardado automáticamente</small>';
        
        form.insertBefore(indicator, form.firstChild);
        
        setTimeout(() => indicator.remove(), 3000);
    }
    
    showDraftRestoredNotification(formId) {
        if (window.notificationSystem) {
            window.notificationSystem.notify({
                title: '📝 Borrador Recuperado',
                message: `Se ha restaurado el borrador guardado del formulario`,
                type: 'info',
                icon: 'bi-file-earmark',
                sound: 'subtle'
            });
        }
    }
    
    // Sistema de Multi-step Forms
    createMultiStepForm(config) {
        const { formId, steps, onComplete } = config;
        const form = document.getElementById(formId);
        if (!form) return;
        
        let currentStep = 0;
        
        // Crear navegación de pasos
        const stepNav = document.createElement('div');
        stepNav.className = 'step-nav mb-4';
        stepNav.innerHTML = this.createStepNavigation(steps);
        
        form.insertBefore(stepNav, form.firstChild);
        
        // Mostrar primer paso
        this.showStep(form, currentStep, steps);
        
        // Configurar navegación
        form.addEventListener('click', (e) => {
            if (e.target.classList.contains('next-step')) {
                if (this.validateCurrentStep(form, currentStep, steps)) {
                    currentStep++;
                    this.showStep(form, currentStep, steps);
                    this.updateStepNav(currentStep, steps);
                }
            } else if (e.target.classList.contains('prev-step')) {
                currentStep--;
                this.showStep(form, currentStep, steps);
                this.updateStepNav(currentStep, steps);
            }
        });
        
        // Modificar submit para validación final
        form.addEventListener('submit', (e) => {
            if (currentStep < steps.length - 1) {
                e.preventDefault();
                if (this.validateCurrentStep(form, currentStep, steps)) {
                    currentStep++;
                    this.showStep(form, currentStep, steps);
                    this.updateStepNav(currentStep, steps);
                }
            } else if (onComplete) {
                onComplete(form);
            }
        });
    }
    
    createStepNavigation(steps) {
        return `
            <div class="progress mb-3" style="height: 25px;">
                <div class="progress-bar step-progress" role="progressbar" style="width: 0%">0%</div>
            </div>
            <div class="d-flex justify-content-between">
                ${steps.map((step, index) => `
                    <div class="step-indicator ${index === 0 ? 'active' : ''}" data-step="${index}">
                        <div class="step-number">${index + 1}</div>
                        <div class="step-title">${step.title}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    showStep(form, stepIndex, steps) {
        // Ocultar todos los pasos
        steps.forEach((step, index) => {
            const stepElement = form.querySelector(`[data-step="${index}"]`);
            if (stepElement) {
                stepElement.style.display = index === stepIndex ? 'block' : 'none';
            }
        });
        
        // Actualizar botones de navegación
        const nextBtn = form.querySelector('.next-step');
        const prevBtn = form.querySelector('.prev-step');
        const submitBtn = form.querySelector('button[type="submit"]');
        
        if (nextBtn) nextBtn.style.display = stepIndex < steps.length - 1 ? 'inline-block' : 'none';
        if (prevBtn) prevBtn.style.display = stepIndex > 0 ? 'inline-block' : 'none';
        if (submitBtn) submitBtn.style.display = stepIndex === steps.length - 1 ? 'inline-block' : 'none';
    }
    
    updateStepNav(currentStep, steps) {
        const progress = ((currentStep + 1) / steps.length) * 100;
        const progressBar = document.querySelector('.step-progress');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
            progressBar.textContent = `${Math.round(progress)}%`;
        }
        
        const indicators = document.querySelectorAll('.step-indicator');
        indicators.forEach((indicator, index) => {
            indicator.classList.toggle('active', index === currentStep);
            indicator.classList.toggle('completed', index < currentStep);
        });
    }
    
    validateCurrentStep(form, stepIndex, steps) {
        const currentStepConfig = steps[stepIndex];
        if (!currentStepConfig.fields) return true;
        
        let isValid = true;
        
        currentStepConfig.fields.forEach(fieldName => {
            const input = form.querySelector(`[name="${fieldName}"]`) || form.querySelector(`#${fieldName}`);
            if (input) {
                const fieldConfig = currentStepConfig.fieldsConfig?.[fieldName];
                if (fieldConfig) {
                    const result = this.validateField(input, fieldConfig.validator);
                    if (!result.valid) isValid = false;
                }
            }
        });
        
        return isValid;
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    window.formValidator = new FormValidator({
        validateOnBlur: true,
        validateOnInput: true,
        showSuccess: true,
        debounceTime: 300,
        enableDrafts: true,
        draftAutoSave: 5000
    });
    
    // Configurar formularios existentes
    setupExistingForms();
});

function setupExistingForms() {
    // Configurar formulario de reservas
    const reservaForm = document.getElementById('formReserva');
    if (reservaForm) {
        window.formValidator.setupForm(reservaForm, {
            fields: [
                { name: 'cedula', validator: 'cedula' },
                { name: 'fecha', validator: 'fecha_futura' },
                { name: 'recurso_nombre', validator: 'nombre' }
            ]
        });
    }
    
    // Configurar formulario de préstamos
    const prestamoForm = document.querySelector('form[action*="prestamos"]');
    if (prestamoForm) {
        window.formValidator.setupForm(prestamoForm, {
            fields: [
                { name: 'cedula', validator: 'cedula' },
                { name: 'hora_inicio', validator: 'hora' },
                { name: 'hora_fin', validator: 'hora' }
            ]
        });
    }
    
    // Configurar formulario de registro de usuario
    const registroForm = document.getElementById('registroForm');
    if (registroForm) {
        window.formValidator.setupForm(registroForm, {
            fields: [
                { name: 'documento', validator: 'cedula' },
                { name: 'email', validator: 'email' },
                { name: 'contraseña', validator: 'password' }
            ]
        });
    }
}