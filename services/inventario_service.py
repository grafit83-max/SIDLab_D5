# services/inventario_service.py
# ─────────────────────────────────────────────────────────────────────
# Servicio CRUD para la tabla inventario.
# Sigue exactamente el mismo patrón que bitacora_service.py:
#   get_connection() de database.database, cursores psycopg2,
#   placeholders %s para PostgreSQL.
# ─────────────────────────────────────────────────────────────────────
import pandas as pd
import warnings
from datetime import datetime

from database.database import get_connection

# ── Valores permitidos (para validación en la vista) ─────────────────
ESTADOS_VALIDOS    = ["BUENO", "REGULAR", "MALO"]
CATEGORIAS_VALIDAS = [
    "CABLES",
    "CESTOS DE BASURA",
    "EQUIPO DE TELECOMUNICACIONES",
    "EQUIPOS AUDIO VISUALES",
    "EQUIPOS DE COMPUTO",
    "EQUIPOS DE ENERGÍA",
    "MESAS",
    "MOBILIARIO Y EQUIPO DE AULAS",
    "MOBILIARIO Y EQUIPO DE LABORATORIOS",
    "MOBILIARIO Y EQUIPO DE OFICINAS",
    "OTRA",
]
LABORATORIOS_INV = [
    "104", "104_RACK",
    "204", "204_RACK", "204_V22",
    "211",
    "212", "212_NOK", "212_RACK",
    "202_RACK",
    "ALMACEN",
    "N/A",
]


# ── LECTURA ───────────────────────────────────────────────────────────

def get_inventario(
    laboratorio: str | None = None,
    categoria: str | None = None,
    estado: str | None = None,
    busqueda: str | None = None,
    solo_activos: bool = True,
) -> pd.DataFrame:
    """
    Devuelve el inventario filtrado como DataFrame.
    Todos los parámetros son opcionales — sin filtros devuelve todos los registros activos.
    """
    conn = get_connection()
    condiciones = []
    params = []

    if solo_activos:
        condiciones.append("activo = TRUE")

    if laboratorio:
        condiciones.append("laboratorio = %s")
        params.append(laboratorio)

    if categoria:
        condiciones.append("categoria = %s")
        params.append(categoria)

    if estado:
        condiciones.append("estado = %s")
        params.append(estado)

    if busqueda and busqueda.strip():
        condiciones.append(
            "(descripcion ILIKE %s OR marca ILIKE %s OR serie ILIKE %s OR num_inventario ILIKE %s)"
        )
        term = f"%{busqueda.strip()}%"
        params.extend([term, term, term, term])

    where = "WHERE " + " AND ".join(condiciones) if condiciones else ""
    sql = f"SELECT * FROM inventario {where} ORDER BY laboratorio, categoria, descripcion"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        df = pd.read_sql_query(sql, conn, params=params if params else None)
    conn.close()
    return df


def get_item_por_id(item_id: int) -> dict | None:
    """Devuelve un registro completo por ID, o None si no existe."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM inventario WHERE id = %s", (item_id,))
    row = c.fetchone()
    if row is None:
        conn.close()
        return None
    cols = [desc[0] for desc in c.description]
    conn.close()
    return dict(zip(cols, row))


def get_resumen_por_laboratorio() -> pd.DataFrame:
    """KPIs agrupados por laboratorio: total, buenos, regulares, malos."""
    conn = get_connection()
    sql = """
        SELECT
            laboratorio,
            COUNT(*)                                          AS total,
            COUNT(*) FILTER (WHERE estado = 'BUENO')         AS buenos,
            COUNT(*) FILTER (WHERE estado = 'REGULAR')       AS regulares,
            COUNT(*) FILTER (WHERE estado = 'MALO')          AS malos
        FROM inventario
        WHERE activo = TRUE
        GROUP BY laboratorio
        ORDER BY laboratorio
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        df = pd.read_sql_query(sql, conn)
    conn.close()
    return df


# ── ESCRITURA ─────────────────────────────────────────────────────────

def agregar_item(
    descripcion: str,
    marca: str | None,
    serie: str | None,
    estado: str,
    modelo: str | None,
    num_inventario: str | None,
    laboratorio: str,
    categoria: str,
    caracteristicas: str | None,
    usuario: str,
) -> tuple[bool, str]:
    """
    Inserta un nuevo item en el inventario.
    Returns (éxito: bool, mensaje: str).
    """
    if not descripcion.strip():
        return False, "La descripción es obligatoria."
    if estado not in ESTADOS_VALIDOS:
        return False, f"Estado inválido. Debe ser: {', '.join(ESTADOS_VALIDOS)}."

    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO inventario
                (descripcion, marca, serie, estado, modelo, num_inventario,
                 laboratorio, categoria, caracteristicas, creado_por, fecha_creacion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            descripcion.strip(),
            marca.strip() if marca else None,
            serie.strip() if serie else None,
            estado,
            modelo.strip() if modelo else None,
            num_inventario.strip() if num_inventario else None,
            laboratorio,
            categoria,
            caracteristicas.strip() if caracteristicas else None,
            usuario,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
        ))
        nuevo_id = c.fetchone()[0]
        conn.commit()
        conn.close()
        return True, f"Item agregado correctamente (ID #{nuevo_id})."
    except Exception as e:
        return False, f"Error al agregar: {e}"


def modificar_item(
    item_id: int,
    descripcion: str,
    marca: str | None,
    serie: str | None,
    estado: str,
    modelo: str | None,
    num_inventario: str | None,
    laboratorio: str,
    categoria: str,
    caracteristicas: str | None,
    usuario: str,
) -> tuple[bool, str]:
    """
    Actualiza un item existente.
    Returns (éxito: bool, mensaje: str).
    """
    if not descripcion.strip():
        return False, "La descripción es obligatoria."
    if estado not in ESTADOS_VALIDOS:
        return False, f"Estado inválido. Debe ser: {', '.join(ESTADOS_VALIDOS)}."

    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            UPDATE inventario SET
                descripcion        = %s,
                marca              = %s,
                serie              = %s,
                estado             = %s,
                modelo             = %s,
                num_inventario     = %s,
                laboratorio        = %s,
                categoria          = %s,
                caracteristicas    = %s,
                modificado_por     = %s,
                fecha_modificacion = %s
            WHERE id = %s
        """, (
            descripcion.strip(),
            marca.strip() if marca else None,
            serie.strip() if serie else None,
            estado,
            modelo.strip() if modelo else None,
            num_inventario.strip() if num_inventario else None,
            laboratorio,
            categoria,
            caracteristicas.strip() if caracteristicas else None,
            usuario,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            item_id,
        ))
        afectados = c.rowcount
        conn.commit()
        conn.close()
        if afectados == 0:
            return False, f"No se encontró el item ID #{item_id}."
        return True, f"Item ID #{item_id} actualizado correctamente."
    except Exception as e:
        return False, f"Error al modificar: {e}"


def eliminar_item(item_id: int, usuario: str) -> tuple[bool, str]:
    """
    Eliminación lógica (activo = FALSE) — el registro no se borra físicamente.
    Returns (éxito: bool, mensaje: str).
    """
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            UPDATE inventario SET
                activo             = FALSE,
                modificado_por     = %s,
                fecha_modificacion = %s
            WHERE id = %s AND activo = TRUE
        """, (usuario, datetime.now().strftime("%Y-%m-%d %H:%M"), item_id))
        afectados = c.rowcount
        conn.commit()
        conn.close()
        if afectados == 0:
            return False, f"No se encontró el item ID #{item_id} o ya estaba inactivo."
        return True, f"Item ID #{item_id} eliminado del inventario."
    except Exception as e:
        return False, f"Error al eliminar: {e}"
