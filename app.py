"""
Punto de entrada mínimo para probar la conexión a Oracle 21c XE mediante Streamlit.
"""

import streamlit as st
import oracledb
from db_connection import get_connection, test_connection

st.set_page_config(
    page_title="Oracle 21c XE - Conexión Base",
    page_icon="🔌",
    layout="centered"
)

st.title("🔌 Oracle 21c XE - Prueba de Conexión")
st.caption("Verificación de conectividad con python-oracledb (Modo Thin).")

with st.form("oracle_connection_form"):
    st.subheader("Parámetros de Conexión")
    
    col1, col2 = st.columns(2)
    with col1:
        host = st.text_input("Host", value="localhost")
        service_name = st.selectbox("Servicio", options=["XEPDB1", "XE"], index=0)
        user = st.text_input("Usuario", value="system")
    with col2:
        port = st.number_input("Puerto", min_value=1, max_value=65535, value=1521)
        is_sysdba = st.checkbox("Conectar como SYSDBA", value=False)
        password = st.text_input("Contraseña", type="password")

    submit_button = st.form_submit_button("Probar Conexión", use_container_width=True)

if submit_button:
    if not user or not password:
        st.warning("Por favor ingresa tanto el usuario como la contraseña.")
    else:
        conn = None
        try:
            with st.spinner("Conectando a Oracle 21c XE..."):
                conn = get_connection(
                    user=user,
                    password=password,
                    host=host,
                    port=int(port),
                    service_name=service_name,
                    is_sysdba=is_sysdba
                )
                instance_info = test_connection(conn)

            st.success("¡Conexión establecida exitosamente con Oracle 21c XE!")
            
            st.markdown("### Información de la Instancia")
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Instancia", instance_info["instance_name"])
            col_b.metric("Estado", instance_info["status"])
            col_c.metric("Versión", instance_info["version"])

        except oracledb.Error as db_err:
            error_obj, = db_err.args
            st.error("Error al conectar con Oracle:")
            st.code(f"Código: {getattr(error_obj, 'code', 'N/A')}\nMensaje: {getattr(error_obj, 'message', str(db_err))}", language="text")
        except Exception as ex:
            st.error(f"Error inesperado: {ex}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
