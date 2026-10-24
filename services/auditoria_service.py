# services/auditoria_service.py
from datetime import datetime
from database.database import get_connection

def registrar_auditoria(usuario: str, num_empleado: str, accion: str, detalle: str = ""):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO auditoria (timestamp, usuario, num_empleado, accion, detalle) VALUES (%s,%s,%s,%s,%s)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), usuario, num_empleado, accion, detalle)
    )
    conn.commit()
    conn.close()