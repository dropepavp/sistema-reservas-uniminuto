"use strict";

/**
 * Script para inicializar las tablas con DataTables y gestionar funcionalidades asociadas.
 */
// Inicializar DataTables cuando el DOM esté listo
$(document).ready(function () {
  // Inicializar todas las tablas con la clase 'datatable'
  $('.datatable').each(function () {
    $(this).DataTable({
      language: {
        url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json'
      },
      // responsive: true, // Desactivado para favorecer el scroll horizontal
      pageLength: 10,
      lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "Todos"]],
      scrollX: true,
      // Activa el scroll horizontal
      scrollY: '50vh',
      // Activa el scroll vertical con una altura del 50% de la ventana
      scrollCollapse: true,
      // Ajusta la altura si hay pocos registros
      // Estructura del DOM para una mejor integración con Bootstrap 5
      // 'l' - length changing input
      // 'f' - filtering input (el buscador)
      // 'B' - Buttons
      // 't' - The table
      // 'i' - Table information summary
      // 'p' - pagination control
      dom: "<'row mb-3'<'col-sm-12 col-md-6'l><'col-sm-12 col-md-6'f>>" + "<'row'<'col-sm-12'tr>>" + "<'row mt-3'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>" + "<'row mt-3'<'col-sm-12'B>>",
      buttons: [{
        extend: 'copy',
        text: '<i class="bi bi-clipboard"></i> Copiar',
        className: 'btn btn-outline-secondary'
      }, {
        extend: 'csv',
        text: '<i class="bi bi-file-earmark-spreadsheet"></i> CSV',
        className: 'btn btn-outline-secondary'
      }, {
        extend: 'excel',
        text: '<i class="bi bi-file-excel"></i> Excel',
        className: 'btn btn-outline-secondary'
      }, {
        extend: 'pdf',
        text: '<i class="bi bi-file-pdf"></i> PDF',
        className: 'btn btn-outline-secondary'
      }, {
        extend: 'print',
        text: '<i class="bi bi-printer"></i> Imprimir',
        className: 'btn btn-outline-secondary'
      }]
    });
  });
});