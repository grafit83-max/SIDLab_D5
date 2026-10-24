# utils/seguridad.py
import hashlib
import hmac
import os
import streamlit as st

def _salt_for(identifier: str) -> str:
    """Sal determinista basada en identificador para no necesitar columna extra."""
    return hashlib.sha256(f"d5-salt-{identifier}".encode()).hexdigest()[:16]

def hashear_pwd(pwd: str, identifier: str) -> str:
    sal = _salt_for(identifier)
    return hashlib.sha256(f"{sal}{pwd}".encode()).hexdigest()

def verificar_pwd(pwd_plano: str, pwd_hash: str, identifier: str) -> bool:
    return hmac.compare_digest(hashear_pwd(pwd_plano, identifier), pwd_hash)

def _leer_secret(key: str, default: str = "") -> str:
    """Lee de st.secrets si existe, si no usa variable de entorno, si no usa default."""
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)