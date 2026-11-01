"""
Funciones auxiliares y de ejecución de consultas para la aplicación de administración de Oracle.
"""

from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import oracledb
import streamlit as st


def flash(message: str, kind: str = "success", code: Optional[str] = None) -> None:
    """
    Guarda un mensaje para mostrarlo tras st.rerun() (si no, el rerun lo borra antes de verse).
    """
    st.session_state["_flash"] = (kind, message, code)


def show_flash() -> None:
    """
    Muestra y descarta el mensaje pendiente guardado con flash().
    """
    pending = st.session_state.pop("_flash", None)
    if pending:
        kind, message, code = pending
        getattr(st, kind)(message)
        if code:
            st.code(code, language="sql")


def run_query(connection: oracledb.Connection, query: str, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Ejecuta una consulta SELECT y retorna el resultado como un DataFrame de pandas.
    """
    with connection.cursor() as cursor:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if cursor.description is None:
            return pd.DataFrame()
            
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=columns)


def run_dml(connection: oracledb.Connection, statement: str, params: Optional[Dict[str, Any]] = None) -> None:
    """
    Ejecuta una sentencia DDL o DML (INSERT, UPDATE, DELETE, ALTER, CREATE, DROP).
    """
    with connection.cursor() as cursor:
        if params:
            cursor.execute(statement, params)
        else:
            cursor.execute(statement)
        connection.commit()


def get_oracle_version(connection: oracledb.Connection) -> str:
    """
    Retorna la versión activa de Oracle Database.
    """
    df = run_query(connection, "SELECT banner_full FROM v$version WHERE ROWNUM = 1")
    if not df.empty:
        return str(df.iloc[0, 0])
    return "Oracle Database"

