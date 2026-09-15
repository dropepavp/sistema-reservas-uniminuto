"""
Utilidades centralizadas para exportación de DataFrames a Excel y CSV.

Todos los blueprints que exportan datos deben importar de aquí para evitar
duplicar el patrón BytesIO → pd.ExcelWriter → send_file.

Uso típico:
    from utils.export_helpers import exportar_df_excel, exportar_df_csv

    if formato == 'excel':
        return exportar_df_excel(df, sheet_name='Profesores', prefix='profesores')
    elif formato == 'csv':
        return exportar_df_csv(df, prefix='profesores')
"""

import io
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd
from flask import send_file


def exportar_df_excel(
    df: pd.DataFrame,
    sheet_name: str,
    prefix: str,
    extra_sheets: Optional[List[Tuple[pd.DataFrame, str]]] = None,
) -> "flask.Response":
    """
    Serializa un DataFrame (y hojas opcionales) en un Excel en memoria
    y devuelve un objeto ``send_file`` listo para retornar desde una vista.

    Args:
        df:           DataFrame principal.
        sheet_name:   Nombre de la hoja principal.
        prefix:       Prefijo del nombre de archivo descargado (sin extensión).
        extra_sheets: Lista de tuplas (df_extra, nombre_hoja) para hojas
                      adicionales, p.ej. una hoja de resumen.

    Returns:
        Respuesta Flask con el archivo adjunto.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        if extra_sheets:
            for extra_df, extra_name in extra_sheets:
                extra_df.to_excel(writer, index=False, sheet_name=extra_name)
    output.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.xlsx"

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        download_name=filename,
        as_attachment=True,
    )


def exportar_df_csv(
    df: pd.DataFrame,
    prefix: str,
) -> "flask.Response":
    """
    Serializa un DataFrame como CSV UTF-8 con BOM (compatible con Excel)
    y devuelve un objeto ``send_file`` listo para retornar desde una vista.

    Args:
        df:     DataFrame a exportar.
        prefix: Prefijo del nombre de archivo descargado (sin extensión).

    Returns:
        Respuesta Flask con el archivo adjunto.
    """
    output = io.StringIO()
    df.to_csv(output, index=False, encoding="utf-8-sig")
    buffer = io.BytesIO(output.getvalue().encode("utf-8-sig"))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.csv"

    return send_file(
        buffer,
        mimetype="text/csv",
        download_name=filename,
        as_attachment=True,
    )
