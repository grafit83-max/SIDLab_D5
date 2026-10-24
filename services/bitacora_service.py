# services/bitacora_service.py
import pandas as pd
import smtplib
import streamlit as st
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from database.database import get_connection
from config.settings import KEYWORDS_FALLA

def analizar_observacion(observaciones: str) -> tuple[str, bool]:
    obs_lower = observaciones.lower().strip()
    frases_ok = {"ninguna", "todo bien", "sin novedad", "ok", "sin observaciones", "n/a", ""}
    if not obs_lower or obs_lower in frases_ok:
        return "✅ Sin incidencias", False
    if any(k in obs_lower for k in KEYWORDS_FALLA):
        return "⚠️ Posible falla de equipo — revisar", True
    return "📝 Observación general registrada", False

def enviar_alerta_falla(profesor: str, laboratorio: str, observaciones: str):
    try:
        cfg = st.secrets.get("email", {})
        if not cfg:
            return  
        msg = MIMEMultipart()
        msg["From"]    = cfg["smtp_user"]
        msg["To"]      = cfg["destinatario"]
        msg["Subject"] = f"[ALERTA D5] Falla reportada en Lab {laboratorio}"
        cuerpo = (
            f"Se detectó una posible falla en el Laboratorio {laboratorio}.\n\n"
            f"Profesor: {profesor}\n"
            f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"Observación: {observaciones}\n\n"
            "Por favor revisar el equipo a la brevedad."
        )
        msg.attach(MIMEText(cuerpo, "plain"))
        with smtplib.SMTP(cfg["smtp_host"], int(cfg.get("smtp_port", 587))) as s:
            s.starttls()
            s.login(cfg["smtp_user"], cfg["smtp_pwd"])
            s.sendmail(cfg["smtp_user"], cfg["destinatario"], msg.as_string())
    except Exception:
        pass

def verificar_conflicto_lab(laboratorio: str, fecha: str, entrada_str: str, salida_str: str, id_excluir: int = -1) -> str | None:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT id, nombre_profesor, entrada, salida
           FROM bitacora
           WHERE laboratorio = %s AND fecha = %s AND id != %s""",
        (laboratorio, fecha, id_excluir),
    )
    registros = c.fetchall()
    conn.close()

    ahora_str = datetime.now().strftime("%H:%M")

    for rid, prof, ent, sal in registros:
        try:
            e1 = datetime.strptime(entrada_str, "%H:%M")
            s1 = datetime.strptime(salida_str,  "%H:%M")
            e2 = datetime.strptime(ent,         "%H:%M")

            if sal:
                s2 = datetime.strptime(sal, "%H:%M")
                # Traslape real entre dos profesores distintos en el mismo lab
                # e1 < s2 estricto: permite que uno entre exactamente cuando el otro sale
                if e1 < s2 and s1 > e2:
                    return (f"🚫 **Laboratorio {laboratorio} no disponible.**\n\n"
                            f"Ya existe una sesión registrada de **{ent} – {sal}** "
                            f"a cargo del **Prof. {prof}** (ID #{rid}) que se traslapa "
                            f"con el horario solicitado ({entrada_str} – {salida_str}).")
            else:
                ahora_dt = datetime.strptime(ahora_str, "%H:%M")
                if e2 <= ahora_dt:
                    return (f"🚫 **Laboratorio {laboratorio} actualmente en uso.**\n\n"
                            f"El **Prof. {prof}** ingresó a las **{ent}** y su sesión sigue activa.")
        except ValueError:
            pass
    return None

def verificar_sesion_activa_profesor(num_empleado: str, fecha: str, entrada_str: str, salida_str: str, id_excluir: int = -1) -> str | None:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT id, laboratorio, entrada, salida
           FROM bitacora
           WHERE num_empleado = %s AND fecha = %s AND id != %s""",
        (num_empleado, fecha, id_excluir),
    )
    registros = c.fetchall()
    conn.close()

    for rid, lab, ent, sal in registros:
        try:
            e1 = datetime.strptime(entrada_str, "%H:%M")
            s1 = datetime.strptime(salida_str,  "%H:%M")
            e2 = datetime.strptime(ent,         "%H:%M")

            if sal:
                s2 = datetime.strptime(sal, "%H:%M")
                # <= y >= para bloquear traslapes incluyendo inicio = fin de sesión anterior
                if e1 <= s2 and s1 >= e2:
                    from config.settings import EDIFICIOS
                    edificio_lab = next((e for e, labs in EDIFICIOS.items() if lab in labs), "?")
                    return (
                        f"🚫 **Ya tienes una sesión registrada en Edificio {edificio_lab} "
                        f"Lab {lab} de {ent} a {sal} (ID #{rid}).**\n\n"
                        f"Un profesor no puede registrar dos sesiones que se toquen o traslapen. "
                        f"La sesión anterior termina a las {sal} y la nueva inicia a las {entrada_str}."
                    )
            else:
                ahora_dt = datetime.strptime(datetime.now().strftime("%H:%M"), "%H:%M")
                if e2 <= ahora_dt:
                    return (
                        f"🚫 **Ya tienes una sesión activa en Lab {lab} "
                        f"desde las {ent} (ID #{rid}).**\n\n"
                        f"No puedes registrar otra sesión mientras tienes una en curso."
                    )
        except ValueError:
            pass
    return None

def get_bitacora(fecha_inicio: str | None = None, fecha_fin: str | None = None, laboratorio: str | None = None, profesor: str | None = None, solo_fallas: bool = False) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM bitacora WHERE 1=1"
    params: list = []
    if fecha_inicio:
        query += " AND fecha >= %s"; params.append(fecha_inicio)
    if fecha_fin:
        query += " AND fecha <= %s"; params.append(fecha_fin)
    if laboratorio and laboratorio != "Todos":
        query += " AND laboratorio = %s"; params.append(laboratorio)
    if profesor and profesor.strip():
        query += " AND (nombre_profesor LIKE %s OR num_empleado = %s)"
        params += [f"%{profesor}%", profesor]
    if solo_fallas:
        query += " AND tiene_falla = 1"
    query += " ORDER BY id DESC"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df