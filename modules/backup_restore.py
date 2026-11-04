"""
Módulo para la Creación y Recuperación de Respaldos en Oracle 21c XE utilizando Oracle Data Pump.
Soporta:
1. Exportación (expdp): Schemas, Tablas y Full Database.
2. Importación / Restauración (impdp): Schemas, Tablas, Full, con Remap de Esquemas y control de tablas existentes.
"""

import os
import subprocess
import datetime
import tempfile
import streamlit as st
import pandas as pd
import oracledb
from modules.common import run_query, render_subtabs
from modules.directories import get_oracle_directories, list_files_in_directory


def execute_datapump(command_type: str, par_content: str) -> tuple:
    """
    Ejecuta expdp o impdp usando un archivo temporal de parámetros (parfile).
    Retorna (exit_code, output_text).
    """
    temp_par = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".par", encoding="utf-8")
    temp_par.write(par_content)
    temp_par.close()

    cmd = [command_type, f"parfile={temp_par.name}"]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        output_lines = []
        for line in iter(process.stdout.readline, ''):
            output_lines.append(line)
        process.stdout.close()
        return_code = process.wait()
        full_output = "".join(output_lines)
        return return_code, full_output
    except Exception as e:
        return -1, f"Error al invocar {command_type}: {str(e)}"
    finally:
        if os.path.exists(temp_par.name):
            try:
                os.remove(temp_par.name)
            except Exception:
                pass


def render_backup_restore(conn: oracledb.Connection, conn_params: dict):
    """
    Renderiza la interfaz para la creación y recuperación de respaldos con Data Pump.
    """
    st.header("📦 Respaldos y Recuperación (Oracle Data Pump)")
    st.caption("Generación y restauración de copias de seguridad lógicas de esquemas, tablas o base de datos completa.")

    active_tab = render_subtabs([
        "📤 Crear Respaldo (Export / expdp)",
        "📥 Recuperar Respaldo (Import / impdp)"
    ], key="backup_active_subtab")

    # Directorios disponibles
    df_dirs = get_oracle_directories(conn)
    if df_dirs.empty:
        st.warning("No se encontraron directorios en Oracle. Cree al menos un directorio en el módulo 'Directorios y Archivos' antes de continuar.")
        return

    dir_names = df_dirs["NOMBRE_DIRECTORIO"].tolist()
    default_dir_idx = dir_names.index("DATA_PUMP_DIR") if "DATA_PUMP_DIR" in dir_names else 0

    # Construir cadena de conexión para el parfile
    user = conn_params.get("user", "system")
    password = conn_params.get("password", "")
    host = conn_params.get("host", "localhost")
    port = conn_params.get("port", 1521)
    service_name = conn_params.get("service_name", "XEPDB1")
    is_sysdba = conn_params.get("is_sysdba", False)

    connect_target = f"{host}:{port}/{service_name}"
    if is_sysdba or user.lower() == "sys":
        userid_line = f'USERID="{user}/{password}@{connect_target} as sysdba"'
    else:
        userid_line = f'USERID={user}/{password}@{connect_target}'

    # 1. CREACIÓN DE RESPALDOS (EXPDP)
    if active_tab == "📤 Crear Respaldo (Export / expdp)":
        st.subheader("Configuración de Exportación (expdp)")

        mode = st.radio(
            "Alcance del Respaldo:",
            ["Por Esquemas (Schemas)", "Por Tablas Específicas", "Respaldo Completo (Full Database)"],
            horizontal=True
        )

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            sel_exp_dir = st.selectbox("Directorio Oracle de Destino:", dir_names, index=default_dir_idx, key="exp_dir_sel")
            
            # Obtener esquemas válidos
            schemas_df = run_query(conn, "SELECT username FROM all_users WHERE oracle_maintained = 'N' OR username IN ('SYSTEM', 'HR', 'SH') ORDER BY username")
            schema_list = schemas_df["USERNAME"].tolist() if not schemas_df.empty else ["SYSTEM"]

            selected_schemas = []
            selected_tables = []
            
            if "Esquemas" in mode:
                selected_schemas = st.multiselect("Seleccionar Esquema(s) a respaldar:", schema_list, default=[schema_list[0]] if schema_list else [])
            elif "Tablas" in mode:
                sel_schema_for_tables = st.selectbox("Esquema:", schema_list, key="exp_schema_for_tables")
                tables_df = run_query(conn, "SELECT table_name FROM all_tables WHERE owner = :o ORDER BY table_name", {"o": sel_schema_for_tables})
                available_tables = tables_df["TABLE_NAME"].tolist() if not tables_df.empty else []
                selected_tables_raw = st.multiselect("Seleccionar Tabla(s):", available_tables)
                selected_tables = [f"{sel_schema_for_tables}.{t}" for t in selected_tables_raw]
            else:
                st.info("ℹ️ Se respaldará la base de datos completa (`FULL=Y`), incluyendo metadatos, datos de todos los usuarios y tablespaces.")

        with col_b2:
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = "EXP_FULL" if "Completo" in mode else ("EXP_SCHEMAS" if "Esquemas" in mode else "EXP_TABLES")
            
            default_dmp_name = f"{prefix}_{timestamp_str}.dmp"
            default_log_name = f"{prefix}_{timestamp_str}.log"

            dumpfile_name = st.text_input("Nombre del archivo de volcado (.dmp):", value=default_dmp_name)
            logfile_name = st.text_input("Nombre del archivo de registro (.log):", value=default_log_name)
            compression = st.selectbox(
                "Compresión:",
                ["NONE", "METADATA_ONLY", "ALL", "DATA_ONLY"],
                index=0,
                format_func=lambda x: {
                    "NONE": "NONE (Sin compresión - Recomendado para Oracle XE)",
                    "METADATA_ONLY": "METADATA_ONLY (Solo metadatos - Soportado en XE)",
                    "ALL": "ALL (Todo - Requiere Oracle Enterprise Edition)",
                    "DATA_ONLY": "DATA_ONLY (Solo datos - Requiere Oracle Enterprise Edition)"
                }.get(x, x),
                help="Oracle 21c XE no incluye la opción de compresión de datos de Enterprise Edition. Use NONE o METADATA_ONLY."
            )
            reuse_dump = st.checkbox("Sobrescribir si el archivo ya existe (REUSE_DUMPFILES=YES)", value=True)

        if st.button("🚀 Ejecutar Respaldo Ahora", type="primary", use_container_width=True):
            if "Esquemas" in mode and not selected_schemas:
                st.warning("Debe seleccionar al menos un esquema para respaldar.")
            elif "Tablas" in mode and not selected_tables:
                st.warning("Debe seleccionar al menos una tabla para respaldar.")
            else:
                # Construir parámetros
                par_lines = [
                    userid_line,
                    f"DIRECTORY={sel_exp_dir}",
                    f"DUMPFILE={dumpfile_name}",
                    f"LOGFILE={logfile_name}",
                    f"COMPRESSION={compression}",
                    f"REUSE_DUMPFILES={'YES' if reuse_dump else 'NO'}"
                ]

                if "Esquemas" in mode:
                    par_lines.append(f"SCHEMAS={','.join(selected_schemas)}")
                elif "Tablas" in mode:
                    par_lines.append(f"TABLES={','.join(selected_tables)}")
                else:
                    par_lines.append("FULL=YES")

                parfile_str = "\n".join(par_lines)

                with st.spinner("Ejecutando Oracle Data Pump Export (expdp)..."):
                    exit_code, output_text = execute_datapump("expdp", parfile_str)

                if exit_code == 0:
                    st.success("✅ ¡Respaldo completado exitosamente!")
                elif exit_code == 5:
                    st.warning("⚠️ El respaldo finalizó con advertencias (algunos objetos o tablas vacías).")
                else:
                    st.error(f"❌ El proceso de respaldo falló con código de salida {exit_code}.")

                with st.expander("Consola y Registro de Salida (expdp)", expanded=True):
                    st.code(output_text, language="text")

    # 2. RECUPERACIÓN DE RESPALDOS (IMPDP)
    elif active_tab == "📥 Recuperar Respaldo (Import / impdp)":
        st.subheader("Configuración de Importación / Restauración (impdp)")

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            sel_imp_dir = st.selectbox("Directorio donde se encuentra el respaldo:", dir_names, index=default_dir_idx, key="imp_dir_sel")
            dir_row = df_dirs[df_dirs["NOMBRE_DIRECTORIO"] == sel_imp_dir].iloc[0]
            phys_path = dir_row["RUTA_FISICA"]

            # Listar archivos .dmp
            available_files_df = list_files_in_directory(phys_path)
            dmp_files = []
            if not available_files_df.empty:
                dmp_files = available_files_df[available_files_df["EXTENSION"] == ".dmp"]["NOMBRE_ARCHIVO"].tolist()

            if not dmp_files:
                st.warning(f"No se encontraron archivos .dmp en `{phys_path}`. Genere primero un respaldo o coloque un archivo .dmp en esa carpeta.")
                return

            sel_dmp_file = st.selectbox("Archivo de volcado a restaurar (.dmp):", dmp_files)
            restore_mode = st.radio("Modalidad de Restauración:", ["Por Esquemas (Schemas)", "Por Tablas", "Completo (Full)"], horizontal=True)

            restore_schemas = []
            restore_tables = []
            if "Esquemas" in restore_mode:
                raw_schemas = st.text_input("Esquema(s) a restaurar (separados por coma):", placeholder="HR, VENTAS")
                restore_schemas = [s.strip().upper() for s in raw_schemas.split(",") if s.strip()]
            elif "Tablas" in restore_mode:
                raw_tables = st.text_input("Tabla(s) a restaurar (ESQUEMA.TABLA, separadas por coma):", placeholder="HR.EMPLOYEES, HR.JOBS")
                restore_tables = [t.strip().upper() for t in raw_tables.split(",") if t.strip()]

        with col_r2:
            timestamp_rst = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            imp_log_name = st.text_input("Nombre de Log de Importación:", value=f"IMP_{timestamp_rst}.log")
            table_exists_action = st.selectbox(
                "Acción si las tablas ya existen (TABLE_EXISTS_ACTION):",
                ["REPLACE", "TRUNCATE", "APPEND", "SKIP"],
                index=0,
                format_func=lambda x: {
                    "REPLACE": "REPLACE - Elimina la tabla existente y la recrea con datos del volcado",
                    "TRUNCATE": "TRUNCATE - Vacía la tabla existente y reinserta los datos",
                    "APPEND": "APPEND - Conserva datos existentes y agrega los del respaldo",
                    "SKIP": "SKIP - Salta la tabla si ya existe (no la toca)"
                }[x]
            )

        st.divider()
        st.markdown("#### Opciones Avanzadas de Restauración")
        c_adv1, c_adv2 = st.columns(2)
        with c_adv1:
            use_remap_schema = st.checkbox("Reasignar Esquema (REMAP_SCHEMA - Restaurar en otro usuario)")
            if use_remap_schema:
                remap_src = st.text_input("Esquema Origen (en el respaldo):", placeholder="HR").strip().upper()
                remap_dst = st.text_input("Esquema Destino (nuevo propietario):", placeholder="HR_TEST").strip().upper()
        
        with c_adv2:
            use_remap_ts = st.checkbox("Reasignar Tablespace (REMAP_TABLESPACE)")
            if use_remap_ts:
                ts_src = st.text_input("Tablespace Origen:", placeholder="USERS").strip().upper()
                ts_dst = st.text_input("Tablespace Destino:", placeholder="NUEVO_TS").strip().upper()

        if st.button("📥 Iniciar Proceso de Restauración", type="primary", use_container_width=True):
            imp_lines = [
                userid_line,
                f"DIRECTORY={sel_imp_dir}",
                f"DUMPFILE={sel_dmp_file}",
                f"LOGFILE={imp_log_name}",
                f"TABLE_EXISTS_ACTION={table_exists_action}"
            ]

            if "Completo" in restore_mode:
                imp_lines.append("FULL=YES")
            elif "Esquemas" in restore_mode and restore_schemas:
                imp_lines.append(f"SCHEMAS={','.join(restore_schemas)}")
            elif "Tablas" in restore_mode and restore_tables:
                imp_lines.append(f"TABLES={','.join(restore_tables)}")

            if use_remap_schema and remap_src and remap_dst:
                imp_lines.append(f"REMAP_SCHEMA={remap_src}:{remap_dst}")

            if use_remap_ts and ts_src and ts_dst:
                imp_lines.append(f"REMAP_TABLESPACE={ts_src}:{ts_dst}")

            imp_parfile_str = "\n".join(imp_lines)

            with st.spinner("Ejecutando Oracle Data Pump Import (impdp)..."):
                exit_code, output_text = execute_datapump("impdp", imp_parfile_str)

            if exit_code == 0:
                st.success("✅ ¡Restauración completada exitosamente!")
            elif exit_code == 5:
                st.warning("⚠️ La importación finalizó con advertencias (ej: objetos ya existentes o permisos).")
            else:
                st.error(f"❌ La restauración finalizó con errores (código de salida {exit_code}).")

            with st.expander("Consola y Registro de Salida (impdp)", expanded=True):
                st.code(output_text, language="text")
