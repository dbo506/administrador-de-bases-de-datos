# Administrador de Bases de Datos Oracle 21c XE

Proyecto final del curso **EIF-402 Administración de Bases de Datos**, Universidad Nacional (UNA), Sede Interuniversitaria de Alajuela.
Docente: MAP. Rodolfo Sánchez Sánchez.

Aplicación web (Python + Streamlit) para administrar Oracle 21c XE y ejecutar respaldos con Data Pump.

**Entrega y demo:** 4 de noviembre de 2026 (semana 15, en el laboratorio).

---

## Estado del proyecto

Última actualización: 1 de noviembre de 2026.

| Requisito del enunciado | Estado | Módulo |
|---|---|---|
| Administración de tablespaces | ✅ Implementado | `modules/tablespaces.py` |
| Tuning de consultas (planes, estadísticas, índices) | ✅ Implementado | `modules/tuning.py` |
| Performance de la base de datos | ✅ Implementado | `modules/performance.py` |
| Auditoría de la BD | ✅ Implementado | `modules/auditing.py` |
| Seguridad de usuarios | ✅ Implementado | `modules/security.py` |
| Respaldos por Schemas / Tablas / Full | ✅ Implementado | `modules/backup_restore.py` |
| Recuperación de respaldos | ✅ Implementado | `modules/backup_restore.py` |
| Administración de archivos de respaldo y directorios | ✅ Implementado | `modules/directories.py` |
| Manual de usuario (máx. 4 páginas) | ⚠️ Borrador en Markdown | `docs/manual_de_usuario.md` |

### Pendiente antes de la entrega

- [ ] Probar cada módulo contra Oracle 21c XE real (funcionalidad = 70% de la nota).
- [ ] Confirmar que `expdp` e `impdp` están en el `PATH` de la máquina del laboratorio.
- [ ] Verificar los privilegios de auditoría (`AUDIT_VIEWER` / `AUDIT_ADMIN`) del usuario que se usará en la demo.
- [ ] Pasar el manual a PDF, con capturas de pantalla, en 4 páginas como máximo.
- [ ] Corregir en el manual: dice `DBA_TAB_STATISTICS`, pero el código usa `ALL_TAB_STATISTICS`.

### Cambios recientes

- Los mensajes de éxito ahora se ven después de cada acción (antes `st.rerun()` los borraba). Ver `flash()` en `modules/common.py`.
- La restauración (impdp) por esquemas y por tablas ahora genera `SCHEMAS=` / `TABLES=` (antes solo funcionaba Full).
- Corregido el cálculo del espacio libre en tablespaces temporales.
- Al crear un índice, las columnas se actualizan al cambiar de tabla.
- Barra de herramientas de Streamlit en modo mínimo (`.streamlit/config.toml`).

---

## Funcionalidades por módulo

- **💾 Tablespaces y Datafiles:** monitoreo de uso con gráficos; crear tablespaces (permanent, temporary, undo); cambiar estado (online/offline) y modo (read only/write); agregar y redimensionar datafiles; eliminar con confirmación.
- **⚡ Tuning:** Explain Plan con `DBMS_XPLAN`; ver y recolectar estadísticas con `DBMS_STATS` (por tabla o por esquema); listar, crear (B-Tree, Unique, Bitmap), reconstruir y eliminar índices.
- **📊 Performance:** memoria SGA/PGA, hit ratios, sesiones con opción de kill, bloqueos y Top SQL.
- **🛡️ Auditoría:** consulta de `UNIFIED_AUDIT_TRAIL` con filtros, logins fallidos, crear, deshabilitar y eliminar políticas de auditoría.
- **👥 Seguridad:** crear, modificar, bloquear/desbloquear y eliminar usuarios; otorgar y revocar roles y privilegios; modificar perfiles.
- **📦 Respaldos y Restauración:** `expdp` por esquemas, tablas o full; `impdp` con `TABLE_EXISTS_ACTION`, `REMAP_SCHEMA` y `REMAP_TABLESPACE`.
- **📁 Directorios y Archivos:** crear y eliminar objetos `DIRECTORY`; explorar archivos, ver logs, descargar y borrar respaldos.

---

## Requisitos

- Oracle Database 21c Express Edition en ejecución (servicio `XEPDB1` o `XE`).
- Python 3.10 o superior.
- `expdp` y `impdp` accesibles en el `PATH` (para el módulo de respaldos).

## Instalación y ejecución

```powershell
pip install -r requirements.txt
streamlit run app.py
```

La aplicación abre en `http://localhost:8501`. Conectarse con `SYSTEM` (o con `SYS` marcando "Conectar como SYSDBA").

## Estructura

```
app.py                  # Login, menú lateral y pantalla de inicio
db_connection.py        # Conexión a Oracle (oracledb)
modules/
  common.py             # Ejecución de consultas y mensajes (flash)
  tablespaces.py
  tuning.py
  performance.py
  auditing.py
  security.py
  backup_restore.py
  directories.py
docs/manual_de_usuario.md
.streamlit/config.toml
```
