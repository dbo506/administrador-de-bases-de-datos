"""
Aplicación Principal de Administración y Respaldo de Base de Datos Oracle 21c XE.
EIF-402 Administración de Bases de Datos - Universidad Nacional (UNA).
"""

import streamlit as st
import oracledb
from db_connection import get_connection, test_connection
from modules.tablespaces import render_tablespaces
from modules.tuning import render_tuning
from modules.performance import render_performance
from modules.auditing import render_auditing
from modules.security import render_security
from modules.backup_restore import render_backup_restore
from modules.directories import render_directories

# Configuración inicial de la página
st.set_page_config(
    page_title="Oracle 21c XE - Administrador DBA",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados para mejorar la apariencia visual
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1e3a8a;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #64748b;
        margin-bottom: 1.5rem;
    }
    .stat-card {
        background-color: #f8fafc;
        border-radius: 8px;
        padding: 1rem;
        border: 1px solid #e2e8f0;
    }
    div[data-testid="stSidebarNav"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# Inicialización de variables en sesión
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "conn_params" not in st.session_state:
    st.session_state.conn_params = {}
if "instance_info" not in st.session_state:
    st.session_state.instance_info = {}


def get_active_db_connection():
    """
    Retorna la conexión activa a Oracle o reconecta automáticamente si la conexión cayó.
    """
    if not st.session_state.authenticated or not st.session_state.conn_params:
        return None

    params = st.session_state.conn_params
    try:
        conn = get_connection(
            user=params["user"],
            password=params["password"],
            host=params["host"],
            port=params["port"],
            service_name=params["service_name"],
            is_sysdba=params["is_sysdba"]
        )
        return conn
    except Exception as e:
        st.session_state.authenticated = False
        st.error(f"Error al restablecer la conexión con la base de datos: {e}")
        return None


# --- PANTALLA DE INICIO DE SESIÓN ---
def show_login_screen():
    st.markdown("<div class='main-header'>🗄️ Oracle 21c XE - Panel de Administración</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Proyecto Final - EIF-402 Administración de Bases de Datos (UNA)</div>", unsafe_allow_html=True)

    c1, c2 = st.columns([3, 2])
    with c1:
        with st.form("oracle_login_form"):
            st.subheader("Conexión al Motor Oracle")
            
            f1, f2 = st.columns(2)
            with f1:
                host = st.text_input("Host / Dirección IP", value="localhost")
                service_name = st.selectbox("Servicio Oracle", options=["XEPDB1", "XE"], index=0, help="XEPDB1 es la PDB conectable recomendada para usuarios y datos; XE es el CDB raíz.")
                user = st.text_input("Usuario DBA", value="system")
            with f2:
                port = st.number_input("Puerto Listener", min_value=1, max_value=65535, value=1521)
                is_sysdba = st.checkbox("Conectar como SYSDBA (Requerido para usuario 'SYS')", value=False)
                password = st.text_input("Contraseña", type="password")

            btn_login = st.form_submit_button("🔌 Conectar a la Base de Datos", use_container_width=True, type="primary")

        if btn_login:
            if not user or not password:
                st.warning("Debe ingresar tanto el usuario como la contraseña.")
            else:
                try:
                    with st.spinner("Estableciendo conexión con Oracle 21c XE..."):
                        temp_conn = get_connection(
                            user=user,
                            password=password,
                            host=host,
                            port=int(port),
                            service_name=service_name,
                            is_sysdba=is_sysdba
                        )
                        inst_info = test_connection(temp_conn)
                        temp_conn.close()

                    st.session_state.authenticated = True
                    st.session_state.conn_params = {
                        "user": user,
                        "password": password,
                        "host": host,
                        "port": int(port),
                        "service_name": service_name,
                        "is_sysdba": is_sysdba
                    }
                    st.session_state.instance_info = inst_info
                    st.success("¡Conexión establecida exitosamente!")
                    st.rerun()

                except oracledb.Error as db_err:
                    err, = db_err.args
                    st.error(f"Error de conexión Oracle [{getattr(err, 'code', 'N/A')}]: {getattr(err, 'message', str(db_err))}")
                except Exception as ex:
                    st.error(f"Error inesperado: {ex}")

    with c2:
        st.info("""
        ### Módulos del Sistema:
        * 💾 **Administración de Tablespaces** (Capacidad, creación, datafiles y drop).
        * ⚡ **Tuning de Consultas** (Explain Plan, `DBMS_STATS`, gestión de índices).
        * 📊 **Performance** (SGA/PGA, Hit Ratios, Bloqueos, Top SQL y Kill Session).
        * 🛡️ **Auditoría** (Unified Auditing, logins fallidos, creación de políticas).
        * 👥 **Seguridad de Usuarios** (Cuentas, roles, privilegios, perfiles).
        * 📦 **Respaldos y Recuperación** (Data Pump `expdp`/`impdp`: Schemas, Tablas, Full).
        * 📁 **Directorios y Archivos** (`DBA_DIRECTORIES`, visor de `.log`, descarga y limpieza).
        """)


# --- PANTALLA PRINCIPAL CON NAVEGACIÓN ---
def show_main_dashboard():
    info = st.session_state.instance_info
    params = st.session_state.conn_params

    # Barra lateral
    with st.sidebar:
        st.markdown(f"### 🗄️ Oracle 21c XE")
        st.caption(f"**Usuario:** `{params['user'].upper()}` {'(SYSDBA)' if params['is_sysdba'] else ''}")
        st.caption(f"**Instancia:** `{info.get('instance_name', 'XE')}` | **BD:** `{info.get('db_name', 'XE')}`")
        st.caption(f"**Servicio:** `{params['service_name']}` | **Host:** `{params['host']}:{params['port']}`")
        
        st.divider()

        menu_choice = st.radio(
            "Módulos del Sistema:",
            [
                "🏠 Inicio y Resumen",
                "💾 Tablespaces y Datafiles",
                "⚡ Tuning de Consultas",
                "📊 Performance y Salud",
                "🛡️ Auditoría de la BD",
                "👥 Seguridad y Usuarios",
                "📦 Respaldos y Restauración",
                "📁 Directorios y Archivos",
                "📖 Manual de Usuario"
            ]
        )

        st.divider()
        if st.button("🚪 Cerrar Sesión / Desconectar", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.conn_params = {}
            st.session_state.instance_info = {}
            st.rerun()

    # Obtener conexión activa
    conn = get_active_db_connection()
    if conn is None:
        return

    try:
        if menu_choice == "🏠 Inicio y Resumen":
            render_home_dashboard(conn, info, params)
        elif menu_choice == "💾 Tablespaces y Datafiles":
            render_tablespaces(conn)
        elif menu_choice == "⚡ Tuning de Consultas":
            render_tuning(conn)
        elif menu_choice == "📊 Performance y Salud":
            render_performance(conn)
        elif menu_choice == "🛡️ Auditoría de la BD":
            render_auditing(conn)
        elif menu_choice == "👥 Seguridad y Usuarios":
            render_security(conn)
        elif menu_choice == "📦 Respaldos y Restauración":
            render_backup_restore(conn, params)
        elif menu_choice == "📁 Directorios y Archivos":
            render_directories(conn)
        elif menu_choice == "📖 Manual de Usuario":
            render_user_manual()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def render_home_dashboard(conn, info, params):
    st.markdown("<div class='main-header'>🏠 Panel General de la Base de Datos</div>", unsafe_allow_html=True)
    st.caption("Visión global del motor Oracle 21c Express Edition y accesos directos de administración.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Estado de la Instancia", info.get("status", "OPEN"))
    m2.metric("Modo de Apertura", info.get("open_mode", "READ WRITE"))
    m3.metric("Modo Log", info.get("log_mode", "NOARCHIVELOG"))
    m4.metric("Versión Oracle", info.get("version", "21c"))

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Detalles del Servidor e Instancia")
        st.write(f"- **Nombre de Instancia:** `{info.get('instance_name', 'N/A')}`")
        st.write(f"- **Nombre de Base de Datos:** `{info.get('db_name', 'N/A')}`")
        st.write(f"- **Nombre del Host:** `{info.get('host_name', 'N/A')}`")
        st.write(f"- **Fecha y Hora de Arranque:** `{info.get('startup_time', 'N/A')}`")
        st.write(f"- **Servicio de Conexión Activo:** `{params.get('service_name', 'N/A')}`")
        st.write(f"- **Usuario Administrador:** `{params.get('user', 'N/A')}`")

    with col_b:
        st.subheader("Atajos Rápidos")
        st.info("""
        Seleccione una opción en el menú lateral izquierdo para comenzar a operar:
        - Para revisar espacio libre o crear un tablespace: **💾 Tablespaces y Datafiles**.
        - Para analizar una consulta pesada o crear índices: **⚡ Tuning de Consultas**.
        - Para inspeccionar el consumo de memoria o sesiones bloqueadas: **📊 Performance y Salud**.
        - Para auditar acciones o logins erróneos: **🛡️ Auditoría de la BD**.
        - Para gestionar cuentas de usuario y permisos: **👥 Seguridad y Usuarios**.
        - Para generar respaldos de esquemas, tablas o full: **📦 Respaldos y Restauración**.
        - Para consultar logs o descargar dumpfiles: **📁 Directorios y Archivos**.
        """)


def render_user_manual():
    st.header("📖 Manual de Usuario del Sistema")
    st.caption("Guía de operación y referencia técnica del Administrador de Base de Datos Oracle 21c XE.")

    try:
        with open("docs/manual_de_usuario.md", "r", encoding="utf-8") as f:
            manual_text = f.read()
        st.markdown(manual_text)
    except Exception as e:
        st.info("El manual de usuario detallado se encuentra en la carpeta `docs/manual_de_usuario.md`.")


# Punto de entrada
if __name__ == "__main__":
    if not st.session_state.authenticated:
        show_login_screen()
    else:
        show_main_dashboard()
