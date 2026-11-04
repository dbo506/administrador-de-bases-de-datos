"""
Módulo para la Administración de Directorios de Oracle y Archivos de Respaldo.
Permite:
1. Listar, crear y eliminar objetos DIRECTORY de Oracle (DBA_DIRECTORIES).
2. Explorar los archivos físicos (.dmp, .log) contenidos en el directorio.
3. Visualizar y descargar archivos de registro (logs) de Data Pump.
4. Eliminar archivos antiguos de respaldo para liberar espacio en disco.
"""

import os
import datetime
import streamlit as st
import pandas as pd
import oracledb
from modules.common import run_query, run_dml, flash, render_subtabs


def get_oracle_directories(conn: oracledb.Connection) -> pd.DataFrame:
    """
    Retorna la lista de directorios registrados en Oracle.
    """
    sql = """
    SELECT 
        owner AS "PROPIETARIO",
        directory_name AS "NOMBRE_DIRECTORIO",
        directory_path AS "RUTA_FISICA"
    FROM dba_directories
    ORDER BY directory_name
    """
    return run_query(conn, sql)


def list_files_in_directory(path: str) -> pd.DataFrame:
    """
    Explora la ruta física del sistema de archivos y lista los archivos encontrados.
    """
    if not os.path.exists(path):
        return pd.DataFrame()

    file_records = []
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                stat = entry.stat()
                file_records.append({
                    "NOMBRE_ARCHIVO": entry.name,
                    "EXTENSION": os.path.splitext(entry.name)[1].lower(),
                    "TAMANO_MB": round(stat.st_size / (1024 * 1024), 3),
                    "TAMANO_KB": round(stat.st_size / 1024, 2),
                    "FECHA_MODIFICACION": datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    "RUTA_COMPLETA": entry.path
                })
    except Exception as e:
        st.error(f"Error al leer archivos del sistema operativo: {e}")

    df = pd.DataFrame(file_records)
    if not df.empty:
        df = df.sort_values(by="FECHA_MODIFICACION", ascending=False)
    return df


def render_directories(conn: oracledb.Connection):
    """
    Renderiza la interfaz de gestión de directorios y explorador de respaldos.
    """
    st.header("📁 Administración de Directorios y Archivos de Respaldo")
    st.caption("Configuración de objetos DIRECTORY en Oracle y explorador de archivos .dmp y .log.")

    active_tab = render_subtabs([
        "📂 Explorador de Archivos de Respaldo",
        "⚙️ Gestión de Directorios de Oracle"
    ], key="dirs_active_subtab")

    df_dirs = get_oracle_directories(conn)
    if df_dirs.empty:
        st.warning("No hay directorios registrados en Oracle.")
        return

    dir_options = df_dirs["NOMBRE_DIRECTORIO"].tolist()
    default_idx = dir_options.index("DATA_PUMP_DIR") if "DATA_PUMP_DIR" in dir_options else 0

    # 1. EXPLORADOR DE ARCHIVOS
    if active_tab == "📂 Explorador de Archivos de Respaldo":
        st.subheader("Archivos de Volcado (.dmp) y Logs (.log)")

        selected_dir_name = st.selectbox("Seleccione el Directorio de Oracle:", dir_options, index=default_idx)

        selected_row = df_dirs[df_dirs["NOMBRE_DIRECTORIO"] == selected_dir_name].iloc[0]
        phys_path = selected_row["RUTA_FISICA"]
        st.info(f"📍 Ruta física en el servidor: `{phys_path}`")

        # Verificar si la ruta existe físicamente
        if not os.path.exists(phys_path):
            st.error(f"⚠️ La ruta física `{phys_path}` no existe actualmente en el sistema de archivos de Windows. Puede crearla manualmente o desde la pestaña de Gestión de Directorios.")
        else:
            files_df = list_files_in_directory(phys_path)
            if files_df.empty:
                st.info("El directorio no contiene archivos actualmente.")
            else:
                st.dataframe(
                    files_df[["NOMBRE_ARCHIVO", "EXTENSION", "TAMANO_MB", "FECHA_MODIFICACION"]],
                    use_container_width=True,
                    hide_index=True
                )

                st.divider()
                st.markdown("#### 🔍 Visor de Logs y Descarga de Respaldos")
                col_v1, col_v2 = st.columns([3, 2])

                with col_v1:
                    log_files = files_df[files_df["EXTENSION"].isin([".log", ".txt"])]["NOMBRE_ARCHIVO"].tolist()
                    if log_files:
                        sel_log = st.selectbox("Seleccionar Archivo de Log para Visualizar:", log_files)
                        if st.button("Ver Contenido del Log"):
                            target_log_path = os.path.join(phys_path, sel_log)
                            try:
                                with open(target_log_path, "r", encoding="utf-8", errors="replace") as f:
                                    log_content = f.read()
                                st.code(log_content, language="text")
                            except Exception as e:
                                st.error(f"Error al leer el archivo log: {e}")
                    else:
                        st.info("No hay archivos .log disponibles en este directorio.")

                with col_v2:
                    all_files = files_df["NOMBRE_ARCHIVO"].tolist()
                    sel_file_action = st.selectbox("Seleccionar Archivo para Descargar o Eliminar:", all_files)
                    target_file_path = os.path.join(phys_path, sel_file_action)

                    # Botón de Descarga
                    try:
                        with open(target_file_path, "rb") as f_down:
                            st.download_button(
                                label=f"⬇️ Descargar {sel_file_action}",
                                data=f_down,
                                file_name=sel_file_action,
                                use_container_width=True
                            )
                    except Exception:
                        pass

                    # Botón de Eliminación
                    confirm_file_del = st.checkbox(f"Confirmo que deseo eliminar {sel_file_action} del disco", key=f"confirm_del_{sel_file_action}")
                    if st.button(f"🗑️ Eliminar {sel_file_action}", type="primary", use_container_width=True, disabled=not confirm_file_del):
                        try:
                            os.remove(target_file_path)
                            flash(f"Archivo {sel_file_action} eliminado con éxito.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar archivo: {e}")

    # 2. GESTIÓN DE DIRECTORIOS DE ORACLE
    elif active_tab == "⚙️ Gestión de Directorios de Oracle":
        st.subheader("Crear y Eliminar Directorios de Oracle")
        
        st.markdown("#### Directorios Existentes")
        st.dataframe(df_dirs, use_container_width=True, hide_index=True)

        st.divider()
        col_c_dir, col_d_dir = st.columns(2)

        with col_c_dir:
            st.markdown("#### ➕ Crear Nuevo Directorio")
            with st.form("form_create_directory"):
                new_dir_name = st.text_input("Nombre del Directorio en Oracle", placeholder="EXP_BACKUP_DIR").strip().upper()
                new_dir_path = st.text_input("Ruta Física en el Disco", value="C:\\oracle_backups")
                create_folder = st.checkbox("Crear la carpeta en Windows si no existe", value=True)
                grant_public = st.checkbox("Conceder permisos READ, WRITE a PUBLIC", value=False)
                btn_create_d = st.form_submit_button("Crear Directorio")

            if btn_create_d:
                if not new_dir_name or not new_dir_path:
                    st.warning("Ingrese nombre de directorio y ruta física.")
                else:
                    try:
                        if create_folder and not os.path.exists(new_dir_path):
                            os.makedirs(new_dir_path, exist_ok=True)

                        ddl_dir = f"CREATE OR REPLACE DIRECTORY {new_dir_name} AS '{new_dir_path}'"
                        run_dml(conn, ddl_dir)

                        if grant_public:
                            run_dml(conn, f"GRANT READ, WRITE ON DIRECTORY {new_dir_name} TO PUBLIC")

                        flash(f"Directorio **{new_dir_name}** creado exitosamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear directorio: {e}")

        with col_d_dir:
            st.markdown("#### 🗑️ Eliminar Directorio")
            with st.form("form_drop_directory"):
                # No permitir eliminar DATA_PUMP_DIR por accidente
                droppable_dirs = [d for d in dir_options if d not in ["DATA_PUMP_DIR", "ORACLE_BASE", "ORACLE_HOME"]]
                sel_drop_dir = st.selectbox("Directorio a Eliminar:", droppable_dirs if droppable_dirs else ["(Ninguno disponible)"])
                btn_drop_d = st.form_submit_button("Eliminar Directorio", type="primary")

            if btn_drop_d and sel_drop_dir and sel_drop_dir != "(Ninguno disponible)":
                try:
                    run_dml(conn, f"DROP DIRECTORY {sel_drop_dir}")
                    flash(f"Directorio {sel_drop_dir} eliminado de Oracle.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al eliminar directorio: {e}")
