# services/auditoria_service.py
from datetime import datetime
from zoneinfo import ZoneInfo
from database.database import get_connection

def registrar_auditoria(usuario: str, num_empleado: str, accion: str, detalle: str = ""):
    conn = get_connection()
    c = conn.cursor()
    
    # Genera el string con la hora exacta local
    hora_local = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute(
        "INSERT INTO auditoria (timestamp, usuario, num_empleado, accion, detalle) VALUES (%s,%s,%s,%s,%s)",
        (hora_local, usuario, num_empleado, accion, detalle)
    )
    conn.commit()
    conn.close()