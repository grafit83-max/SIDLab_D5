# database/init_db.py
from database.database import get_connection
from utils.seguridad import hashear_pwd

def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Tabla principal de bitácora
    # Cambio a PostgreSQL: Usar SERIAL en lugar de AUTOINCREMENT
    c.execute('''
        CREATE TABLE IF NOT EXISTS bitacora (
            id               SERIAL PRIMARY KEY,
            fecha            TEXT NOT NULL,
            turno            TEXT,
            laboratorio      TEXT,
            entrada          TEXT,
            salida           TEXT,
            grado_grupo      TEXT,
            no_alum          INTEGER,
            asignatura       TEXT,
            tema             TEXT,
            nombre_profesor  TEXT,
            num_empleado     TEXT,
            firma_hash       TEXT,
            firma_jefe_grupo TEXT,
            observaciones    TEXT,
            tiene_falla      INTEGER DEFAULT 0,
            analisis_obs     TEXT,
            editado          INTEGER DEFAULT 0,
            editado_por      TEXT,
            fecha_edicion    TEXT
        )
    ''')

    # Tabla de usuarios
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            num_empleado     TEXT PRIMARY KEY,
            nombre           TEXT,
            password_hash    TEXT,
            requiere_cambio  INTEGER DEFAULT 1,
            activo           INTEGER DEFAULT 1
        )
    ''')

    # Tabla de auditoría de sesiones
    # Cambio a PostgreSQL: Usar SERIAL en lugar de AUTOINCREMENT
    c.execute('''
        CREATE TABLE IF NOT EXISTS auditoria (
            id           SERIAL PRIMARY KEY,
            timestamp    TEXT,
            usuario      TEXT,
            num_empleado TEXT,
            accion       TEXT,
            detalle      TEXT,
            ip_hint      TEXT
        )
    ''')

    conn.commit()
    conn.close()

def migrar_db():
    """
    Migración de esquema.
    Al iniciar con PostgreSQL desde cero, el esquema ya nace con la v2.0.
    Por lo tanto, no es necesario ejecutar sentencias PRAGMA o ALTER TABLE iniciales.
    """
    pass