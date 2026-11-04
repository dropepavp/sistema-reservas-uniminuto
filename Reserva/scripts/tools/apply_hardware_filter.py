# -*- coding: utf-8 -*-
"""
Script to apply hardware visibility filter in:
 - templates/inventario.html
 - templates/hoja_vida_equipo.html
Only displays Hardware & Ficha Técnica for:
 - Equipos de Cómputo (Portátiles, Todo en Uno, Computadores, Laptops, etc.)
 - Pantallas Digitales Interactivas (ONE SCREEN)
"""
import sys

def update_inventario():
    path = 'templates/inventario.html'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update formInventario hardware section
    p1 = content.find('id="procesador"')
    if p1 == -1:
        print("ERROR: Could not locate id=procesador")
        return False

    p1_start = content.rfind('<!-- SECCI', 0, p1)
    p1_end = content.find('<!-- SECCI', p1)

    if p1_start == -1 or p1_end == -1:
        print("ERROR: Could not locate boundaries for formInventario hardware section")
        return False

    sec1_replacement = """<!-- SECCIÓN 2: ESPECIFICACIONES TÉCNICAS (HOJA DE VIDA) -->
                                        <div id="seccionHardwareNuevoContainer" class="my-2">
                                            <div id="avisoNoHardwareNuevo" class="alert alert-light border small text-muted my-2 p-3 rounded-3 d-flex align-items-center justify-content-between shadow-sm">
                                                <div class="d-flex align-items-center gap-2">
                                                    <i class="bi bi-info-circle-fill text-primary fs-5"></i>
                                                    <span><strong>Ficha Técnica & Hardware:</strong> Solo aplica a Equipos de Cómputo (Portátiles, Todo en Uno) y Pantallas Digitales Interactivas (ONE SCREEN).</span>
                                                </div>
                                                <button type="button" class="btn btn-sm btn-outline-secondary py-1 px-2 text-nowrap ms-2" onclick="toggleForzarHardware('nuevo')">
                                                    <i class="bi bi-sliders"></i> <span id="btnForzarHardwareTextNuevo">Habilitar campos</span>
                                                </button>
                                            </div>

                                            <div id="camposHardwareNuevo" style="display: none;">
                                                <div class="hv-form-section-title">
                                                    <i class="bi bi-cpu-fill text-primary"></i> 2. Ficha Técnica & Hardware (Hoja de Vida)
                                                </div>
                                                <div class="row g-3">
                                                    <div class="col-md-6">
                                                        <label class="form-label fw-semibold" for="procesador">Procesador (CPU):</label>
                                                        <input type="text" class="form-control shadow-sm" id="procesador" name="procesador"
                                                            placeholder="Ej: Intel Core i7-12700H / AMD Ryzen 7">
                                                    </div>
                                                    <div class="col-md-6">
                                                        <label class="form-label fw-semibold" for="ram_gb">Memoria RAM:</label>
                                                        <input type="text" class="form-control shadow-sm" id="ram_gb" name="ram_gb"
                                                            placeholder="Ej: 16 GB DDR4 / 32 GB DDR5">
                                                    </div>
                                                    <div class="col-md-6">
                                                        <label class="form-label fw-semibold" for="almacenamiento">Almacenamiento:</label>
                                                        <input type="text" class="form-control shadow-sm" id="almacenamiento" name="almacenamiento"
                                                            placeholder="Ej: 512 GB SSD NVMe / 1 TB HDD">
                                                    </div>
                                                    <div class="col-md-6">
                                                        <label class="form-label fw-semibold" for="sistema_operativo">Sistema Operativo:</label>
                                                        <input type="text" class="form-control shadow-sm" id="sistema_operativo" name="sistema_operativo"
                                                            placeholder="Ej: Windows 11 Pro, Ubuntu 22.04, macOS">
                                                    </div>
                                                    <div class="col-12">
                                                        <label class="form-label fw-semibold" for="especificaciones_tecnicas">Especificaciones Técnicas Adicionales:</label>
                                                        <textarea class="form-control shadow-sm" id="especificaciones_tecnicas" name="especificaciones_tecnicas"
                                                            rows="2" placeholder="Puertos, tarjeta gráfica, resolución de pantalla, potencia de audio, conectividad, etc."></textarea>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        """

    content = content[:p1_start] + sec1_replacement + content[p1_end:]
    print("Sec 1 (Nuevo) replaced successfully!")

    # 2. Update editModal hardware section
    p2 = content.find('id="editProcesador"')
    if p2 == -1:
        print("ERROR: Could not locate id=editProcesador")
        return False

    p2_start = content.rfind('<!-- SECCI', 0, p2)
    p2_end = content.find('<!-- SECCI', p2)

    if p2_start == -1 or p2_end == -1:
        print("ERROR: Could not locate boundaries for editModal hardware section")
        return False

    sec2_replacement = """<!-- SECCIÓN 2: ESPECIFICACIONES TÉCNICAS (HOJA DE VIDA) -->
                                    <div id="seccionHardwareEditContainer" class="my-2">
                                        <div id="avisoNoHardwareEdit" class="alert alert-light border small text-muted my-2 p-3 rounded-3 d-flex align-items-center justify-content-between shadow-sm">
                                            <div class="d-flex align-items-center gap-2">
                                                <i class="bi bi-info-circle-fill text-primary fs-5"></i>
                                                <span><strong>Ficha Técnica & Hardware:</strong> Solo aplica a Equipos de Cómputo (Portátiles, Todo en Uno) y Pantallas Digitales Interactivas (ONE SCREEN).</span>
                                            </div>
                                            <button type="button" class="btn btn-sm btn-outline-secondary py-1 px-2 text-nowrap ms-2" onclick="toggleForzarHardware('edit')">
                                                <i class="bi bi-sliders"></i> <span id="btnForzarHardwareTextEdit">Habilitar campos</span>
                                            </button>
                                        </div>

                                        <div id="camposHardwareEdit" style="display: none;">
                                            <div class="hv-form-section-title">
                                                <i class="bi bi-cpu-fill text-primary"></i> 2. Ficha Técnica & Hardware (Hoja de Vida)
                                            </div>
                                            <div class="row g-3">
                                                <div class="col-md-6">
                                                    <label class="form-label fw-semibold" for="editProcesador">Procesador (CPU):</label>
                                                    <input type="text" class="form-control shadow-sm" id="editProcesador" name="procesador" placeholder="Ej: Intel Core i7-12700H">
                                                </div>
                                                <div class="col-md-6">
                                                    <label class="form-label fw-semibold" for="editRamGb">Memoria RAM:</label>
                                                    <input type="text" class="form-control shadow-sm" id="editRamGb" name="ram_gb" placeholder="Ej: 16 GB DDR4">
                                                </div>
                                                <div class="col-md-6">
                                                    <label class="form-label fw-semibold" for="editAlmacenamiento">Almacenamiento:</label>
                                                    <input type="text" class="form-control shadow-sm" id="editAlmacenamiento" name="almacenamiento" placeholder="Ej: 512 GB SSD NVMe">
                                                </div>
                                                <div class="col-md-6">
                                                    <label class="form-label fw-semibold" for="editSistemaOperativo">Sistema Operativo:</label>
                                                    <input type="text" class="form-control shadow-sm" id="editSistemaOperativo" name="sistema_operativo" placeholder="Ej: Windows 11 Pro">
                                                </div>
                                                <div class="col-12">
                                                    <label class="form-label fw-semibold" for="editEspecificacionesTecnicas">Especificaciones Técnicas Adicionales:</label>
                                                    <textarea class="form-control shadow-sm" id="editEspecificacionesTecnicas" name="especificaciones_tecnicas" rows="2" placeholder="Puertos, tarjeta gráfica, pantalla, etc."></textarea>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    """

    content = content[:p2_start] + sec2_replacement + content[p2_end:]
    print("Sec 2 (Edit) replaced successfully!")

    # 3. Add JavaScript logic before DOMContentLoaded
    js_code = """
        // =========================================================================
        // CONTROL CONDICIONAL DE FICHA TÉCNICA & HARDWARE
        // Solo para Equipos de Cómputo y Pantallas Digitales Interactivas (ONE SCREEN)
        // =========================================================================
        window.esEquipoComputoUOneScreen = function(categoria, itemNombre) {
            const c = (categoria || '').toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
            const it = (itemNombre || '').toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();

            const terminosComputoYScreen = [
                'equipos portatiles', 'portatil', 'portatiles', 'todo en uno',
                'computo', 'computador', 'computadora', 'laptop', 'all in one',
                'pantallas digitales interactivas', 'pantalla digital interactiva',
                'pantalla digital', 'pantalla interactiva', 'one screen', '0ne screen'
            ];

            const coincideCat = terminosComputoYScreen.some(t => c.includes(t));
            const coincideItem = terminosComputoYScreen.some(t => it.includes(t)) || it.includes('screen') || it.startsWith('cpu ');

            return coincideCat || coincideItem;
        };

        window.forzarHardwareNuevo = false;
        window.forzarHardwareEdit = false;

        window.toggleForzarHardware = function(modo) {
            if (modo === 'nuevo') {
                window.forzarHardwareNuevo = !window.forzarHardwareNuevo;
                window.actualizarVisibilidadHardware('nuevo');
            } else {
                window.forzarHardwareEdit = !window.forzarHardwareEdit;
                window.actualizarVisibilidadHardware('edit');
            }
        };

        window.actualizarVisibilidadHardware = function(modo) {
            if (modo === 'nuevo') {
                const catEl = document.getElementById('categoria');
                const itemEl = document.getElementById('item');
                const cat = catEl ? catEl.value : '';
                const item = itemEl ? itemEl.value : '';

                const campos = document.getElementById('camposHardwareNuevo');
                const aviso = document.getElementById('avisoNoHardwareNuevo');
                const btnTxt = document.getElementById('btnForzarHardwareTextNuevo');

                const aplica = window.esEquipoComputoUOneScreen(cat, item) || window.forzarHardwareNuevo;

                if (campos) campos.style.display = aplica ? 'block' : 'none';
                if (aviso) {
                    aviso.style.display = (aplica && !window.forzarHardwareNuevo) ? 'none' : 'flex';
                    if (window.forzarHardwareNuevo) {
                        aviso.classList.remove('alert-light');
                        aviso.classList.add('alert-warning');
                    } else {
                        aviso.classList.remove('alert-warning');
                        aviso.classList.add('alert-light');
                    }
                }
                if (btnTxt) {
                    btnTxt.textContent = window.forzarHardwareNuevo ? 'Ocultar campos' : 'Habilitar campos';
                }
            } else if (modo === 'edit') {
                const catEl = document.getElementById('editCategoria');
                const itemEl = document.getElementById('editItem');
                const cat = catEl ? catEl.value : '';
                const item = itemEl ? itemEl.value : '';

                const proc = document.getElementById('editProcesador') ? document.getElementById('editProcesador').value.trim() : '';
                const ram = document.getElementById('editRamGb') ? document.getElementById('editRamGb').value.trim() : '';
                const disco = document.getElementById('editAlmacenamiento') ? document.getElementById('editAlmacenamiento').value.trim() : '';
                const so = document.getElementById('editSistemaOperativo') ? document.getElementById('editSistemaOperativo').value.trim() : '';

                const tieneDatos = (proc !== '' || ram !== '' || disco !== '' || so !== '');
                const campos = document.getElementById('camposHardwareEdit');
                const aviso = document.getElementById('avisoNoHardwareEdit');
                const btnTxt = document.getElementById('btnForzarHardwareTextEdit');

                const aplica = window.esEquipoComputoUOneScreen(cat, item) || tieneDatos || window.forzarHardwareEdit;

                if (campos) campos.style.display = aplica ? 'block' : 'none';
                if (aviso) {
                    aviso.style.display = (aplica && !window.forzarHardwareEdit) ? 'none' : 'flex';
                    if (window.forzarHardwareEdit) {
                        aviso.classList.remove('alert-light');
                        aviso.classList.add('alert-warning');
                    } else {
                        aviso.classList.remove('alert-warning');
                        aviso.classList.add('alert-light');
                    }
                }
                if (btnTxt) {
                    btnTxt.textContent = window.forzarHardwareEdit ? 'Ocultar campos' : 'Habilitar campos';
                }
            }
        };
"""

    dom_target = "document.addEventListener('DOMContentLoaded', function () {"
    if dom_target in content:
        content = content.replace(dom_target, js_code + "\n            " + dom_target, 1)
        print("JS helper functions inserted before DOMContentLoaded")
    else:
        print("ERROR: dom_target not found")
        return False

    # In DOMContentLoaded, hook listeners for inputs
    hook_code = """
                // Listeners para visibilidad condicional de Ficha Técnica & Hardware
                const catInputNuevo = document.getElementById('categoria');
                if (catInputNuevo) {
                    catInputNuevo.addEventListener('change', () => window.actualizarVisibilidadHardware('nuevo'));
                }
                if (itemInput) {
                    itemInput.addEventListener('input', () => window.actualizarVisibilidadHardware('nuevo'));
                    itemInput.addEventListener('change', () => window.actualizarVisibilidadHardware('nuevo'));
                }

                const catInputEdit = document.getElementById('editCategoria');
                if (catInputEdit) {
                    catInputEdit.addEventListener('change', () => window.actualizarVisibilidadHardware('edit'));
                }
                if (editItemInput) {
                    editItemInput.addEventListener('input', () => window.actualizarVisibilidadHardware('edit'));
                    editItemInput.addEventListener('change', () => window.actualizarVisibilidadHardware('edit'));
                }

                // Evaluar visibilidad inicial para el formulario de nuevo ítem
                window.actualizarVisibilidadHardware('nuevo');
"""

    dropzone_target = "setupDropzone('fotoDropzoneEdit', 'fotoEdit', previewImageEdit);"
    if dropzone_target in content:
        content = content.replace(dropzone_target, dropzone_target + "\n" + hook_code, 1)
        print("Input event listeners hooked into DOMContentLoaded")
    else:
        print("ERROR: dropzone_target not found")
        return False

    # Also hook inside fetch .btn-edit response (after loading specs)
    btn_edit_target = "document.getElementById('editEspecificacionesTecnicas').value = item.especificaciones_tecnicas || '';"
    if btn_edit_target in content:
        content = content.replace(btn_edit_target, btn_edit_target + "\n                                    window.actualizarVisibilidadHardware('edit');", 1)
        print("Hooked into fetch .btn-edit callback")
    else:
        print("ERROR: btn_edit_target not found")
        return False

    # Also hook into the table delegation click for .btn-edit
    delegation_target = "document.getElementById('editSerial').value = row.cells[5].textContent.replace('--', '').trim();"
    if delegation_target in content:
        content = content.replace(delegation_target, delegation_target + "\n                            window.actualizarVisibilidadHardware('edit');", 1)
        print("Hooked into table delegation .btn-edit")
    else:
        print("ERROR: delegation_target not found")
        return False

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("templates/inventario.html successfully updated!")
    return True

def update_hoja_vida():
    path = 'templates/hoja_vida_equipo.html'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    p_f3 = content.find('<!-- Fila 3: Hardware Clave -->')
    if p_f3 == -1:
        print("ERROR: Could not locate Fila 3 in hoja_vida_equipo.html")
        return False

    # Find end of Fila 4 (Sistema Operativo block)
    p_f5 = content.find('<!-- Fila 5: Proveedor y Garant', p_f3)
    if p_f5 == -1:
        print("ERROR: Could not locate Fila 5 in hoja_vida_equipo.html")
        return False

    original_hardware_block = content[p_f3:p_f5]

    wrapped_hardware_block = """{# Solo mostrar Hardware para Equipos de Cómputo, Pantallas Digitales ONE SCREEN o si tiene datos técnicos registrados #}
                        {% set cat_norm = (equipo.categoria or '')|lower %}
                        {% set item_norm = (equipo.item or '')|lower %}
                        {% set es_hardware = ('portatil' in cat_norm or 'portatiles' in cat_norm or 'todo en uno' in cat_norm or 'comput' in cat_norm or 'pantalla' in cat_norm or 'screen' in cat_norm or 'portatil' in item_norm or 'comput' in item_norm or 'laptop' in item_norm or 'screen' in item_norm or equipo.procesador or equipo.ram_gb or equipo.almacenamiento or equipo.sistema_operativo) %}
                        {% if es_hardware %}
                        """ + original_hardware_block.strip() + """
                        {% endif %}

                        """

    content = content[:p_f3] + wrapped_hardware_block + content[p_f5:]

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("templates/hoja_vida_equipo.html successfully updated!")
    return True

if __name__ == '__main__':
    ok1 = update_inventario()
    ok2 = update_hoja_vida()
    if not (ok1 and ok2):
        sys.exit(1)
    print("ALL UPDATES APPLIED SUCCESSFULLY!")
