import psycopg2
import streamlit as st

def get_connection():
    # Extrae la cadena de conexión completa desde secrets.toml
    db_url = st.secrets["postgres"]["url"]
    return psycopg2.connect(db_url)