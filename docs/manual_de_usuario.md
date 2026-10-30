# Manual de Usuario - Administrador de Bases de Datos Oracle 21c XE
**Curso:** EIF-402 Administración de Bases de Datos  
**Institución:** Universidad Nacional de Costa Rica (UNA) - Sede Interuniversitaria de Alajuela  
**Docente:** MAP. Rodolfo Sánchez Sánchez  
**Versión del Sistema:** 1.0.0 (Oracle 21c XE / Python-Streamlit)

---

## 1. Introducción y Requisitos Previos

La aplicación **Oracle 21c XE DBA Manager** es una herramienta integral diseñada para la supervisión, mantenimiento preventivo, seguridad, afinamiento y ejecución de respaldos lógicos sobre el gestor relacional Oracle 21c Express Edition.

### Requisitos del Entorno:
1. **Motor de Base de Datos:** Oracle Database 21c Express Edition (XE) instalado y en ejecución en Windows (servicios `OracleServiceXE` y `OracleOraDB21Home1TNSListener` activos).
2. **Entorno de Ejecución:** Python 3.10 o superior con las dependencias del archivo `requirements.txt` (`oracledb`, `streamlit`, `pandas`, `plotly`).
3. **Herramientas de Respaldo:** Binarios `expdp.exe` e `impdp.exe` accesibles en la variable de entorno `PATH` del sistema.

### Instalación y Puesta en Marcha:
```powershell
# 1. Instalar librerías
pip install -r requirements.txt

# 2. Iniciar la aplicación
streamlit run app.py
```
La interfaz web se desplegará de forma automática en el navegador (por defecto en `http://localhost:8501`).

---

## 2. Autenticación y Conexión

Al iniciar la aplicación, se presenta la pantalla de autenticación con los parámetros necesarios:
* **Host / Dirección IP:** `localhost` (o IP del servidor de base de datos).
* **Puerto:** `1521` (puerto por defecto del listener de Oracle).
* **Servicio:** 
  * `XEPDB1`: Base de datos conectable (PDB). **Recomendada** para la administración de esquemas de negocio, tablas de aplicación y usuarios convencionales.
  * `XE`: Contenedor raíz (CDB$ROOT). Empleado para administración global de la instancia.
* **Usuario:** Usuario con privilegios administrativos (ej. `SYSTEM` o `SYS`).
* **Contraseña:** Contraseña configurada durante la instalación de Oracle.
* **Conectar como SYSDBA:** Marcar **únicamente** cuando se inicie sesión con el superusuario `SYS`. Para `SYSTEM`, mantener desmarcado.

Una vez autenticado, la sesión permanece activa en la barra lateral mientras el usuario navega entre los distintos módulos.

---

## 3. Guía de Operación por Módulos

### 3.1. Administración de Tablespaces y Datafiles
Permite gestionar la capa de almacenamiento físico y lógico:
* **Monitoreo General:** Visualización del tamaño total (MB), espacio usado, espacio libre y porcentaje de ocupación mediante gráficos de barras interactivas.
* **Crear Tablespace:** Asignación de nombre, tipo (`PERMANENT`, `TEMPORARY`, `UNDO`), tamaño inicial y configuración de autoextensión (`AUTOEXTEND ON NEXT ... MAXSIZE ...`).
* **Modificar / Estado:** Cambio del estado de disponibilidad (`ONLINE`, `OFFLINE NORMAL`, `OFFLINE IMMEDIATE`) y del modo de acceso (`READ WRITE`, `READ ONLY`).
* **Gestión de Datafiles:** Listado de archivos `.dbf`, incorporación de nuevos datafiles a tablespaces existentes y redimensionamiento dinámico (`RESIZE`).
* **Eliminar Tablespace:** Borrado seguro con confirmación explícita, incluyendo opciones `INCLUDING CONTENTS`, `AND DATAFILES` y `CASCADE CONSTRAINTS`.

### 3.2. Tuning de Consultas (Planes de Ejecución, Estadísticas e Índices)
Optimización del rendimiento de sentencias SQL y del Optimizador Basado en Costos (CBO):
* **Explain Plan:** Entrada de texto para sentencias SQL. Genera el plan de ejecución oficial vía `DBMS_XPLAN.DISPLAY`, además de una tabla jerárquica con el desglose de operaciones (`TABLE ACCESS FULL`, `INDEX RANGE SCAN`), costos, cardinalidad y predicados.
* **Estadísticas (DBMS_STATS):** Consulta de estadísticas vigentes de tablas (`DBA_TAB_STATISTICS`). Permite lanzar la recolección automática tanto a nivel de tabla individual como de esquema completo (`DBMS_STATS.GATHER_SCHEMA_STATS` con `CASCADE => TRUE`).
* **Gestión de Índices:** Inventario de índices clasificados por tipo (`B-Tree`, `UNIQUE`, `BITMAP`), estado (`VALID`, `UNUSABLE`) y nivel de árbol (`blevel`). Permite crear índices en una o múltiples columnas, reconstruirlos (`ALTER INDEX ... REBUILD ONLINE`) o eliminarlos.

### 3.3. Performance y Salud del Motor
Monitoreo de recursos en tiempo real:
* **Memoria (SGA / PGA):** Distribución de componentes (Buffer Cache, Shared Pool, Large Pool) y cálculo automático de los indicadores clave:
  * *Buffer Cache Hit Ratio:* Meta $\ge 90\%$ (minimiza accesos físicos a disco).
  * *Library Cache Hit Ratio:* Meta $\ge 95\%$ (reutilización eficiente de sentencias en la Shared Pool).
* **Sesiones de Usuarios:** Listado de conexiones activas e inactivas. Incluye la herramienta **Kill Session** (`ALTER SYSTEM KILL SESSION 'sid,serial#' IMMEDIATE`) para desconectar procesos anómalos.
* **Bloqueos (Lock Tree):** Detección inmediata de sesiones bloqueadoras que detienen la ejecución de otros usuarios, con botón de liberación inmediata.
* **Top SQL:** Ranking de las consultas que más consumen CPU, tiempo de ejecución, lecturas lógicas (Buffer Gets) o lecturas físicas de disco.

### 3.4. Auditoría de la Base de Datos
Control de cumplimiento y trazabilidad según el modelo de *Unified Auditing* de Oracle 21c:
* **Registros de Auditoría:** Explorador de `UNIFIED_AUDIT_TRAIL` con filtros por usuario, acción ejecutada (DDL/DML) y resultado (éxito vs. fallo).
* **Logins Fallidos:** Detección de intentos de intrusión o autenticaciones inválidas (`ORA-01017`, `ORA-28000`).
* **Políticas de Auditoría:** Consulta de políticas activas y asistente para crear y habilitar nuevas políticas unificadas (`CREATE AUDIT POLICY` / `AUDIT POLICY ...`).

### 3.5. Seguridad y Usuarios
Administración de identidades, privilegios y perfiles:
* **Directorio de Usuarios:** Listado de cuentas con estado (`OPEN`, `LOCKED`, `EXPIRED`), fecha de caducidad y tablespaces asignados.
* **Crear Usuario:** Creación de esquemas con contraseña, asignación de tablespaces, cuota de almacenamiento y roles iniciales (`CONNECT`, `RESOURCE`).
* **Mantenimiento:** Cambio de contraseñas, forzado de expiración en próximo inicio, bloqueo/desbloqueo de cuentas y eliminación en cascada (`DROP USER ... CASCADE`).
* **Roles y Privilegios:** Asignación y revocación de roles del sistema y privilegios de sistema (`CREATE TABLE`, `CREATE VIEW`, etc.).
* **Perfiles de Seguridad (DBA_PROFILES):** Configuración de políticas de contraseñas (`FAILED_LOGIN_ATTEMPTS`, `PASSWORD_LIFE_TIME`).

### 3.6. Respaldos y Recuperación (Oracle Data Pump)
Gestión de copias de seguridad lógicas mediante `expdp` e `impdp`:
* **Creación de Respaldos (Export):**
  * *Por Esquemas (Schemas):* Respalda uno o varios esquemas completos (estructuras y datos).
  * *Por Tablas:* Respalda tablas específicas seleccionadas interactivamente.
  * *Completo (Full):* Respaldo exhaustivo de toda la base de datos (`FULL=YES`).
  * *Opciones:* Directorio de destino, compresión (`ALL`, `DATA_ONLY`), sobrescritura (`REUSE_DUMPFILES`) y visualización de la consola en tiempo real.
* **Recuperación de Respaldos (Import):**
  * Detección automática de archivos `.dmp` en el directorio seleccionado.
  * Modos de importación: Schemas, Tablas o Full.
  * Manejo de conflictos: `TABLE_EXISTS_ACTION` (`REPLACE`, `TRUNCATE`, `APPEND`, `SKIP`).
  * Opciones avanzadas de reubicación: `REMAP_SCHEMA` (restaurar un esquema en otro usuario) y `REMAP_TABLESPACE`.

### 3.7. Directorios y Archivos de Respaldo
* **Gestor de Directorios:** Registro y eliminación de objetos `DIRECTORY` en Oracle (`CREATE OR REPLACE DIRECTORY ... AS '...'`).
* **Explorador del Sistema de Archivos:** Navegación por la carpeta física, tamaño de los volcados `.dmp`, visor de logs de Data Pump integrado en pantalla, descarga directa al cliente y eliminación de respaldos obsoletos.

---

## 4. Diagnóstico y Preguntas Frecuentes

| Error / Mensaje | Causa Común | Solución |
|---|---|---|
| **ORA-01017: invalid username/password** | Credenciales incorrectas o conexión como `SYS` sin marcar SYSDBA. | Verifique la contraseña o active la casilla "Conectar como SYSDBA". |
| **ORA-12541: TNS:no listener** | El servicio listener de Oracle no está en ejecución. | Inicie el servicio de Windows `OracleOraDB21Home1TNSListener`. |
| **ORA-12514: TNS:listener does not know of service** | El servicio `XEPDB1` no está abierto o no ha sido registrado. | Conecte primero a `XE` y verifique con `SHOW PDBS;` que `XEPDB1` esté en modo `READ WRITE`. |
| **ORA-39002 / ORA-39070 (Data Pump)** | El directorio especificado en Oracle no existe físicamente en el disco o faltan permisos. | Cree la carpeta física en Windows y verifique que el usuario tenga privilegios `READ, WRITE` sobre el objeto `DIRECTORY`. |
| **LRM-00118 en expdp** | Se pasaron parámetros con guiones (`-version`). | Data Pump utiliza sintaxis `KEYWORD=VALOR` o archivos de parámetros `parfile`, tal como lo gestiona esta aplicación internamente. |

