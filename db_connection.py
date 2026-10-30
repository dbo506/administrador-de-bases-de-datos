"""
Módulo base para la gestión de conexiones a Oracle 21c Express Edition (XE).
Utiliza python-oracledb en modo Thin de forma nativa (sin requerir Oracle Instant Client).
"""

from typing import Any, Dict, Optional
import oracledb


def get_connection(
    user: str,
    password: str,
    dsn: Optional[str] = None,
    host: str = "localhost",
    port: int = 1521,
    service_name: str = "XEPDB1",
    is_sysdba: bool = False,
) -> oracledb.Connection:
    """
    Crea y retorna una conexión a la base de datos Oracle 21c XE en modo Thin.

    :param user: Nombre de usuario de Oracle (ej. 'sys', 'system', o usuario específico).
    :param password: Contraseña del usuario.
    :param dsn: DSN o cadena Easy Connect opcional (ej. 'localhost:1521/XEPDB1').
                Si no se proporciona, se construye a partir de host, port y service_name.
    :param host: Host o dirección IP de la base de datos (por defecto 'localhost').
    :param port: Puerto del listener de Oracle (por defecto 1521).
    :param service_name: Nombre del servicio Oracle ('XEPDB1' para PDB o 'XE' para CDB raíz).
    :param is_sysdba: Si es True, conecta con privilegios de administrador (oracledb.AUTH_MODE_SYSDBA).
    :return: Objeto oracledb.Connection activo.
    """
    target_dsn = dsn if dsn else f"{host}:{port}/{service_name}"

    conn_params = {
        "user": user,
        "password": password,
        "dsn": target_dsn,
    }

    if is_sysdba:
        conn_params["mode"] = oracledb.AUTH_MODE_SYSDBA

    # Modo Thin nativo de python-oracledb (sin inicializar el cliente pesado C)
    return oracledb.connect(**conn_params)


def test_connection(connection: oracledb.Connection) -> Dict[str, Any]:
    """
    Ejecuta una consulta de prueba en v$instance para verificar el estado del motor Oracle.

    :param connection: Conexión activa a Oracle.
    :return: Diccionario con instance_name, status y version.
    """
    query = "SELECT instance_name, status, version FROM v$instance"
    with connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("No se obtuvo información desde v$instance.")
        return {
            "instance_name": str(row[0]),
            "status": str(row[1]),
            "version": str(row[2]),
        }
