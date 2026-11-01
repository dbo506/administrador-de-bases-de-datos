"""
Módulo para la Administración y Consulta de Auditoría en Oracle 21c XE.
Soporta:
1. Consulta y filtrado de la pista de auditoría unificada (UNIFIED_AUDIT_TRAIL).
2. Monitoreo de accesos, intentos fallidos (logins) y operaciones DDL/DML.
3. Gestión de políticas de auditoría unificada (AUDIT_UNIFIED_POLICIES, AUDIT/NOAUDIT).
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import oracledb
from modules.common import run_query, run_dml, flash


def get_audit_trail(conn: oracledb.Connection, limit: int = 100, user_filter: str = None, action_filter: str = None, only_failures: bool = False) -> pd.DataFrame:
    """
    Consulta registros de la vista UNIFIED_AUDIT_TRAIL o DBA_AUDIT_TRAIL como fallback.
    """
    conditions = ["1=1"]
    params = {}

    if user_filter and user_filter != "(Todos)":
        conditions.append("dbusername = :u_filter")
        params["u_filter"] = user_filter

    if action_filter and action_filter != "(Todas)":
        conditions.append("action_name = :a_filter")
        params["a_filter"] = action_filter

    if only_failures:
        conditions.append("return_code != 0")

    where_clause = " AND ".join(conditions)

    sql = f"""
    SELECT 
        TO_CHAR(event_timestamp, 'YYYY-MM-DD HH24:MI:SS') AS "FECHA_HORA",
        dbusername AS "USUARIO",
        action_name AS "ACCION",
        object_schema AS "ESQUEMA_OBJETO",
        object_name AS "OBJETO",
        return_code AS "CODIGO_RETORNO",
        CASE WHEN return_code = 0 THEN 'EXITOSO' ELSE 'FALLIDO (' || return_code || ')' END AS "ESTADO",
        client_program_name AS "PROGRAMA_CLIENTE",
        SUBSTR(sql_text, 1, 120) AS "SQL_EJECUTADO"
    FROM unified_audit_trail
    WHERE {where_clause}
    ORDER BY event_timestamp DESC
    FETCH FIRST {limit} ROWS ONLY
    """
    try:
        return run_query(conn, sql, params)
    except Exception:
        # Fallback a DBA_AUDIT_TRAIL si Unified Auditing no está configurado
        fallback_sql = f"""
        SELECT 
            TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS "FECHA_HORA",
            username AS "USUARIO",
            action_name AS "ACCION",
            owner AS "ESQUEMA_OBJETO",
            obj_name AS "OBJETO",
            returncode AS "CODIGO_RETORNO",
            CASE WHEN returncode = 0 THEN 'EXITOSO' ELSE 'FALLIDO (' || returncode || ')' END AS "ESTADO",
            os_username AS "USUARIO_SO"
        FROM dba_audit_trail
        ORDER BY timestamp DESC
        FETCH FIRST {limit} ROWS ONLY
        """
        return run_query(conn, fallback_sql)


def get_audit_policies(conn: oracledb.Connection) -> pd.DataFrame:
    """
    Retorna las políticas de auditoría unificada existentes y habilitadas.
    """
    sql = """
    SELECT 
        p.policy_name AS "POLITICA",
        p.audit_option_type AS "TIPO_OPCION",
        p.audit_option AS "OPCION_ACCION",
        p.object_schema AS "ESQUEMA",
        p.object_name AS "OBJETO",
        NVL(e.enabled_option, 'DISABLED') AS "ESTADO_HABILITADA",
        e.user_name AS "APLICADA_A_USUARIO",
        e.success AS "EN_EXITO",
        e.failure AS "EN_FALLO"
    FROM audit_unified_policies p
    LEFT JOIN audit_unified_enabled_policies e ON p.policy_name = e.policy_name
    WHERE p.policy_name NOT LIKE 'ORA_%'
    ORDER BY p.policy_name
    """
    try:
        df = run_query(conn, sql)
        if df.empty:
            # Si no hay personalizadas, mostrar las del sistema ORA_
            sql_all = """
            SELECT 
                p.policy_name AS "POLITICA",
                p.audit_option_type AS "TIPO_OPCION",
                p.audit_option AS "OPCION_ACCION",
                NVL(e.enabled_option, 'DISABLED') AS "ESTADO_HABILITADA"
            FROM audit_unified_policies p
            LEFT JOIN audit_unified_enabled_policies e ON p.policy_name = e.policy_name
            FETCH FIRST 30 ROWS ONLY
            """
            return run_query(conn, sql_all)
        return df
    except Exception:
        return pd.DataFrame()


def render_auditing(conn: oracledb.Connection):
    """
    Renderiza la interfaz de auditoría.
    """
    st.header("🛡️ Auditoría de la Base de Datos")
    st.caption("Inspección de eventos de seguridad, inicios de sesión, cambios estructurales (DDL) y políticas de auditoría.")

    tab_trail, tab_failed_logins, tab_policies, tab_create_policy = st.tabs([
        "📜 Registros de Auditoría",
        "🚨 Intentos Fallidos / Logins",
        "📋 Políticas de Auditoría",
        "⚙️ Crear / Habilitar Política"
    ])

    # 1. REGISTROS DE AUDITORÍA
    with tab_trail:
        st.subheader("Pista de Auditoría")

        # Filtros
        c_f1, c_f2, c_f3, c_f4 = st.columns(4)
        with c_f1:
            try:
                users_df = run_query(conn, "SELECT DISTINCT dbusername FROM unified_audit_trail WHERE dbusername IS NOT NULL FETCH FIRST 50 ROWS ONLY")
                user_list = ["(Todos)"] + users_df["DBUSERNAME"].tolist()
            except Exception:
                user_list = ["(Todos)"]
            sel_user = st.selectbox("Filtrar por Usuario", user_list)

        with c_f2:
            try:
                actions_df = run_query(conn, "SELECT DISTINCT action_name FROM unified_audit_trail WHERE action_name IS NOT NULL FETCH FIRST 50 ROWS ONLY")
                action_list = ["(Todas)"] + actions_df["ACTION_NAME"].tolist()
            except Exception:
                action_list = ["(Todas)"]
            sel_action = st.selectbox("Filtrar por Acción", action_list)

        with c_f3:
            only_errs = st.checkbox("Solo operaciones fallidas (Return Code != 0)", value=False)
        with c_f4:
            limit_rows = st.slider("Límite de registros", min_value=25, max_value=500, value=100, step=25)

        try:
            df_trail = get_audit_trail(conn, limit=limit_rows, user_filter=sel_user, action_filter=sel_action, only_failures=only_errs)
            
            # Gráfico de acciones
            if not df_trail.empty and "ACCION" in df_trail.columns:
                action_counts = df_trail["ACCION"].value_counts().reset_index()
                action_counts.columns = ["Acción", "Frecuencia"]
                fig_act = px.bar(action_counts.head(10), x="Acción", y="Frecuencia", color="Frecuencia", title="Top 10 Acciones Auditadas")
                fig_act.update_layout(height=280)
                st.plotly_chart(fig_act, use_container_width=True)

            st.dataframe(df_trail, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Error al consultar pista de auditoría: {e}")

    # 2. LOGINS FALLIDOS
    with tab_failed_logins:
        st.subheader("🚨 Intentos de Inicio de Sesión Fallidos")
        st.caption("Detección de accesos no autorizados o contraseñas inválidas (ORA-01017, ORA-28000, etc.).")

        try:
            sql_failed = """
            SELECT 
                TO_CHAR(event_timestamp, 'YYYY-MM-DD HH24:MI:SS') AS "FECHA_HORA",
                dbusername AS "USUARIO_INTENTADO",
                client_program_name AS "PROGRAMA",
                userhost AS "HOST_ORIGEN",
                return_code AS "CODIGO_ERROR",
                CASE 
                    WHEN return_code = 1017 THEN 'ORA-01017: Usuario o contraseña incorrectos'
                    WHEN return_code = 28000 THEN 'ORA-28000: Cuenta bloqueada'
                    ELSE 'Código: ' || return_code 
                END AS "DETALLE_ERROR"
            FROM unified_audit_trail
            WHERE action_name = 'LOGON' AND return_code != 0
            ORDER BY event_timestamp DESC
            FETCH FIRST 50 ROWS ONLY
            """
            df_failed = run_query(conn, sql_failed)
            if df_failed.empty:
                st.success("✅ No se registran intentos de login fallidos recientes.")
            else:
                st.dataframe(df_failed, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error al consultar logins fallidos: {e}")

    # 3. POLÍTICAS DE AUDITORÍA
    with tab_policies:
        st.subheader("Políticas de Auditoría Unificada")
        try:
            df_pol = get_audit_policies(conn)
            if df_pol.empty:
                st.info("No se encontraron políticas personalizadas.")
            else:
                st.dataframe(df_pol, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error al obtener políticas: {e}")

    # 4. CREAR Y HABILITAR POLÍTICA
    with tab_create_policy:
        st.subheader("Configurar Nueva Política de Auditoría")
        
        with st.form("form_create_policy"):
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                pol_name = st.text_input("Nombre de la Política", placeholder="POL_AUDITORIA_TABLAS").strip().upper()
                pol_actions = st.multiselect(
                    "Acciones a Auditar",
                    ["LOGON", "LOGOFF", "CREATE TABLE", "ALTER TABLE", "DROP TABLE", "CREATE USER", "DROP USER", "SELECT", "INSERT", "UPDATE", "DELETE"],
                    default=["CREATE TABLE", "ALTER TABLE", "DROP TABLE"]
                )
            with c_p2:
                apply_whenever = st.selectbox("Condición de Disparo", ["WHENEVER SUCCESSFUL", "WHENEVER NOT SUCCESSFUL", "SIEMPRE (Éxito y Fallo)"])
                auto_enable = st.checkbox("Habilitar de inmediato tras crearla", value=True)

            btn_create_pol = st.form_submit_button("Crear Política de Auditoría", use_container_width=True)

        if btn_create_pol:
            if not pol_name or not pol_actions:
                st.warning("Debe ingresar un nombre y seleccionar al menos una acción.")
            else:
                try:
                    actions_clause = ", ".join(pol_actions)
                    ddl_create_pol = f"CREATE AUDIT POLICY {pol_name} ACTIONS {actions_clause}"
                    run_dml(conn, ddl_create_pol)

                    if auto_enable:
                        enable_stmt = f"AUDIT POLICY {pol_name}"
                        if apply_whenever == "WHENEVER SUCCESSFUL":
                            enable_stmt += " WHENEVER SUCCESSFUL"
                        elif apply_whenever == "WHENEVER NOT SUCCESSFUL":
                            enable_stmt += " WHENEVER NOT SUCCESSFUL"
                        run_dml(conn, enable_stmt)

                    flash(f"Política **{pol_name}** creada y habilitada exitosamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al configurar política: {e}")

        st.divider()
        st.markdown("#### Deshabilitar / Eliminar Política")
        with st.form("form_drop_policy"):
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                pol_target = st.text_input("Nombre de la política a deshabilitar / eliminar").strip().upper()
            with c_d2:
                action_type = st.radio("Acción:", ["Deshabilitar (NOAUDIT)", "Eliminar Definitivamente (DROP)"])
            btn_manage_pol = st.form_submit_button("Ejecutar Acción")

        if btn_manage_pol and pol_target:
            try:
                if "Deshabilitar" in action_type:
                    run_dml(conn, f"NOAUDIT POLICY {pol_target}")
                    flash(f"Política {pol_target} deshabilitada.")
                else:
                    try:
                        run_dml(conn, f"NOAUDIT POLICY {pol_target}")
                    except Exception:
                        pass
                    run_dml(conn, f"DROP AUDIT POLICY {pol_target}")
                    flash(f"Política {pol_target} eliminada.")
                st.rerun()
            except Exception as e:
                st.error(f"Error en gestión de política: {e}")

