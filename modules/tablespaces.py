"""
Módulo para la administración de Tablespaces y Datafiles en Oracle 21c XE.
Permite listar, crear, modificar, redimensionar datafiles, cambiar estado y eliminar tablespaces.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import oracledb
from modules.common import run_query, run_dml


def get_tablespaces_metrics(conn: oracledb.Connection) -> pd.DataFrame:
    """
    Obtiene métricas completas de uso y capacidad para tablespaces permanentes, undo y temporales.
    """
    sql = """
    WITH df_stats AS (
        SELECT 
            tablespace_name,
            ROUND(SUM(bytes) / 1024 / 1024, 2) AS total_mb,
            ROUND(SUM(CASE WHEN autoextensible = 'YES' THEN maxbytes ELSE bytes END) / 1024 / 1024, 2) AS max_mb,
            MAX(autoextensible) AS autoextensible
        FROM dba_data_files
        GROUP BY tablespace_name
        UNION ALL
        SELECT 
            tablespace_name,
            ROUND(SUM(bytes) / 1024 / 1024, 2) AS total_mb,
            ROUND(SUM(CASE WHEN autoextensible = 'YES' THEN maxbytes ELSE bytes END) / 1024 / 1024, 2) AS max_mb,
            MAX(autoextensible) AS autoextensible
        FROM dba_temp_files
        GROUP BY tablespace_name
    ),
    free_stats AS (
        SELECT 
            tablespace_name,
            ROUND(SUM(bytes) / 1024 / 1024, 2) AS free_mb
        FROM dba_free_space
        GROUP BY tablespace_name
        UNION ALL
        SELECT 
            tf.tablespace_name,
            ROUND((SUM(tf.bytes) - NVL(SUM(tu.blocks * dt.block_size), 0)) / 1024 / 1024, 2) AS free_mb
        FROM dba_temp_files tf
        JOIN dba_tablespaces dt ON tf.tablespace_name = dt.tablespace_name
        LEFT JOIN gv$temp_extent_pool tu ON tf.tablespace_name = tu.tablespace_name
        GROUP BY tf.tablespace_name
    )
    SELECT 
        t.tablespace_name AS "TABLESPACE",
        t.contents AS "TIPO",
        t.status AS "ESTADO",
        NVL(d.total_mb, 0) AS "TOTAL_MB",
        ROUND(NVL(d.total_mb, 0) - NVL(f.free_mb, 0), 2) AS "USADO_MB",
        NVL(f.free_mb, 0) AS "LIBRE_MB",
        CASE 
            WHEN NVL(d.total_mb, 0) > 0 THEN 
                ROUND(((NVL(d.total_mb, 0) - NVL(f.free_mb, 0)) / d.total_mb) * 100, 2)
            ELSE 0 
        END AS "USO_PCT",
        NVL(d.autoextensible, 'NO') AS "AUTOEXTEND",
        t.extent_management AS "GESTION_EXT"
    FROM dba_tablespaces t
    LEFT JOIN df_stats d ON t.tablespace_name = d.tablespace_name
    LEFT JOIN free_stats f ON t.tablespace_name = f.tablespace_name
    ORDER BY t.tablespace_name
    """
    return run_query(conn, sql)


def get_datafiles(conn: oracledb.Connection, tablespace_name: str = None) -> pd.DataFrame:
    """
    Lista los archivos de datos (datafiles y tempfiles) de la base de datos.
    """
    sql = """
    SELECT 
        file_id AS "ID",
        file_name AS "ARCHIVO",
        tablespace_name AS "TABLESPACE",
        ROUND(bytes / 1024 / 1024, 2) AS "TAMANO_MB",
        ROUND(maxbytes / 1024 / 1024, 2) AS "MAX_TAMANO_MB",
        autoextensible AS "AUTOEXTEND",
        ROUND(increment_by * (SELECT value FROM v$parameter WHERE name = 'db_block_size') / 1024 / 1024, 2) AS "INCREMENTO_MB",
        status AS "ESTADO",
        'DATAFILE' AS "TIPO_ARCHIVO"
    FROM dba_data_files
    UNION ALL
    SELECT 
        file_id AS "ID",
        file_name AS "ARCHIVO",
        tablespace_name AS "TABLESPACE",
        ROUND(bytes / 1024 / 1024, 2) AS "TAMANO_MB",
        ROUND(maxbytes / 1024 / 1024, 2) AS "MAX_TAMANO_MB",
        autoextensible AS "AUTOEXTEND",
        ROUND(increment_by * (SELECT value FROM v$parameter WHERE name = 'db_block_size') / 1024 / 1024, 2) AS "INCREMENTO_MB",
        status AS "ESTADO",
        'TEMPFILE' AS "TIPO_ARCHIVO"
    FROM dba_temp_files
    ORDER BY "TABLESPACE", "ID"
    """
    df = run_query(conn, sql)
    if tablespace_name:
        df = df[df["TABLESPACE"] == tablespace_name]
    return df


def get_default_datafile_directory(conn: oracledb.Connection) -> str:
    """
    Intenta obtener el directorio por defecto de los datafiles de Oracle.
    """
    try:
        df = run_query(conn, "SELECT file_name FROM dba_data_files WHERE ROWNUM = 1")
        if not df.empty:
            full_path = df.iloc[0, 0]
            # Extraer ruta del directorio padre
            import os
            return os.path.dirname(full_path)
    except Exception:
        pass
    return "C:\\app\\oracle\\oradata\\XE"


def render_tablespaces(conn: oracledb.Connection):
    """
    Renderiza la vista y controles de administración de Tablespaces.
    """
    st.header("💾 Administración de Tablespaces y Datafiles")
    st.caption("Supervisión de espacio en disco, creación, modificación y gestión de archivos de datos.")

    tab_overview, tab_create, tab_modify, tab_datafiles, tab_drop = st.tabs([
        "📊 Monitoreo General",
        "➕ Crear Tablespace",
        "⚙️ Modificar / Estado",
        "📁 Gestión de Datafiles",
        "🗑️ Eliminar Tablespace"
    ])

    # 1. MONITOREO GENERAL
    with tab_overview:
        col_refresh, _ = st.columns([1, 5])
        with col_refresh:
            if st.button("🔄 Actualizar", key="refresh_ts"):
                st.rerun()

        try:
            df_ts = get_tablespaces_metrics(conn)
            
            # Métricas rápidas
            total_db_mb = df_ts["TOTAL_MB"].sum()
            used_db_mb = df_ts["USADO_MB"].sum()
            free_db_mb = df_ts["LIBRE_MB"].sum()
            avg_pct = (used_db_mb / total_db_mb * 100) if total_db_mb > 0 else 0

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Tablespaces Totales", len(df_ts))
            m2.metric("Capacidad Total (MB)", f"{total_db_mb:,.1f}")
            m3.metric("Espacio Usado (MB)", f"{used_db_mb:,.1f}", delta=f"{avg_pct:.1f}% ocupado", delta_color="inverse")
            m4.metric("Espacio Libre (MB)", f"{free_db_mb:,.1f}")

            # Gráfico de barras de % de Uso
            st.subheader("Ocupación por Tablespace (%)")
            fig = px.bar(
                df_ts,
                x="TABLESPACE",
                y="USO_PCT",
                color="USO_PCT",
                color_continuous_scale=["#2ecc71", "#f39c12", "#e74c3c"],
                range_color=[0, 100],
                text="USO_PCT",
                labels={"USO_PCT": "% Ocupado", "TABLESPACE": "Tablespace"},
                title="Porcentaje de Espacio Utilizado"
            )
            fig.update_layout(height=350, yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)

            # Tabla detallada
            st.subheader("Detalle de Tablespaces")
            st.dataframe(
                df_ts.style.format({
                    "TOTAL_MB": "{:,.2f}",
                    "USADO_MB": "{:,.2f}",
                    "LIBRE_MB": "{:,.2f}",
                    "USO_PCT": "{:.2f}%"
                }),
                use_container_width=True,
                hide_index=True
            )

        except Exception as e:
            st.error(f"Error al consultar métricas de tablespaces: {e}")

    # 2. CREAR TABLESPACE
    with tab_create:
        st.subheader("Crear Nuevo Tablespace")
        default_dir = get_default_datafile_directory(conn)

        with st.form("form_create_tablespace"):
            c1, c2 = st.columns(2)
            with c1:
                new_ts_name = st.text_input("Nombre del Tablespace", placeholder="EJEMPLO_TS").strip().upper()
                ts_type = st.selectbox("Tipo de Tablespace", ["PERMANENT", "TEMPORARY", "UNDO"])
                init_size_mb = st.number_input("Tamaño Inicial (MB)", min_value=10, max_value=102400, value=100, step=10)
            
            with c2:
                suggested_filename = f"{default_dir}\\{new_ts_name.lower() if new_ts_name else 'datafile'}01.dbf"
                datafile_path = st.text_input("Ruta completa del Datafile", value=suggested_filename)
                autoextend = st.checkbox("Habilitar Autoextend", value=True)
                
            if autoextend:
                ca, cb = st.columns(2)
                with ca:
                    next_size_mb = st.number_input("Incremento (NEXT en MB)", min_value=5, max_value=1024, value=20, step=5)
                with cb:
                    unlimited = st.checkbox("Tamaño Máximo Ilimitado (UNLIMITED)", value=True)
                    max_size_mb = st.number_input("Tamaño Máximo (MB)", min_value=init_size_mb, max_value=102400, value=500, disabled=unlimited)

            create_btn = st.form_submit_button("Crear Tablespace", use_container_width=True)

        if create_btn:
            if not new_ts_name or not datafile_path:
                st.warning("Debe ingresar un nombre de tablespace y una ruta válida de datafile.")
            else:
                try:
                    # Construir sentencia DDL
                    if ts_type == "TEMPORARY":
                        ddl = f"CREATE TEMPORARY TABLESPACE {new_ts_name} TEMPFILE '{datafile_path}' SIZE {init_size_mb}M"
                    elif ts_type == "UNDO":
                        ddl = f"CREATE UNDO TABLESPACE {new_ts_name} DATAFILE '{datafile_path}' SIZE {init_size_mb}M"
                    else:
                        ddl = f"CREATE TABLESPACE {new_ts_name} DATAFILE '{datafile_path}' SIZE {init_size_mb}M"

                    if autoextend:
                        max_clause = "UNLIMITED" if unlimited else f"{max_size_mb}M"
                        ddl += f" AUTOEXTEND ON NEXT {next_size_mb}M MAXSIZE {max_clause}"
                    else:
                        ddl += " AUTOEXTEND OFF"

                    with st.spinner("Ejecutando DDL de creación de Tablespace..."):
                        run_dml(conn, ddl)
                    st.success(f"¡Tablespace **{new_ts_name}** creado con éxito!")
                    st.code(ddl, language="sql")
                except Exception as e:
                    st.error(f"Error al crear tablespace: {e}")

    # 3. MODIFICAR / ESTADO TABLESPACE
    with tab_modify:
        st.subheader("Modificar Estado y Parámetros del Tablespace")
        try:
            df_ts_all = run_query(conn, "SELECT tablespace_name, status, contents FROM dba_tablespaces ORDER BY tablespace_name")
            ts_options = df_ts_all["TABLESPACE_NAME"].tolist()
            
            selected_ts = st.selectbox("Seleccionar Tablespace a modificar", ts_options)
            current_status = df_ts_all[df_ts_all["TABLESPACE_NAME"] == selected_ts]["STATUS"].iloc[0]
            st.info(f"Estado actual de **{selected_ts}**: `{current_status}`")

            c_mod1, c_mod2 = st.columns(2)
            with c_mod1:
                st.markdown("#### Cambiar Disponibilidad")
                new_status = st.selectbox("Nuevo Estado", ["ONLINE", "OFFLINE NORMAL", "OFFLINE IMMEDIATE"])
                if st.button("Aplicar Disponibilidad", key="btn_apply_status"):
                    try:
                        ddl = f"ALTER TABLESPACE {selected_ts} {new_status}"
                        run_dml(conn, ddl)
                        st.success(f"Estado de {selected_ts} modificado a {new_status}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al cambiar disponibilidad: {e}")

            with c_mod2:
                st.markdown("#### Modo de Lectura / Escritura")
                new_mode = st.selectbox("Modo", ["READ WRITE", "READ ONLY"])
                if st.button("Aplicar Modo", key="btn_apply_mode"):
                    try:
                        ddl = f"ALTER TABLESPACE {selected_ts} {new_mode}"
                        run_dml(conn, ddl)
                        st.success(f"Modo de {selected_ts} cambiado a {new_mode}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al cambiar modo de lectura/escritura: {e}")

        except Exception as e:
            st.error(f"Error al cargar tablespaces: {e}")

    # 4. GESTIÓN DE DATAFILES
    with tab_datafiles:
        st.subheader("Archivos de Datos (Datafiles y Tempfiles)")
        try:
            df_df = get_datafiles(conn)
            st.dataframe(df_df, use_container_width=True, hide_index=True)

            st.divider()
            col_add, col_resize = st.columns(2)

            # Agregar Datafile
            with col_add:
                st.markdown("#### ➕ Agregar Datafile a Tablespace")
                with st.form("form_add_df"):
                    target_ts = st.selectbox("Tablespace Destino", df_ts_all["TABLESPACE_NAME"].tolist(), key="add_df_ts")
                    new_df_path = st.text_input("Ruta y nombre del nuevo archivo .dbf", value=f"{default_dir}\\{target_ts.lower()}_add01.dbf")
                    df_size = st.number_input("Tamaño (MB)", min_value=10, max_value=51200, value=50, step=10)
                    df_auto = st.checkbox("Autoextend", value=True, key="add_df_auto")
                    btn_add_df = st.form_submit_button("Agregar Datafile")

                if btn_add_df:
                    try:
                        ddl = f"ALTER TABLESPACE {target_ts} ADD DATAFILE '{new_df_path}' SIZE {df_size}M"
                        if df_auto:
                            ddl += " AUTOEXTEND ON NEXT 10M MAXSIZE UNLIMITED"
                        run_dml(conn, ddl)
                        st.success(f"Datafile agregado a {target_ts} con éxito.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al agregar datafile: {e}")

            # Redimensionar Datafile
            with col_resize:
                st.markdown("#### 📏 Redimensionar Datafile Existente")
                with st.form("form_resize_df"):
                    selected_file = st.selectbox("Seleccionar Archivo", df_df["ARCHIVO"].tolist(), key="resize_df_select")
                    target_row = df_df[df_df["ARCHIVO"] == selected_file].iloc[0]
                    file_type = target_row["TIPO_ARCHIVO"]
                    new_size = st.number_input("Nuevo Tamaño (MB)", min_value=5, max_value=102400, value=int(target_row["TAMANO_MB"]) + 50, step=10)
                    btn_resize = st.form_submit_button("Redimensionar")

                if btn_resize:
                    try:
                        keyword = "TEMPFILE" if file_type == "TEMPFILE" else "DATAFILE"
                        ddl = f"ALTER DATABASE {keyword} '{selected_file}' RESIZE {new_size}M"
                        run_dml(conn, ddl)
                        st.success(f"Archivo {selected_file} redimensionado a {new_size} MB con éxito.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al redimensionar archivo: {e}")

        except Exception as e:
            st.error(f"Error en gestión de datafiles: {e}")

    # 5. ELIMINAR TABLESPACE
    with tab_drop:
        st.subheader("🗑️ Eliminar Tablespace (DROP TABLESPACE)")
        st.warning("⚠️ **Precaución**: Esta operación es destructiva e irreversible. Asegúrese de tener respaldos de los datos importantes.")

        try:
            df_drop = run_query(conn, "SELECT tablespace_name, contents FROM dba_tablespaces WHERE tablespace_name NOT IN ('SYSTEM', 'SYSAUX', 'UNDOTBS1', 'TEMP') ORDER BY tablespace_name")
            if df_drop.empty:
                st.info("No hay tablespaces creados por el usuario disponibles para eliminar (los tablespaces del sistema SYSTEM, SYSAUX, UNDO y TEMP están protegidos).")
            else:
                drop_ts_target = st.selectbox("Tablespace a Eliminar", df_drop["TABLESPACE_NAME"].tolist())
                
                c_inc = st.checkbox("INCLUDING CONTENTS (Eliminar todos los objetos y datos contenidos)", value=True)
                c_data = st.checkbox("AND DATAFILES (Eliminar físicamente los archivos .dbf del disco)", value=True)
                c_casc = st.checkbox("CASCADE CONSTRAINTS (Eliminar restricciones de integridad referencial dependientes)", value=True)

                confirm_txt = st.text_input(f"Escriba exactamente '{drop_ts_target}' para confirmar:")
                btn_drop = st.button("🚨 Eliminar Tablespace Definitivamente", type="primary")

                if btn_drop:
                    if confirm_txt.strip() != drop_ts_target:
                        st.error("El texto de confirmación no coincide con el nombre del tablespace.")
                    else:
                        try:
                            ddl = f"DROP TABLESPACE {drop_ts_target}"
                            if c_inc:
                                ddl += " INCLUDING CONTENTS"
                            if c_casc:
                                ddl += " CASCADE CONSTRAINTS"
                            if c_data:
                                ddl += " AND DATAFILES"

                            run_dml(conn, ddl)
                            st.success(f"Tablespace **{drop_ts_target}** eliminado con éxito.")
                            st.code(ddl, language="sql")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar tablespace: {e}")

        except Exception as e:
            st.error(f"Error al cargar lista de tablespaces para eliminación: {e}")

