# services/auth_service.py
import streamlit as st
from database.database import get_connection
from utils.seguridad import hashear_pwd, verificar_pwd, _leer_secret

def verificar_o_crear_usuario(num_emp: str, nombre_sugerido: str, pwd_ingresado: str) -> dict:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT nombre, password_hash, requiere_cambio, activo FROM usuarios WHERE num_empleado = %s",
        (num_emp,)
    )
    user = c.fetchone()

    if not user:
        hash_inicial = hashear_pwd("1234", num_emp)
        c.execute(
            "INSERT INTO usuarios (num_empleado, nombre, password_hash, requiere_cambio, activo) VALUES (%s,%s,%s,1,1)",
            (num_emp, nombre_sugerido, hash_inicial)
        )
        conn.commit()
        conn.close()
        if verificar_pwd(pwd_ingresado, hash_inicial, num_emp):
            return {"valido": True, "nombre": nombre_sugerido, "requiere_cambio": 1}
        return {"valido": False, "msg": "Cuenta creada. Usa la contraseña inicial '1234'."}

    db_nombre, db_hash, db_cambio, db_activo = user
    conn.close()

    if not db_activo:
        return {"valido": False, "msg": "Cuenta desactivada. Contacta al administrador."}
    if verificar_pwd(pwd_ingresado, db_hash, num_emp):
        return {"valido": True, "nombre": db_nombre, "requiere_cambio": db_cambio}
    return {"valido": False, "msg": "Contraseña incorrecta para ese número de empleado."}

def actualizar_password_db(num_emp: str, nueva_pwd: str):
    nuevo_hash = hashear_pwd(nueva_pwd, num_emp)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE usuarios SET password_hash = %s, requiere_cambio = 0 WHERE num_empleado = %s",
        (nuevo_hash, num_emp)
    )
    conn.commit()
    conn.close()

def resetear_usuario_db(num_emp: str):
    nuevo_hash = hashear_pwd("1234", num_emp)
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE usuarios SET password_hash = %s, requiere_cambio = 1 WHERE num_empleado = %s",
        (nuevo_hash, num_emp)
    )
    conn.commit()
    conn.close()

def verificar_admin(usuario: str, pwd: str) -> dict | None:
    try:
        admins = st.secrets.get("admins", {})
    except Exception:
        admins = {}

    if not admins:
        admin_env = {
            _leer_secret("ADMIN_USER", "ManuelEA"): {
                "password": _leer_secret("ADMIN_PWD", "M0r@1355"),
                "rol": "admin",
            },
            _leer_secret("CONTROL_USER", "ErikaRR"): {
                "password": _leer_secret("CONTROL_PWD", "3r1K488"),
                "rol": "control",
            },
        }
        admins = admin_env

    if usuario in admins and admins[usuario]["password"] == pwd:
        return admins[usuario]
    return None