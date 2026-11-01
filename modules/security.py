"""
Módulo para la Seguridad y Administración de Usuarios en Oracle 21c XE.
Incluye:
1. Gestión de usuarios (Crear, Modificar, Bloquear/Desbloquear, Reset Password, Drop).
2. Roles y Privilegios (Asignación y revocación de roles y privilegios de sistema y objetos).
3. Perfiles de Contraseñas y Recursos (DBA_PROFILES).
"""

import streamlit as st
import pandas as pd
import oracledb
from modules.common import run_query, run_dml, flash


def get_users_list(conn: oracledb.Connection, only_open: bool = False) -> pd.DataFrame:
    """
    Retorna la lista de usuarios con sus estados y tablespaces asignados.
    """
    sql = """
    SELECT 
        username AS "USUARIO",
        account_status AS "ESTADO_CUENTA",
        default_tablespace AS "TABLESPACE_DEF",
        temporary_tablespace AS "TABLESPACE_TEMP",
        profile AS "PERFIL",
        TO_CHAR(created, 'YYYY-MM-DD HH24:MI') AS "FECHA_CREACION",
        TO_CHAR(expiry_date, 'YYYY-MM-DD HH24:MI') AS "FECHA_EXPIRACION",
        oracle_maintained AS "DEL_SISTEMA"
    FROM dba_users
    ORDER BY oracle_maintained, username
    """
    df = run_query(conn, sql)
    if only_open:
        df = df[df["ESTADO_CUENTA"] == "OPEN"]
    return df


def get_roles_list(conn: oracledb.Connection) -> list:
    """
    Retorna los roles disponibles en la base de datos.
    """
    df = run_query(conn, "SELECT role FROM dba_roles ORDER BY role")
    return df["ROLE"].tolist() if not df.empty else []


def get_user_roles(conn: oracledb.Connection, username: str) -> pd.DataFrame:
    """
    Retorna los roles otorgados al usuario indicado.
    """
    sql = """
    SELECT 
        granted_role AS "ROL_OTORGADO",
        admin_option AS "OPCION_ADMIN",
        default_role AS "ROL_DEFECTO"
    FROM dba_role_privs
    WHERE grantee = :u
    ORDER BY granted_role
    """
    return run_query(conn, sql, {"u": username})


def get_user_sys_privs(conn: oracledb.Connection, username: str) -> pd.DataFrame:
    """
    Retorna los privilegios de sistema otorgados a un usuario.
    """
    sql = """
    SELECT 
        privilege AS "PRIVILEGIO",
        admin_option AS "OPCION_ADMIN"
    FROM dba_sys_privs
    WHERE grantee = :u
    ORDER BY privilege
    """
    return run_query(conn, sql, {"u": username})


def get_profiles_summary(conn: oracledb.Connection) -> pd.DataFrame:
    """
    Obtiene las directivas de seguridad de contraseñas de los perfiles.
    """
    sql = """
    SELECT 
        profile AS "PERFIL",
        resource_name AS "PARAMETRO",
        limit AS "VALOR_LIMITE"
    FROM dba_profiles
    WHERE resource_type = 'PASSWORD'
      AND resource_name IN ('FAILED_LOGIN_ATTEMPTS', 'PASSWORD_LIFE_TIME', 'PASSWORD_LOCK_TIME', 'PASSWORD_GRACE_TIME')
    ORDER BY profile, resource_name
    """
    return run_query(conn, sql)


def render_security(conn: oracledb.Connection):
    """
    Renderiza la interfaz para administración de seguridad y usuarios.
    """
    st.header("👥 Seguridad y Administración de Usuarios")
    st.caption("Control de cuentas, contraseñas, asignación de roles, privilegios y políticas de seguridad.")

    tab_users, tab_create_user, tab_manage_user, tab_roles_privs, tab_profiles = st.tabs([
        "📋 Directorio de Usuarios",
        "➕ Crear Usuario",
        "⚙️ Modificar / Bloquear / Drop",
        "🔑 Roles y Privilegios",
        "🛡️ Perfiles de Seguridad"
    ])

    # 1. DIRECTORIO DE USUARIOS
    with tab_users:
        st.subheader("Usuarios Registrados en Oracle")
        
        c_u1, c_u2 = st.columns([2, 1])
        with c_u1:
            filter_sys = st.checkbox("Ocultar usuarios internos de Oracle (ORACLE_MAINTAINED = 'Y')", value=True)
        with c_u2:
            if st.button("🔄 Refrescar Lista", key="ref_users"):
                st.rerun()

        try:
            df_users = get_users_list(conn)
            if filter_sys and "DEL_SISTEMA" in df_users.columns:
                df_users = df_users[df_users["DEL_SISTEMA"] == "N"]

            # Métricas
            total_u = len(df_users)
            open_u = len(df_users[df_users["ESTADO_CUENTA"] == "OPEN"])
            locked_u = len(df_users[df_users["ESTADO_CUENTA"].str.contains("LOCKED", na=False)])
            expired_u = len(df_users[df_users["ESTADO_CUENTA"].str.contains("EXPIRED", na=False)])

            mu1, mu2, mu3, mu4 = st.columns(4)
            mu1.metric("Usuarios", total_u)
            mu2.metric("Abiertos (OPEN)", open_u)
            mu3.metric("Bloqueados (LOCKED)", locked_u)
            mu4.metric("Expirados (EXPIRED)", expired_u)

            st.dataframe(df_users, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error al listar usuarios: {e}")

    # 2. CREAR USUARIO
    with tab_create_user:
        st.subheader("Crear Nueva Cuenta de Usuario")

        # Obtener tablespaces disponibles
        try:
            ts_perm_df = run_query(conn, "SELECT tablespace_name FROM dba_tablespaces WHERE contents = 'PERMANENT'")
            ts_temp_df = run_query(conn, "SELECT tablespace_name FROM dba_tablespaces WHERE contents = 'TEMPORARY'")
            profiles_df = run_query(conn, "SELECT DISTINCT profile FROM dba_profiles ORDER BY profile")
            
            ts_perm_list = ts_perm_df["TABLESPACE_NAME"].tolist() if not ts_perm_df.empty else ["USERS"]
            ts_temp_list = ts_temp_df["TABLESPACE_NAME"].tolist() if not ts_temp_df.empty else ["TEMP"]
            prof_list = profiles_df["PROFILE"].tolist() if not profiles_df.empty else ["DEFAULT"]
        except Exception:
            ts_perm_list = ["USERS"]
            ts_temp_list = ["TEMP"]
            prof_list = ["DEFAULT"]

        with st.form("form_create_user"):
            c_cu1, c_cu2 = st.columns(2)
            with c_cu1:
                new_username = st.text_input("Nombre de Usuario", placeholder="C##APP_USER o HR_USER").strip().upper()
                new_user_pwd = st.text_input("Contraseña Temporal / Inicial", type="password")
                sel_profile = st.selectbox("Perfil de Seguridad", prof_list)
            with c_cu2:
                sel_def_ts = st.selectbox("Tablespace por Defecto", ts_perm_list)
                sel_tmp_ts = st.selectbox("Tablespace Temporal", ts_temp_list)
                quota_unlimited = st.checkbox("Cuota Ilimitada en Tablespace por Defecto", value=True)

            st.markdown("##### Privilegios Iniciales")
            grant_connect = st.checkbox("Asignar rol CONNECT (Inicio de sesión)", value=True)
            grant_resource = st.checkbox("Asignar rol RESOURCE (Creación de tablas, secuencias, etc.)", value=True)

            btn_submit_create_user = st.form_submit_button("Crear Usuario", use_container_width=True)

        if btn_submit_create_user:
            if not new_username or not new_user_pwd:
                st.warning("Debe ingresar un nombre de usuario y una contraseña.")
            else:
                try:
                    # DDL de creación
                    ddl_user = f"CREATE USER {new_username} IDENTIFIED BY \"{new_user_pwd}\" DEFAULT TABLESPACE {sel_def_ts} TEMPORARY TABLESPACE {sel_tmp_ts} PROFILE {sel_profile}"
                    if quota_unlimited:
                        ddl_user += f" QUOTA UNLIMITED ON {sel_def_ts}"

                    with st.spinner(f"Creando usuario {new_username}..."):
                        run_dml(conn, ddl_user)

                        # Roles iniciales
                        if grant_connect:
                            run_dml(conn, f"GRANT CONNECT TO {new_username}")
                        if grant_resource:
                            run_dml(conn, f"GRANT RESOURCE TO {new_username}")

                    flash(f"¡Usuario **{new_username}** creado exitosamente!", code=ddl_user)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al crear usuario: {e}")

    # 3. MODIFICAR / BLOQUEAR / DROP
    with tab_manage_user:
        st.subheader("Mantenimiento de Usuarios")

        try:
            df_target_users = run_query(conn, "SELECT username, account_status FROM dba_users WHERE oracle_maintained = 'N' OR username IN ('SYSTEM', 'HR') ORDER BY username")
            if df_target_users.empty:
                df_target_users = run_query(conn, "SELECT username, account_status FROM dba_users ORDER BY username")
            
            selected_u = st.selectbox("Seleccione el Usuario a Modificar:", df_target_users["USERNAME"].tolist())
            curr_stat = df_target_users[df_target_users["USERNAME"] == selected_u]["ACCOUNT_STATUS"].iloc[0]
            st.info(f"Usuario: **{selected_u}** | Estado actual: `{curr_stat}`")

            col_pwd, col_lock = st.columns(2)
            with col_pwd:
                st.markdown("#### Cambiar Contraseña")
                with st.form("form_change_pwd"):
                    new_pwd_change = st.text_input("Nueva Contraseña", type="password")
                    expire_now = st.checkbox("Expirar contraseña (obligar a cambiar en el próximo login)", value=False)
                    btn_pwd = st.form_submit_button("Actualizar Contraseña")

                if btn_pwd:
                    if not new_pwd_change:
                        st.warning("Ingrese la nueva contraseña.")
                    else:
                        try:
                            run_dml(conn, f"ALTER USER {selected_u} IDENTIFIED BY \"{new_pwd_change}\"")
                            if expire_now:
                                run_dml(conn, f"ALTER USER {selected_u} PASSWORD EXPIRE")
                            st.success(f"Contraseña de {selected_u} actualizada.")
                        except Exception as e:
                            st.error(f"Error al cambiar contraseña: {e}")

            with col_lock:
                st.markdown("#### Bloqueo / Desbloqueo")
                c_lk1, c_lk2 = st.columns(2)
                with c_lk1:
                    if st.button("🔓 Desbloquear Cuenta", use_container_width=True):
                        try:
                            run_dml(conn, f"ALTER USER {selected_u} ACCOUNT UNLOCK")
                            flash(f"Cuenta {selected_u} desbloqueada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                with c_lk2:
                    if st.button("🔒 Bloquear Cuenta", use_container_width=True):
                        try:
                            run_dml(conn, f"ALTER USER {selected_u} ACCOUNT LOCK")
                            flash(f"Cuenta {selected_u} bloqueada.", "warning")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

            st.divider()
            st.markdown("#### 🗑️ Eliminar Usuario (DROP USER)")
            with st.expander("Zona de Peligro: Eliminar Usuario Definitivamente"):
                st.warning(f"Se eliminará el usuario **{selected_u}**.")
                cascade_drop = st.checkbox("Eliminar también todos los objetos creados por el usuario (CASCADE)", value=True)
                confirm_drop_u = st.text_input(f"Escriba exactamente '{selected_u}' para confirmar eliminación:")
                if st.button(f"🚨 Eliminar Usuario {selected_u}", type="primary"):
                    if confirm_drop_u.strip() != selected_u:
                        st.error("El texto de confirmación no coincide.")
                    else:
                        try:
                            ddl_drop_u = f"DROP USER {selected_u}"
                            if cascade_drop:
                                ddl_drop_u += " CASCADE"
                            run_dml(conn, ddl_drop_u)
                            flash(f"Usuario {selected_u} eliminado correctamente.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar usuario: {e}")

        except Exception as e:
            st.error(f"Error al cargar módulo de modificación: {e}")

    # 4. ROLES Y PRIVILEGIOS
    with tab_roles_privs:
        st.subheader("Asignación de Roles y Privilegios")
        try:
            target_user_privs = st.selectbox("Seleccione el Usuario:", df_target_users["USERNAME"].tolist(), key="privs_user_sel")
            
            c_r1, c_r2 = st.columns(2)
            with c_r1:
                st.markdown(f"#### Roles Otorgados a `{target_user_privs}`")
                df_user_roles = get_user_roles(conn, target_user_privs)
                st.dataframe(df_user_roles, use_container_width=True, hide_index=True)

                # Conceder rol
                st.markdown("##### ➕ Conceder Rol")
                available_roles = get_roles_list(conn)
                sel_role_to_grant = st.selectbox("Rol a otorgar", available_roles)
                with_admin = st.checkbox("Con opción de administración (WITH ADMIN OPTION)")
                if st.button("Otorgar Rol"):
                    try:
                        sql_gr = f"GRANT {sel_role_to_grant} TO {target_user_privs}"
                        if with_admin:
                            sql_gr += " WITH ADMIN OPTION"
                        run_dml(conn, sql_gr)
                        flash(f"Rol {sel_role_to_grant} otorgado a {target_user_privs}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al otorgar rol: {e}")

                # Revocar rol
                if not df_user_roles.empty:
                    st.markdown("##### ➖ Revocar Rol")
                    role_to_revoke = st.selectbox("Rol a revocar", df_user_roles["ROL_OTORGADO"].tolist())
                    if st.button("Revocar Rol", type="primary"):
                        try:
                            run_dml(conn, f"REVOKE {role_to_revoke} FROM {target_user_privs}")
                            flash(f"Rol {role_to_revoke} revocado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al revocar rol: {e}")

            with c_r2:
                st.markdown(f"#### Privilegios de Sistema de `{target_user_privs}`")
                df_sys_privs = get_user_sys_privs(conn, target_user_privs)
                st.dataframe(df_sys_privs, use_container_width=True, hide_index=True)

                # Conceder privilegio de sistema común
                st.markdown("##### ➕ Conceder Privilegio de Sistema")
                common_privs = [
                    "CREATE SESSION", "CREATE TABLE", "CREATE VIEW", "CREATE PROCEDURE",
                    "CREATE SEQUENCE", "CREATE TRIGGER", "CREATE SYNONYM", "UNLIMITED TABLESPACE",
                    "ALTER SYSTEM", "SELECT ANY TABLE", "DROP ANY TABLE"
                ]
                sel_sys_priv = st.selectbox("Privilegio del Sistema", common_privs)
                if st.button("Conceder Privilegio"):
                    try:
                        run_dml(conn, f"GRANT {sel_sys_priv} TO {target_user_privs}")
                        flash(f"Privilegio {sel_sys_priv} concedido a {target_user_privs}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al conceder privilegio: {e}")

        except Exception as e:
            st.error(f"Error en administración de roles: {e}")

    # 5. PERFILES DE SEGURIDAD
    with tab_profiles:
        st.subheader("Políticas de Contraseñas y Recursos (DBA_PROFILES)")
        st.caption("Configuración de bloqueo por intentos fallidos, caducidad de contraseñas y límites.")
        try:
            df_prof = get_profiles_summary(conn)
            st.dataframe(df_prof, use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("#### Configurar Parámetro de Perfil")
            with st.form("form_alter_profile"):
                cp1, cp2, cp3 = st.columns(3)
                with cp1:
                    prof_name_alt = st.selectbox("Perfil", prof_list)
                with cp2:
                    prof_param = st.selectbox("Parámetro", [
                        "FAILED_LOGIN_ATTEMPTS",
                        "PASSWORD_LIFE_TIME",
                        "PASSWORD_LOCK_TIME",
                        "PASSWORD_GRACE_TIME"
                    ])
                with cp3:
                    prof_val = st.text_input("Nuevo Valor (ej: 3, 90, UNLIMITED)", value="5")

                btn_alter_prof = st.form_submit_button("Modificar Perfil")

            if btn_alter_prof:
                try:
                    stmt_prof = f"ALTER PROFILE {prof_name_alt} LIMIT {prof_param} {prof_val}"
                    run_dml(conn, stmt_prof)
                    flash(f"Parámetro {prof_param} del perfil {prof_name_alt} cambiado a {prof_val}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al modificar perfil: {e}")

        except Exception as e:
            st.error(f"Error al consultar perfiles: {e}")

