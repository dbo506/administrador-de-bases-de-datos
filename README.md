# Administrador de Bases de Datos Oracle

Aplicación web hecha con **Python** y **Streamlit** para administrar una base de datos **Oracle 21c XE** desde una interfaz gráfica.

## Partes del sistema

- **Inicio y conexión:** permite conectarse a Oracle y muestra información general de la instancia.
- **Tablespaces y datafiles:** consulta el espacio utilizado y permite crear, modificar y eliminar tablespaces y administrar sus archivos de datos.
- **Tuning de consultas:** permite revisar planes de ejecución, gestionar estadísticas y administrar índices para apoyar el análisis y ajuste de consultas.
- **Rendimiento y salud:** muestra métricas de memoria y actividad, sesiones, bloqueos y consultas SQL de mayor costo.
- **Auditoría:** permite consultar registros e intentos fallidos de inicio de sesión, además de administrar políticas de auditoría.
- **Seguridad y usuarios:** permite administrar cuentas, perfiles, roles y privilegios de Oracle.
- **Respaldos y restauración:** crea y restaura respaldos por esquema, tabla o de la base de datos completa mediante Oracle Data Pump.
- **Directorios y archivos:** administra directorios de Oracle y permite explorar archivos de respaldo y registros.

## Cómo correrlo

### Requisitos

- Python 3.10 o superior.
- Oracle 21c XE en ejecución.
- `expdp` e `impdp` disponibles en el `PATH` para utilizar respaldos y restauraciones.

### Pasos

1. Abre una terminal en la carpeta del proyecto.
2. Instala las dependencias:

   ```powershell
   pip install -r requirements.txt
   ```

3. Ejecuta la aplicación:

   ```powershell
   streamlit run app.py
   ```

4. Abre [http://localhost:8501](http://localhost:8501) en el navegador e inicia sesión con tus credenciales de Oracle.
