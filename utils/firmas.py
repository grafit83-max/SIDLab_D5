# utils/firmas.py
import hashlib

def generar_firma_digital(usuario: str, laboratorio: str, fecha: str, hora: str, clave: str) -> str:
    cadena = f"{usuario}|{laboratorio}|{fecha}|{hora}|{clave}"
    digest = hashlib.sha256(cadena.encode()).hexdigest()
    return f"SHA256:{digest[:20].upper()}"
