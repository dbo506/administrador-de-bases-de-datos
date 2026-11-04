"""
Módulo para el Tuning de Consultas en Oracle 21c XE.
Incluye:
1. Planes de ejecución (EXPLAIN PLAN y DBMS_XPLAN).
2. Recolección y consulta de estadísticas (DBMS_STATS).
3. Administración y monitoreo de índices (B-Tree, Unique, Bitmap, Rebuild, Drop).
"""

import time
import uuid
import streamlit as st
import pandas as pd
import oracledb
from modules.common import run_query, run_dml, flash, render_subtabs


def get_schemas_list(conn: oracledb.Connection) -> list:
    """
    Retorna la lista de esquemas/usuarios válidos en la base de datos.
    """
    df = run_query(conn, "SELECT username FROM all_users WHERE oracle_maintained = 'N' OR username IN ('SYSTEM', 'HR', 'SH') ORDER BY username")
    if df.empty:
        df = run_query(conn, "SELECT username FROM all_users ORDER BY username")
    return df["USERNAME"].tolist()


def get_tables_list(conn: oracledb.Connection, owner: str) -> list:
    """
    Retorna las tablas pertenecientes al esquema dado.
    """
    df = run_query(conn, "SELECT table_name FROM all_tables WHERE owner = :owner ORDER BY table_name", {"owner": owner})
    return df["TABLE_NAME"].tolist() if not df.empty else []


def get_columns_list(conn: oracledb.Connection, owner: str, table_name: str) -> list:
    """
    Retorna las columnas de una tabla dada.
    """
    df = run_query(
        conn,
        "SELECT column_name, data_type FROM all_tab_columns WHERE owner = :owner AND table_name = :tname ORDER BY column_id",
        {"owner": owner, "tname": table_name}
    )
    return df["COLUMN_NAME"].tolist() if not df.empty else []


def render_tuning(conn: oracledb.Connection):
    """
    Renderiza la interfaz para tuning de consultas, estadísticas e índices.
    """
    st.header("⚡ Tuning y Optimización de Consultas")
    st.caption("Análisis de planes de ejecución, recolección de estadísticas de CBO y administración de índices.")

    active_tab = render_subtabs([
        "🔍 Plan de Ejecución (Explain Plan)",
        "📈 Estadísticas (DBMS_STATS)",
        "🗂️ Gestión de Índices"
    ], key="tuning_active_subtab")

    # 1. EXPLAIN PLAN
    if active_tab == "🔍 Plan de Ejecución (Explain Plan)":
        st.subheader("Generador de Planes de Ejecución")
        st.markdown(
            "Ingrese una consulta `SELECT`, `UPDATE` o `DELETE` para evaluar el plan de ejecución "
            "del optimizador basado en costos (CBO), estimación de cardinalidad y métodos de acceso."
        )

        sample_sql = "SELECT table_name, num_rows FROM all_tables WHERE num_rows > 100 ORDER BY num_rows DESC"
        query_input = st.text_area("Sentencia SQL a analizar:", value=sample_sql, height=120)

        plan_format = st.selectbox(
            "Formato de salida de DBMS_XPLAN",
            ["TYPICAL", "ALL", "BASIC", "ADVANCED"],
            index=0
        )

        if st.button("🚀 Generar Explain Plan", type="primary"):
            if not query_input.strip():
                st.warning("Ingrese una consulta SQL válida.")
            else:
                stmt_id = f"ST_{uuid.uuid4().hex[:10].upper()}"
                try:
                    with st.spinner("Generando plan de ejecución con el optimizador..."):
                        # Asegurarse de que no haya punto y coma al final para EXPLAIN PLAN
                        clean_sql = query_input.strip().rstrip(";")
                        explain_stmt = f"EXPLAIN PLAN SET STATEMENT_ID = '{stmt_id}' FOR {clean_sql}"
                        run_dml(conn, explain_stmt)

                        # Obtener salida formateada con DBMS_XPLAN
                        plan_df = run_query(
                            conn,
                            f"SELECT plan_table_output FROM TABLE(DBMS_XPLAN.DISPLAY('PLAN_TABLE', '{stmt_id}', '{plan_format}'))"
                        )

                        # Obtener detalle estructurado de la tabla PLAN_TABLE
                        detail_sql = f"""
                        SELECT 
                            id AS "ID",
                            parent_id AS "PARENT_ID",
                            LPAD(' ', 2 * (level - 1)) || operation || ' ' || NVL(options, '') AS "OPERACION",
                            object_owner AS "PROPIETARIO",
                            object_name AS "OBJETO",
                            cost AS "COSTO",
                            cardinality AS "CARDINALIDAD",
                            bytes AS "BYTES",
                            time AS "TIEMPO_EST_S",
                            access_predicates AS "PREDICADO_ACCESO",
                            filter_predicates AS "PREDICADO_FILTRO"
                        FROM plan_table
                        START WITH statement_id = '{stmt_id}' AND id = 0
                        CONNECT BY PRIOR id = parent_id AND statement_id = '{stmt_id}'
                        ORDER SIBLINGS BY id
                        """
                        detail_df = run_query(conn, detail_sql)

                    st.success("¡Plan de ejecución generado con éxito!")

                    # Vista tabular estructurada
                    st.markdown("#### Operaciones y Costos Detallados")
                    if not detail_df.empty:
                        st.dataframe(detail_df, use_container_width=True, hide_index=True)

                    # Vista oficial de DBMS_XPLAN
                    st.markdown("#### Salida Completa DBMS_XPLAN.DISPLAY")
                    if not plan_df.empty:
                        raw_text = "\n".join(plan_df["PLAN_TABLE_OUTPUT"].astype(str).tolist())
                        st.code(raw_text, language="text")

                    # Limpieza del plan temporal
                    try:
                        run_dml(conn, f"DELETE FROM plan_table WHERE statement_id = '{stmt_id}'")
                    except Exception:
                        pass

                except Exception as e:
                    st.error(f"Error al generar el plan de ejecución: {e}")

    # 2. ESTADÍSTICAS (DBMS_STATS)
    elif active_tab == "📈 Estadísticas (DBMS_STATS)":
        st.subheader("Estadísticas del Optimizador (DBMS_STATS)")
        st.caption("Visualice y refresque las estadísticas para garantizar que el optimizador elija las mejores rutas de acceso.")

        schemas = get_schemas_list(conn)
        sel_schema = st.selectbox("Esquema / Propietario", schemas, key="stats_schema")

        col_st1, col_st2 = st.columns([3, 2])

        with col_st1:
            st.markdown(f"#### Estadísticas de Tablas en `{sel_schema}`")
            try:
                stats_sql = """
                SELECT 
                    table_name AS "TABLA",
                    num_rows AS "FILAS",
                    blocks AS "BLOQUES",
                    avg_row_len AS "LONG_PROM_FILA",
                    TO_CHAR(last_analyzed, 'YYYY-MM-DD HH24:MI:SS') AS "ULTIMO_ANALISIS",
                    stale_stats AS "DESACTUALIZADA",
                    sample_size AS "MUESTRA_FILAS"
                FROM all_tab_statistics
                WHERE owner = :owner AND object_type = 'TABLE'
                ORDER BY table_name
                """
                df_stats = run_query(conn, stats_sql, {"owner": sel_schema})
                if df_stats.empty:
                    st.info(f"No se encontraron tablas para el esquema {sel_schema}.")
                else:
                    st.dataframe(df_stats, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Error al consultar estadísticas: {e}")

        with col_st2:
            st.markdown("#### ⚡ Recolectar Estadísticas")
            target_type = st.radio("Ámbito:", ["Tabla Individual", "Esquema Completo"], horizontal=True)

            if target_type == "Tabla Individual":
                tables = get_tables_list(conn, sel_schema)
                sel_table = st.selectbox("Tabla objetivo:", tables if tables else ["(Sin tablas)"])
                cascade_idx = st.checkbox("Analizar también Índices (CASCADE => TRUE)", value=True)

                if st.button("Recolectar para Tabla", type="primary", disabled=not bool(tables)):
                    try:
                        with st.spinner(f"Analizando estadísticas para {sel_schema}.{sel_table}..."):
                            plsql = """
                            BEGIN
                                DBMS_STATS.GATHER_TABLE_STATS(
                                    ownname          => :ownname,
                                    tabname          => :tabname,
                                    estimate_percent => DBMS_STATS.AUTO_SAMPLE_SIZE,
                                    cascade          => :cascade_flag
                                );
                            END;
                            """
                            with conn.cursor() as cur:
                                cur.execute(plsql, {
                                    "ownname": sel_schema,
                                    "tabname": sel_table,
                                    "cascade_flag": cascade_idx
                                })
                        flash(f"Estadísticas recolectadas para {sel_schema}.{sel_table}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al recolectar estadísticas de tabla: {e}")

            else:
                st.info(f"Se actualizarán todas las tablas e índices del esquema **{sel_schema}**.")
                if st.button("Recolectar para Esquema Completo", type="primary"):
                    try:
                        with st.spinner(f"Analizando todo el esquema {sel_schema}..."):
                            plsql = """
                            BEGIN
                                DBMS_STATS.GATHER_SCHEMA_STATS(
                                    ownname          => :ownname,
                                    estimate_percent => DBMS_STATS.AUTO_SAMPLE_SIZE,
                                    cascade          => TRUE
                                );
                            END;
                            """
                            with conn.cursor() as cur:
                                cur.execute(plsql, {"ownname": sel_schema})
                        flash(f"Estadísticas completas del esquema {sel_schema} actualizadas.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al recolectar estadísticas de esquema: {e}")

    # 3. GESTIÓN DE ÍNDICES
    elif active_tab == "🗂️ Gestión de Índices":
        st.subheader("Administración de Índices")
        st.caption("Cree, monitoree, reconstruya o elimine índices para acelerar búsquedas y optimizar consultas.")

        schemas = get_schemas_list(conn)
        idx_schema = st.selectbox("Esquema:", schemas, key="idx_schema_sel")
        idx_tables = get_tables_list(conn, idx_schema)

        active_idx_tab = render_subtabs([
            "📋 Lista de Índices",
            "➕ Crear Índice",
            "🛠️ Reconstruir / Eliminar"
        ], key="idx_active_subtab")

        if active_idx_tab == "📋 Lista de Índices":
            try:
                idx_sql = """
                SELECT 
                    i.index_name AS "INDICE",
                    i.table_name AS "TABLA",
                    i.index_type AS "TIPO",
                    i.uniqueness AS "UNICIDAD",
                    i.status AS "ESTADO",
                    i.tablespace_name AS "TABLESPACE",
                    i.blevel AS "NIVEL_ARBOL",
                    i.leaf_blocks AS "BLOQUES_HOJA",
                    i.distinct_keys AS "CLAVES_DISTINTAS",
                    LISTAGG(c.column_name, ', ') WITHIN GROUP (ORDER BY c.column_position) AS "COLUMNAS"
                FROM all_indexes i
                JOIN all_ind_columns c 
                    ON i.owner = c.index_owner AND i.index_name = c.index_name
                WHERE i.owner = :owner
                GROUP BY 
                    i.index_name, i.table_name, i.index_type, i.uniqueness, 
                    i.status, i.tablespace_name, i.blevel, i.leaf_blocks, i.distinct_keys
                ORDER BY i.table_name, i.index_name
                """
                df_indices = run_query(conn, idx_sql, {"owner": idx_schema})
                if df_indices.empty:
                    st.info(f"No hay índices registrados para el esquema {idx_schema}.")
                else:
                    st.dataframe(df_indices, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Error al consultar índices: {e}")

        elif active_idx_tab == "➕ Crear Índice":
            st.markdown("#### Crear Nuevo Índice")
            with st.form("form_create_index"):
                c_i1, c_i2 = st.columns(2)
                with c_i1:
                    sel_tab_idx = st.selectbox("Tabla Destino", idx_tables if idx_tables else [""])
                    idx_type_choice = st.selectbox("Tipo de Índice", ["B-Tree Estándar (NORMAL)", "Único (UNIQUE)", "Bitmap (BITMAP)"])
                    new_idx_name = st.text_input("Nombre del Índice", placeholder="IDX_EMPLEADOS_SALARIO").strip().upper()
                with c_i2:
                    col_options = get_columns_list(conn, idx_schema, sel_tab_idx) if sel_tab_idx else []
                    sel_columns = st.multiselect("Columnas a Indexar (en orden)", col_options)
                    
                    # Tablespaces disponibles
                    ts_df = run_query(conn, "SELECT tablespace_name FROM dba_tablespaces WHERE contents = 'PERMANENT'")
                    ts_list = ts_df["TABLESPACE_NAME"].tolist() if not ts_df.empty else ["USERS"]
                    sel_idx_ts = st.selectbox("Tablespace Almacén", ts_list)

                btn_create_idx = st.form_submit_button("Crear Índice", use_container_width=True)

            if btn_create_idx:
                if not new_idx_name or not sel_tab_idx or not sel_columns:
                    st.warning("Debe especificar nombre del índice, tabla y al menos una columna.")
                else:
                    try:
                        type_str = ""
                        if "UNIQUE" in idx_type_choice:
                            type_str = "UNIQUE"
                        elif "BITMAP" in idx_type_choice:
                            type_str = "BITMAP"

                        cols_str = ", ".join(sel_columns)
                        ddl_idx = f"CREATE {type_str} INDEX {idx_schema}.{new_idx_name} ON {idx_schema}.{sel_tab_idx} ({cols_str}) TABLESPACE {sel_idx_ts}"
                        run_dml(conn, ddl_idx)
                        flash(f"Índice **{new_idx_name}** creado con éxito.", code=ddl_idx)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear índice: {e}")

        elif active_idx_tab == "🛠️ Reconstruir / Eliminar":
            st.markdown("#### Reconstrucción y Eliminación de Índices")
            try:
                indexes_df = run_query(conn, "SELECT index_name, table_name, status FROM all_indexes WHERE owner = :owner ORDER BY index_name", {"owner": idx_schema})
                if indexes_df.empty:
                    st.info("No hay índices en este esquema.")
                else:
                    idx_choice = st.selectbox("Seleccione el Índice:", indexes_df["INDEX_NAME"].tolist())
                    
                    c_act1, c_act2 = st.columns(2)
                    with c_act1:
                        st.markdown("**Reconstruir Índice (`REBUILD`)**")
                        st.caption("Útil para desfragmentar y volver a balancear el árbol B del índice.")
                        online_rb = st.checkbox("Reconstrucción ONLINE", value=True)
                        if st.button("🔨 Reconstruir Índice", key="btn_rebuild"):
                            try:
                                ddl_rb = f"ALTER INDEX {idx_schema}.{idx_choice} REBUILD"
                                if online_rb:
                                    ddl_rb += " ONLINE"
                                run_dml(conn, ddl_rb)
                                flash(f"Índice {idx_choice} reconstruido exitosamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al reconstruir índice: {e}")

                    with c_act2:
                        st.markdown("**Eliminar Índice (`DROP`)**")
                        st.caption("Elimina el índice de forma definitiva.")
                        if st.button("🗑️ Eliminar Índice", type="primary", key="btn_drop_idx"):
                            try:
                                ddl_drop = f"DROP INDEX {idx_schema}.{idx_choice}"
                                run_dml(conn, ddl_drop)
                                flash(f"Índice {idx_choice} eliminado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al eliminar índice: {e}")
            except Exception as e:
                st.error(f"Error en acciones de índice: {e}")
