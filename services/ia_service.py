# services/ia_service.py
import json
import urllib.request
import pandas as pd
import warnings
from datetime import date

from database.database import get_connection
from config.settings import LABORATORIOS, TURNOS
from services.dashboard_service import get_ocupacion_actual

# ─────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DEL MODELO — cambia esta línea para probar otro modelo
# ─────────────────────────────────────────────────────────────────────
# "llama3.2"     → más preciso, más lento en CPU sin GPU (recomendado si tienes 16GB+ RAM libre)
# "llama3.2:1b"  → ~3x más rápido, algo menos preciso en SQL complejo (recomendado para tu hardware: 10GB RAM, i5 sin GPU)
OLLAMA_MODEL = "llama3.2"          # <-- cambia a "llama3.2:1b" si sigue lento

OLLAMA_TIMEOUT_SEGUNDOS = 180      # subido de 120 a 180 como colchón de seguridad


def obtener_esquema_bd() -> str:
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'bitacora';
    """)
    columnas = [row[0] for row in c.fetchall()]

    c.execute("SELECT COUNT(*) FROM bitacora")
    total = c.fetchone()[0]

    c.execute("SELECT MIN(fecha), MAX(fecha) FROM bitacora")
    rango = c.fetchone()

    c.execute("SELECT laboratorio, COUNT(*) as n FROM bitacora GROUP BY laboratorio ORDER BY n DESC")
    por_lab = c.fetchall()

    c.execute("SELECT COUNT(*) FROM bitacora WHERE tiene_falla = 1")
    total_fallas = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT num_empleado) FROM bitacora")
    total_profs = c.fetchone()[0]

    conn.close()

    labs_txt = ", ".join([f"Lab {l}: {n}" for l, n in por_lab]) if por_lab else "Sin datos"
    return (
        f"Tabla: bitacora (PostgreSQL)\n"
        f"Columnas: {', '.join(columnas)}\n"
        f"Total registros: {total} | Rango fechas: {rango[0]} a {rango[1]}\n"
        f"Por laboratorio: {labs_txt}\n"
        f"Fallas: {total_fallas} | Profesores distintos: {total_profs}\n"
        f"Labs válidos: {', '.join(LABORATORIOS)}\n"
        f"Turnos válidos: {', '.join(TURNOS)}"
    )


def ejecutar_sql_seguro(sql: str) -> tuple[pd.DataFrame | None, str | None]:
    # Marcador especial: la pregunta de "ocupación actual" no usa SQL real,
    # se resuelve con get_ocupacion_actual() — misma fuente que el sidebar.
    if sql == "__OCUPACION_ACTUAL__":
        return _construir_df_ocupacion_actual(), None

    sql_limpio = sql.strip().rstrip(";")
    primera_palabra = sql_limpio.split()[0].upper() if sql_limpio else ""

    if primera_palabra != "SELECT":
        return None, "Solo se permiten consultas SELECT sobre la base de datos."

    palabras_peligrosas = [
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
        "TRUNCATE", "COPY", "GRANT", "REVOKE"
    ]

    sql_upper = sql_limpio.upper()
    for palabra in palabras_peligrosas:
        if f" {palabra} " in f" {sql_upper} ":
            return None, f"Consulta rechazada: contiene operación no permitida ({palabra})."

    try:
        conn = get_connection()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            df = pd.read_sql_query(sql_limpio, conn)
        conn.close()
        return df, None
    except Exception as e:
        return None, f"Error al ejecutar la consulta en PostgreSQL: {e}"


# ─────────────────────────────────────────────────────────────────────
# DETECCIÓN DE SALUDOS / FUERA DE TEMA — resuelta en código, no en el modelo
# ─────────────────────────────────────────────────────────────────────
# En vez de dejar que el modelo "decida" si la pregunta necesita SQL
# (lo cual fallaba con frecuencia en llama3.2, respondiendo "tipo: texto"
# para preguntas reales de datos), forzamos la decisión aquí: solo se
# trata como saludo/charla si NO contiene ninguna palabra relacionada
# con la bitácora. Para cualquier otra cosa, SIEMPRE se genera SQL.
PALABRAS_CLAVE_DATOS = [
    "profesor", "profesora", "maestro", "maestra", "docente",
    "laboratorio", "lab", "sesion", "sesión", "registro",
    "asignatura", "tema", "grupo", "grado", "alumno",
    "falla", "fallas", "turno", "fecha", "hora",
    "cuant", "cuál", "cual", "quien", "quién", "que", "qué",
    "lista", "listame", "muestra", "muéstrame", "dame", "top", "mas", "más",
]


def _es_saludo_o_fuera_de_tema(pregunta: str) -> bool:
    """True solo si la pregunta no contiene ninguna palabra relacionada con datos."""
    texto = pregunta.lower()
    return not any(palabra in texto for palabra in PALABRAS_CLAVE_DATOS)


# ─────────────────────────────────────────────────────────────────────
# DETECCIÓN DE "OCUPACIÓN ACTUAL" — resuelta con función Python, no SQL
# ─────────────────────────────────────────────────────────────────────
# Comparar la hora actual contra entrada/salida como strings es algo
# que un modelo pequeño (llama3.2) no maneja de forma confiable: en las
# pruebas generó siempre el mismo SQL (filtro de "sin salida") sin
# distinguir "en uso ahora" de "sin salida registrada". En vez de seguir
# ajustando el prompt para un caso tan específico, reutilizamos la
# función get_ocupacion_actual() que ya usa el sidebar de la app —
# misma lógica, un solo lugar de verdad, resultado 100% confiable.
PALABRAS_OCUPACION_ACTUAL = [
    "en uso", "en uso ahora", "ocupado", "ocupados", "ocupación", "ocupacion",
    "sesión activa", "sesion activa", "activo ahora", "activos ahora",
    "ahora mismo", "en este momento", "en curso",
]


def _es_pregunta_ocupacion_actual(pregunta: str) -> bool:
    texto = pregunta.lower()
    return any(frase in texto for frase in PALABRAS_OCUPACION_ACTUAL)


def _construir_df_ocupacion_actual() -> pd.DataFrame:
    """Construye el DataFrame de ocupación actual usando la fuente única de verdad
    (la misma función que usa el sidebar de la app)."""
    ocupacion = get_ocupacion_actual()
    if not ocupacion:
        return pd.DataFrame(columns=["Laboratorio", "Profesor", "Entrada", "Salida"])

    filas = [
        {"Laboratorio": lab, "Profesor": info["profesor"], "Entrada": info["entrada"], "Salida": info["salida"]}
        for lab, info in ocupacion.items()
    ]
    return pd.DataFrame(filas)


def _responder_ocupacion_actual() -> tuple[str, pd.DataFrame]:
    """Texto + DataFrame listos para mostrar, sin pasar por SQL ni por el modelo."""
    df = _construir_df_ocupacion_actual()
    if df.empty:
        return "Ningún laboratorio está en uso en este momento.", df
    return "Laboratorios actualmente en uso:", df


def consultar_ia(pregunta: str, historial: list) -> tuple[str, str | None]:
    # Atajo 1: saludos no necesitan llamar al modelo para nada
    if _es_saludo_o_fuera_de_tema(pregunta):
        return (
            "¡Hola! Pregúntame sobre profesores, laboratorios, sesiones o fallas "
            "registradas en la bitácora. Por ejemplo: \"¿Qué profesor usó más el Lab 204?\"",
            None,
        )

    # Atajo 2: ocupación actual — resuelto con función Python, no con el modelo.
    # En vez de devolver SQL, devolvemos un "pseudo-SQL" especial que
    # ejecutar_sql_seguro() reconoce y resuelve sin tocar PostgreSQL —
    # así no hay que cambiar la firma de la función ni pages/ia.py.
    if _es_pregunta_ocupacion_actual(pregunta):
        texto, _ = _responder_ocupacion_actual()
        return texto, "__OCUPACION_ACTUAL__"

    esquema = obtener_esquema_bd()
    hoy = date.today()
    hoy_str = hoy.strftime("%Y-%m-%d")
    inicio_mes_str = hoy.replace(day=1).strftime("%Y-%m-%d")

    # ── Prompt con una sola tarea: SIEMPRE generar SQL ───────────────────
    # Ya no se le da al modelo la opción de "tipo: texto" para preguntas
    # de datos — eso eliminaba la ambigüedad que causaba que respondiera
    # con resúmenes de memoria en vez de consultar la tabla real.
    # Las fechas relativas ("hoy", "este mes") se resuelven aquí en Python,
    # no se le pide al modelo que calcule fechas — los modelos pequeños
    # fallan calculando rangos de mes/semana de forma consistente.
    system_prompt = f"""Traduces preguntas en español a UNA consulta SQL de PostgreSQL sobre la tabla "bitacora". Respondes SOLO JSON, sin texto adicional, sin explicaciones fuera del JSON.

Formato exacto y único permitido:
{{"sql": "SELECT ...", "explicacion": "..."}}

Reglas:
- SIEMPRE genera SQL. Nunca dejes "sql" vacío ni respondas otra cosa que no sea este JSON.
- Comillas simples para valores de texto en el SQL (nunca dobles).
- Nunca uses DROP, DELETE, UPDATE, INSERT, ALTER, CREATE.
- Agrega LIMIT 50 (o LIMIT 5 si es un "top"/"más"/"usó más").
- Para "hoy" usa fecha = '{hoy_str}'.
- Para "este mes" usa fecha >= '{inicio_mes_str}' AND fecha <= '{hoy_str}'.
- Nunca uses CURRENT_DATE, NOW() ni calcules fechas tú mismo — usa solo las fechas ya escritas arriba.
- laboratorio guarda solo el número como texto, ej: '204' (nunca escribas la palabra "Lab").
- Para comparar texto (turno, asignatura, nombre_profesor) usa ILIKE '%valor%', nunca el signo =.
- Si piden "todos los registros" o "muéstrame todo": SELECT * FROM bitacora ORDER BY fecha DESC LIMIT 50.
- "Sesión activa" o "laboratorio en uso ahora" significa: entrada registrada pero salida vacía (sin registrar). Usa SIEMPRE: WHERE fecha = '{hoy_str}' AND (salida IS NULL OR salida = ''). La columna "editado" NO tiene relación con sesiones activas — esa columna solo indica si un admin corrigió el registro después, nunca la uses para preguntas de "activo" o "en uso".

DOS PATRONES DE SQL — NUNCA LOS MEZCLES:
PATRÓN A — "qué profesores", "lista", "nombres", "quiénes", "qué asignatura" (solo listar, sin contar):
  SELECT DISTINCT <columna> FROM bitacora WHERE <condición> LIMIT 50
  (en este patrón NUNCA agregues GROUP BY ni ORDER BY COUNT)

PATRÓN B — "quién usó más", "cuántos", "top", "más veces" (contar y ordenar):
  SELECT <columna>, COUNT(*) as total FROM bitacora WHERE <condición> GROUP BY <columna> ORDER BY total DESC LIMIT 5
  (en este patrón NUNCA uses DISTINCT, siempre incluye "AS total" y ordena por esa columna, no por COUNT(*))

Ejemplos:
Pregunta: "Que profesores tomaron sesiones en el turno vespertino"
{{"sql": "SELECT DISTINCT nombre_profesor FROM bitacora WHERE turno ILIKE '%vespertino%' LIMIT 50", "explicacion": "Estos son los profesores con sesiones en turno vespertino:"}}

Pregunta: "Qué asignatura se imparte en el Lab 211"
{{"sql": "SELECT DISTINCT asignatura FROM bitacora WHERE laboratorio = '211' LIMIT 50", "explicacion": "Asignaturas impartidas en el Lab 211:"}}

Pregunta: "Muestrame todos los registros"
{{"sql": "SELECT * FROM bitacora ORDER BY fecha DESC LIMIT 50", "explicacion": "Aquí están los registros más recientes:"}}

Pregunta: "Qué profesor usó más el Lab 104 este mes"
{{"sql": "SELECT nombre_profesor, COUNT(*) as total FROM bitacora WHERE laboratorio = '104' AND fecha >= '{inicio_mes_str}' AND fecha <= '{hoy_str}' GROUP BY nombre_profesor ORDER BY total DESC LIMIT 5", "explicacion": "Profesores que más usaron el Lab 104 este mes:"}}

Pregunta: "Cuántas sesiones hubo hoy"
{{"sql": "SELECT COUNT(*) as total FROM bitacora WHERE fecha = '{hoy_str}'", "explicacion": "Total de sesiones de hoy:"}}

Pregunta: "Qué laboratorio está en sesión activa"
{{"sql": "SELECT laboratorio, nombre_profesor, entrada FROM bitacora WHERE fecha = '{hoy_str}' AND (salida IS NULL OR salida = '') LIMIT 50", "explicacion": "Laboratorios actualmente en sesión activa:"}}

Esquema real de la base de datos (úsalo siempre, es la única fuente de verdad):
{esquema}
"""

    mensajes = [{"role": "system", "content": system_prompt}]
    historial_filtrado = [m for m in historial if m["rol"] in ("user", "assistant")]
    recientes = historial_filtrado[-4:]   # reducido de 6 a 4 para acortar el contexto total
    for i, msg in enumerate(recientes):
        if msg["rol"] == "assistant" and (i == 0 or recientes[i - 1]["rol"] == "assistant"):
            continue
        mensajes.append({"role": msg["rol"], "content": msg["contenido"]})
    mensajes.append({"role": "user", "content": pregunta})

    try:
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "messages": mensajes,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "top_p": 0.1,
                "num_predict": 300
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_SEGUNDOS) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as conn_err:
            return (
                "⚠️ No se pudo conectar con Ollama o tardó demasiado.\n\n"
                f"Detalle: {conn_err}\n\n"
                f"Tip: si esto se repite seguido, cambia OLLAMA_MODEL a 'llama3.2:1b' "
                f"en services/ia_service.py (es más rápido en tu hardware).",
                None,
            )

        texto_crudo = data["message"]["content"].strip()

        if not texto_crudo or texto_crudo == "{":
            return "⚠️ El modelo local falló al generar la respuesta completa. Intenta reformular la pregunta.", None

        try:
            respuesta_json = json.loads(texto_crudo)
        except json.JSONDecodeError:
            import re as _re
            match = _re.search(r'\{.*\}', texto_crudo, _re.DOTALL)
            if match:
                try:
                    texto_limpio = match.group().replace("'", '"')
                    respuesta_json = json.loads(texto_limpio)
                except Exception:
                    return f"⚠️ Error decodificando el formato JSON del modelo. Respuesta cruda: {texto_crudo}", None
            else:
                return f"⚠️ El modelo no devolvió un SQL válido. Intenta reformular la pregunta.\n\nRespuesta cruda: {texto_crudo}", None

        sql_generado = respuesta_json.get("sql", "").strip()
        explicacion = respuesta_json.get("explicacion", "Aquí están los resultados:")

        if not sql_generado:
            return "⚠️ El modelo no generó una consulta SQL. Intenta reformular la pregunta con otras palabras.", None

        return explicacion, sql_generado

    except Exception as e:
        return f"⚠️ Error interno al procesar la respuesta de la IA: {e}", None