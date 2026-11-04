"""
Funciones auxiliares y de ejecución de consultas para la aplicación de administración de Oracle.
"""

from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import oracledb
import streamlit as st


def flash(message: str, kind: str = "success", code: Optional[str] = None) -> None:
    """
    Guarda un mensaje para mostrarlo tras st.rerun() (evita que el rerun lo borre).
    """
    st.session_state["_flash"] = (kind, message, code)


def show_flash() -> None:
    """
    Muestra y descarta el mensaje pendiente guardado con flash().
    Genera una alerta altamente visible con bordes acentuados, iconos y un toast emergente.
    """
    pending = st.session_state.pop("_flash", None)
    if pending:
        kind, message, code = pending
        
        icons = {
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️"
        }
        titles = {
            "success": "Operación Exitosa",
            "error": "Error en la Operación",
            "warning": "Advertencia",
            "info": "Información"
        }
        border_colors = {
            "success": "#10b981",
            "error": "#ef4444",
            "warning": "#f59e0b",
            "info": "#3b82f6"
        }
        bg_colors = {
            "success": "#ecfdf5",
            "error": "#fef2f2",
            "warning": "#fffbeb",
            "info": "#eff6ff"
        }
        text_colors = {
            "success": "#065f46",
            "error": "#991b1b",
            "warning": "#92400e",
            "info": "#1e40af"
        }

        icon = icons.get(kind, "📢")
        title = titles.get(kind, "Notificación")
        border = border_colors.get(kind, "#3b82f6")
        bg = bg_colors.get(kind, "#eff6ff")
        text_color = text_colors.get(kind, "#1e40af")

        # Disparar también un toast en la esquina
        try:
            st.toast(f"{icon} {message}")
        except Exception:
            pass

        # Banner de alta visibilidad
        st.markdown(
            f"""
            <div style="
                background-color: {bg};
                border: 2px solid {border};
                border-left: 9px solid {border};
                border-radius: 8px;
                padding: 16px 20px;
                margin-top: 10px;
                margin-bottom: 22px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.12), 0 2px 4px -1px rgba(0, 0, 0, 0.08);
            ">
                <div style="display: flex; align-items: flex-start; gap: 14px;">
                    <span style="font-size: 1.8rem; line-height: 1;">{icon}</span>
                    <div style="flex: 1;">
                        <div style="font-size: 1.15rem; font-weight: 700; color: {text_color}; margin-bottom: 3px;">
                            {title}
                        </div>
                        <div style="font-size: 1.02rem; font-weight: 500; color: {text_color}; line-height: 1.4;">
                            {message}
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if code:
            st.code(code, language="sql")


def render_subtabs(options: List[str], key: str) -> str:
    """
    Renderiza pestañas de navegación horizontal que conservan la selección del usuario
    incluso tras st.rerun(), evitando que el usuario sea devuelto a la primera pestaña.
    """
    if key not in st.session_state or st.session_state[key] not in options:
        st.session_state[key] = options[0]

    try:
        selected = st.segmented_control(
            label="Subpestañas",
            options=options,
            default=st.session_state.get(key, options[0]),
            key=key,
            selection_mode="single",
            required=True,
            label_visibility="collapsed"
        )
    except Exception:
        selected = st.radio(
            label="Subpestañas",
            options=options,
            key=key,
            horizontal=True,
            label_visibility="collapsed"
        )

    if not selected:
        selected = options[0]

    st.markdown("<div style='margin-bottom: 0.9rem;'></div>", unsafe_allow_html=True)
    return selected


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
        rows = [tuple(v.read() if isinstance(v, oracledb.LOB) else v for v in row) for row in cursor.fetchall()]
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


def get_user_tablespaces(connection: oracledb.Connection) -> Tuple[List[str], int]:
    """
    Retorna los tablespaces permanentes sin SYSTEM ni SYSAUX y la posición del
    tablespace permanente por defecto de la base de datos dentro de esa lista.
    """
    df = run_query(
        connection,
        "SELECT tablespace_name FROM dba_tablespaces "
        "WHERE contents = 'PERMANENT' AND tablespace_name NOT IN ('SYSTEM', 'SYSAUX') "
        "ORDER BY tablespace_name",
    )
    names = df["TABLESPACE_NAME"].tolist() if not df.empty else ["USERS"]
    default_df = run_query(
        connection,
        "SELECT property_value FROM database_properties WHERE property_name = 'DEFAULT_PERMANENT_TABLESPACE'",
    )
    default_name = default_df.iloc[0, 0] if not default_df.empty else "USERS"
    return names, names.index(default_name) if default_name in names else 0


def get_oracle_version(connection: oracledb.Connection) -> str:
    """
    Retorna la versión activa de Oracle Database.
    """
    df = run_query(connection, "SELECT banner_full FROM v$version WHERE ROWNUM = 1")
    if not df.empty:
        return str(df.iloc[0, 0])
    return "Oracle Database"
