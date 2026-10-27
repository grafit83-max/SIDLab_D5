# services/dashboard_service.py
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from database.database import get_connection

def get_stats_hoy() -> dict:
    # Fecha exacta de México
    hoy = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM bitacora WHERE fecha = %s", (hoy,))
    total_hoy = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM bitacora WHERE fecha = %s AND tiene_falla = 1", (hoy,))
    fallas_hoy = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT laboratorio) FROM bitacora WHERE fecha = %s", (hoy,))
    labs_usados = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM bitacora")
    total_hist = c.fetchone()[0]
    conn.close()
    return {"total_hoy": total_hoy, "fallas_hoy": fallas_hoy,
            "labs_usados": labs_usados, "total_historico": total_hist}

@st.cache_data(ttl=30)
def get_ocupacion_actual() -> dict:
    # Hora y fecha exactas de México
    hora_mx = datetime.now(ZoneInfo("America/Mexico_City"))
    ahora = hora_mx.strftime("%H:%M")
    hoy   = hora_mx.strftime("%Y-%m-%d")
    
    conn  = get_connection()
    c     = conn.cursor()
    
    c.execute(
        "SELECT laboratorio, nombre_profesor, entrada, salida FROM bitacora "
        "WHERE fecha = %s AND entrada <= %s AND salida >= %s",
        (hoy, ahora, ahora)
    )
    rows = list(c.fetchall())
    
    c.execute(
        "SELECT laboratorio, nombre_profesor, entrada, salida FROM bitacora "
        "WHERE fecha = %s AND entrada <= %s AND (salida IS NULL OR salida = '')",
        (hoy, ahora)
    )
    rows += [r for r in c.fetchall() if r[0] not in {x[0] for x in rows}]
    conn.close()
    
    resultado = {}
    for lab, prof, ent, sal in rows:
        resultado[lab] = {
            "profesor": prof,
            "entrada":  ent,
            "salida":   sal if sal else "En curso",
        }
    return resultado

def edificio_de_lab(laboratorio: str) -> str:
    """Devuelve el edificio al que pertenece un laboratorio, o 'Desconocido'."""
    from config.settings import EDIFICIOS
    for edif, labs in EDIFICIOS.items():
        if laboratorio in labs:
            return edif
    return "Desconocido"