/**
 * Script para inicializar DataTables con exportaciones y funcionalidades completas
 */
$(document).ready(function () {
    console.log('🚀 Inicializando DataTables profesional...');

    $('.datatable').each(function () {
        const $table = $(this);
        const isMinimal = $table.hasClass('minimal-datatable');

        // Evitar doble inicialización
        if ($.fn.DataTable.isDataTable(this)) {
            $(this).DataTable().destroy();
        }

        const table = $table.DataTable({
            language: {
                "processing": "Procesando...",
                "lengthMenu": "Mostrar _MENU_ registros",
                "zeroRecords": "No se encontraron resultados",
                "emptyTable": "Ningún dato disponible en esta tabla",
                "info": "Mostrando del _START_ al _END_ de _TOTAL_ registros",
                "infoEmpty": "Mostrando del 0 al 0 de 0 registros",
                "infoFiltered": "(filtrado de _MAX_ registros totales)",
                "search": "Buscar:",
                "loadingRecords": "Cargando...",
                "paginate": {
                    "first": "Primero",
                    "last": "Último",
                    "next": "Siguiente",
                    "previous": "Anterior"
                }
            },
            responsive: false,
            scrollX: false, // Desactivamos el scroll de DataTables para usar el nuestro mejorado
            scrollCollapse: true,
            pageLength: 25,
            searching: true, // Debe estar en true para que search() API funcione, pero lo ocultamos vía dom
            lengthChange: !isMinimal,
            dom: isMinimal ? "tr<'row mt-3'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>" :
                "<'row mb-3'<'col-sm-12 col-md-4'l><'col-sm-12 col-md-4 text-center'B><'col-sm-12 col-md-4'f>>" +
                "<'row'<'col-sm-12'tr>>" +
                "<'row mt-3'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>",
            buttons: isMinimal ? [] : [
                {
                    extend: 'excel',
                    text: '<i class="bi bi-file-earmark-spreadsheet"></i> Excel',
                    className: 'btn btn-outline-success btn-sm'
                },
                {
                    extend: 'pdf',
                    text: '<i class="bi bi-file-earmark-pdf"></i> PDF',
                    className: 'btn btn-outline-danger btn-sm'
                },
                {
                    extend: 'print',
                    text: '<i class="bi bi-printer"></i> Imprimir',
                    className: 'btn btn-outline-info btn-sm'
                }
            ],
            drawCallback: function () {
                // Re-ajustar columnas al cambiar de página o filtrar
                this.api().columns.adjust();
            }
        });

        // Vincular el buscador externo
        const $externalSearch = $('#buscarInventario');
        if ($externalSearch.length) {
            $externalSearch.off('keyup').on('keyup', function () {
                table.search(this.value).draw();
            });
        }

        const $clearBtn = $('#limpiarBusquedaInventario');
        if ($clearBtn.length) {
            $clearBtn.off('click').on('click', function () {
                $externalSearch.val('');
                table.search('').draw();
            });
        }
    });
});
