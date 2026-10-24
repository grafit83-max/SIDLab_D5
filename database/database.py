# database/database.py
import psycopg2
import streamlit as st

def get_connection():
    """Devuelve una conexión a PostgreSQL usando las credenciales de secrets."""
    cfg = st.secrets["postgres"]
    return psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"]
    )