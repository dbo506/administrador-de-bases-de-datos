"""
Módulo para el Monitoreo del Performance de la Base de Datos Oracle 21c XE.
Incluye:
1. Memoria (SGA, PGA, Hit Ratios de Buffer Cache y Library Cache).
2. Sesiones activas, bloqueos (blocking locks) y terminación de sesiones (Kill Session).
3. Top SQL (consultas más costosas por CPU, tiempo transcurrido y lecturas).
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import oracledb
from modules.common import run_query, run_dml, flash, render_subtabs


def get_memory_metrics(conn: oracledb.Connection) -> dict:
    """
    Obtiene las estadísticas de memoria de SGA y PGA, así como los Hit Ratios.
    """
    metrics = {}
    
    # SGA
    df_sga = run_query(conn, "SELECT name, ROUND(bytes / 1024 / 1024, 2) AS mb FROM v$sgainfo")
    metrics["sga"] = df_sga

    # PGA
    df_pga = run_query(conn, "SELECT name, ROUND(value / 1024 / 1024, 2) AS mb FROM v$pgastat WHERE unit = 'bytes'")
    metrics["pga"] = df_pga

    # Buffer Cache Hit Ratio
    bchr_sql = """
    SELECT ROUND((1 - (pr.value / (cg.value + db.value))) * 100, 2) AS hit_ratio
    FROM v$sysstat pr, v$sysstat cg, v$sysstat db
    WHERE pr.name = 'physical reads'
      AND cg.name = 'consistent gets'
      AND db.name = 'db block gets'
      AND (cg.value + db.value) > 0
    """
    df_bchr = run_query(conn, bchr_sql)
    metrics["bchr"] = df_bchr.iloc[0, 0] if not df_bchr.empty else 100.0

    # Library Cache Hit Ratio
    lchr_sql = """
    SELECT ROUND((SUM(pins - reloads) / NULLIF(SUM(pins), 0)) * 100, 2) AS hit_ratio
    FROM v$librarycache
    """
    df_lchr = run_query(conn, lchr_sql)
    metrics["lchr"] = df_lchr.iloc[0, 0] if not df_lchr.empty and pd.notnull(df_lchr.iloc[0, 0]) else 100.0

    return metrics


def get_active_sessions(conn: oracledb.Connection) -> pd.DataFrame:
    """
    Retorna la lista de sesiones activas en el motor de base de datos.
    """
    sql = """
    SELECT 
        sid AS "SID",
        serial# AS "SERIAL",
        username AS "USUARIO",
        status AS "ESTADO",
        osuser AS "USUARIO_SO",
        machine AS "EQUIPO",
        program AS "PROGRAMA",
        sql_id AS "SQL_ID",
        wait_class AS "CLASE_ESPERA",
        event AS "EVENTO",
        seconds_in_wait AS "SEGUNDOS_ESPERA",
        blocking_session AS "BLOQUEADO_POR"
    FROM v$session
    WHERE type != 'BACKGROUND'
    ORDER BY status, seconds_in_wait DESC
    """
    return run_query(conn, sql)


def get_blocking_locks(conn: oracledb.Connection) -> pd.DataFrame:
    """
    Identifica sesiones que están bloqueando a otras sesiones.
    """
    sql = """
    SELECT 
        b.sid AS "SID_BLOQUEADOR",
        b.serial# AS "SERIAL_BLOQUEADOR",
        b.username AS "USUARIO_BLOQUEADOR",
        b.machine AS "EQUIPO_BLOQUEADOR",
        w.sid AS "SID_BLOQUEADO",
        w.serial# AS "SERIAL_BLOQUEADO",
        w.username AS "USUARIO_BLOQUEADO",
        w.event AS "EVENTO_ESPERA",
        w.seconds_in_wait AS "TIEMPO_ESPERA_S"
    FROM v$session b
    JOIN v$session w ON b.sid = w.blocking_session
    ORDER BY w.seconds_in_wait DESC
    """
    return run_query(conn, sql)


def get_top_sql(conn: oracledb.Connection, sort_by: str = "CPU_TIME", limit: int = 15) -> pd.DataFrame:
    """
    Obtiene las sentencias SQL más consumidoras de recursos.
    """
    order_column = {
        "CPU_TIME": "cpu_time",
        "ELAPSED_TIME": "elapsed_time",
        "BUFFER_GETS": "buffer_gets",
        "DISK_READS": "disk_reads",
        "EXECUTIONS": "executions"
    }.get(sort_by, "cpu_time")

    sql = f"""
    SELECT 
        sql_id AS "SQL_ID",
        parsing_schema_name AS "ESQUEMA",
        executions AS "EJECUCIONES",
        ROUND(cpu_time / 1000000, 2) AS "CPU_TOTAL_S",
        ROUND(elapsed_time / 1000000, 2) AS "TIEMPO_TOTAL_S",
        ROUND((elapsed_time / 1000000) / NULLIF(executions, 0), 4) AS "TIEMPO_PROM_S",
        buffer_gets AS "LECTURAS_BUFFER",
        disk_reads AS "LECTURAS_DISCO",
        SUBSTR(sql_text, 1, 150) AS "SQL_TEXT"
    FROM v$sqlarea
    WHERE parsing_schema_name NOT IN ('SYS', 'SYSTEM')
       OR parsing_schema_name IS NULL
    ORDER BY {order_column} DESC
    FETCH FIRST {limit} ROWS ONLY
    """
    return run_query(conn, sql)


def render_performance(conn: oracledb.Connection):
    """
    Renderiza la vista y monitores de performance de Oracle.
    """
    st.header("📊 Performance y Monitoreo de la Base de Datos")
    st.caption("Salud del motor, distribución de memoria, sesiones activas, bloqueos y Top SQL.")

    active_tab = render_subtabs([
        "🧠 Memoria y Eficiencia (SGA/PGA)",
        "👥 Sesiones de Usuarios",
        "🔒 Bloqueos (Lock Tree)",
        "🔥 Consultas Top SQL"
    ], key="perf_active_subtab")

    # 1. MEMORIA Y HIT RATIOS
    if active_tab == "🧠 Memoria y Eficiencia (SGA/PGA)":
        st.subheader("Eficiencia de Cache y Memoria")
        try:
            mem = get_memory_metrics(conn)
            
            c_gauge1, c_gauge2 = st.columns(2)
            with c_gauge1:
                bchr = mem["bchr"]
                fig_bchr = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=bchr,
                    title={'text': "Buffer Cache Hit Ratio"},
                    number={'suffix': "%"},
                    gauge={
                        'axis': {'range': [0, 100]},
                        'bar': {'color': "#2ecc71" if bchr >= 90 else "#e74c3c"},
                        'steps': [
                            {'range': [0, 70], 'color': "#fadbd8"},
                            {'range': [70, 90], 'color': "#fdebd0"},
                            {'range': [90, 100], 'color': "#d4efdf"}
                        ],
                        'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': 90}
                    }
                ))
                fig_bchr.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_bchr, use_container_width=True)
                st.caption("Valores > 90% indican que la gran mayoría de lecturas se resuelven en RAM sin ir al disco.")

            with c_gauge2:
                lchr = mem["lchr"]
                fig_lchr = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=lchr,
                    title={'text': "Library Cache Hit Ratio"},
                    number={'suffix': "%"},
                    gauge={
                        'axis': {'range': [0, 100]},
                        'bar': {'color': "#3498db" if lchr >= 95 else "#e67e22"},
                        'steps': [
                            {'range': [0, 85], 'color': "#fadbd8"},
                            {'range': [85, 95], 'color': "#fdebd0"},
                            {'range': [95, 100], 'color': "#d6eaf8"}
                        ],
                        'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': 95}
                    }
                ))
                fig_lchr.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_lchr, use_container_width=True)
                st.caption("Valores > 95% indican una alta reutilización de cursores SQL en la Shared Pool.")

            st.divider()
            c_mem1, c_mem2 = st.columns(2)
            with c_mem1:
                st.markdown("#### Componentes de la SGA (MB)")
                df_sga = mem["sga"]
                df_sga_filtered = df_sga[df_sga["MB"] > 0]
                fig_sga = px.pie(df_sga_filtered, values="MB", names="NAME", title="Distribución de la SGA", hole=0.35)
                fig_sga.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_sga, use_container_width=True)
                st.dataframe(df_sga, use_container_width=True, hide_index=True)

            with c_mem2:
                st.markdown("#### Estadísticas de la PGA (MB)")
                df_pga = mem["pga"]
                st.dataframe(df_pga, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error al obtener métricas de memoria: {e}")

    # 2. SESIONES DE USUARIOS
    elif active_tab == "👥 Sesiones de Usuarios":
        st.subheader("Sesiones Activas y Conectadas")
        col_ref_s, col_kill = st.columns([1, 4])
        with col_ref_s:
            if st.button("🔄 Refrescar", key="ref_sess"):
                st.rerun()

        try:
            df_sess = get_active_sessions(conn)
            
            # Resumen
            total_s = len(df_sess)
            active_s = len(df_sess[df_sess["ESTADO"] == "ACTIVE"])
            inactive_s = len(df_sess[df_sess["ESTADO"] == "INACTIVE"])
            
            s1, s2, s3 = st.columns(3)
            s1.metric("Sesiones de Usuario", total_s)
            s2.metric("Sesiones Activas", active_s)
            s3.metric("Sesiones Inactivas", inactive_s)

            st.dataframe(df_sess, use_container_width=True, hide_index=True)

            # Terminación de sesión
            st.divider()
            st.markdown("#### 🚫 Terminar Sesión (Kill Session)")
            with st.form("form_kill_session"):
                c_k1, c_k2, c_k3 = st.columns([2, 2, 2])
                with c_k1:
                    kill_sid = st.number_input("SID", min_value=1, step=1)
                with c_k2:
                    kill_serial = st.number_input("SERIAL#", min_value=1, step=1)
                with c_k3:
                    immediate = st.checkbox("Modo IMMEDIATE", value=True)
                btn_kill = st.form_submit_button("Terminar Sesión", type="primary")

            if btn_kill:
                try:
                    stmt_kill = f"ALTER SYSTEM KILL SESSION '{kill_sid},{kill_serial}'"
                    if immediate:
                        stmt_kill += " IMMEDIATE"
                    run_dml(conn, stmt_kill)
                    flash(f"Sesión {kill_sid},{kill_serial} terminada correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al terminar sesión: {e}")

        except Exception as e:
            st.error(f"Error al consultar sesiones: {e}")

    # 3. BLOQUEOS
    elif active_tab == "🔒 Bloqueos (Lock Tree)":
        st.subheader("Detección de Bloqueos en Tiempo Real (Lock Tree)")
        st.caption("Identifica sesiones en conflicto donde un usuario bloquea recursos que otros están esperando.")
        try:
            df_locks = get_blocking_locks(conn)
            if df_locks.empty:
                st.success("✅ No se detectaron bloqueos activos entre sesiones.")
            else:
                st.warning(f"⚠️ Se detectaron {len(df_locks)} relaciones de bloqueo.")
                st.dataframe(df_locks, use_container_width=True, hide_index=True)

                st.markdown("##### Acciones de Desbloqueo Rápido")
                blocking_sids = df_locks["SID_BLOQUEADOR"].unique().tolist()
                sel_sid_to_kill = st.selectbox("Seleccione SID bloqueador a terminar:", blocking_sids)
                
                # Obtener serial correspondiente
                sel_row = df_locks[df_locks["SID_BLOQUEADOR"] == sel_sid_to_kill].iloc[0]
                sel_serial_to_kill = sel_row["SERIAL_BLOQUEADOR"]

                if st.button(f"🚨 Terminar Sesión Bloqueadora (SID {sel_sid_to_kill}, SERIAL {sel_serial_to_kill})", type="primary"):
                    try:
                        run_dml(conn, f"ALTER SYSTEM KILL SESSION '{sel_sid_to_kill},{sel_serial_to_kill}' IMMEDIATE")
                        flash(f"Sesión bloqueadora {sel_sid_to_kill} terminada.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al desbloquear: {e}")
        except Exception as e:
            st.error(f"Error al verificar bloqueos: {e}")

    # 4. TOP SQL
    elif active_tab == "🔥 Consultas Top SQL":
        st.subheader("Top Consultas SQL Más Costosas")
        c_crit1, c_crit2 = st.columns([2, 1])
        with c_crit1:
            sort_criterion = st.selectbox(
                "Criterio de Ordenamiento:",
                ["CPU_TIME", "ELAPSED_TIME", "BUFFER_GETS", "DISK_READS", "EXECUTIONS"],
                format_func=lambda x: {
                    "CPU_TIME": "Tiempo de CPU (Consumo de procesador)",
                    "ELAPSED_TIME": "Tiempo Total Transcurrido (Duración)",
                    "BUFFER_GETS": "Lecturas Lógicas de Buffer",
                    "DISK_READS": "Lecturas Físicas de Disco",
                    "EXECUTIONS": "Número de Ejecuciones"
                }[x]
            )
        with c_crit2:
            top_limit = st.slider("Cantidad de registros:", min_value=5, max_value=50, value=15, step=5)

        try:
            df_top = get_top_sql(conn, sort_by=sort_criterion, limit=top_limit)
            if df_top.empty:
                st.info("No se encontraron registros de consultas en v$sqlarea.")
            else:
                st.dataframe(df_top, use_container_width=True, hide_index=True)

                st.markdown("##### Visualización Comparativa")
                col_chart = "CPU_TOTAL_S" if sort_criterion == "CPU_TIME" else (
                    "TIEMPO_TOTAL_S" if sort_criterion == "ELAPSED_TIME" else (
                        "LECTURAS_BUFFER" if sort_criterion == "BUFFER_GETS" else (
                            "LECTURAS_DISCO" if sort_criterion == "DISK_READS" else "EJECUCIONES"
                        )
                    )
                )
                fig_top = px.bar(
                    df_top,
                    x="SQL_ID",
                    y=col_chart,
                    hover_data=["ESQUEMA", "EJECUCIONES", "SQL_TEXT"],
                    title=f"Top SQL por {sort_criterion}",
                    color=col_chart,
                    color_continuous_scale="Viridis"
                )
                fig_top.update_layout(height=350)
                st.plotly_chart(fig_top, use_container_width=True)

        except Exception as e:
            st.error(f"Error al obtener Top SQL: {e}")
