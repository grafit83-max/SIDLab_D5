# pages/dashboard.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from config.settings import EDIFICIOS, LABORATORIOS
from services.dashboard_service import get_stats_hoy, get_ocupacion_actual
from services.bitacora_service import get_bitacora

def render():
    if st.session_state.profesor_logueado is None:
        st.warning("🔒 Inicia sesión para ver el dashboard.")
        return

    st.subheader(f"📊 Dashboard — {date.today().strftime('%d de %B de %Y')}")

    stats = get_stats_hoy()
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-card"><div class="val">{stats["total_hoy"]}</div><div class="lbl">Registros hoy</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-card"><div class="val">{stats["fallas_hoy"]}</div><div class="lbl">Fallas reportadas hoy</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-card"><div class="val">{stats["labs_usados"]}</div><div class="lbl">Labs utilizados hoy</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-card"><div class="val">{stats["total_historico"]}</div><div class="lbl">Registros totales</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    col_g1, col_g2 = st.columns(2)
    inicio_30 = (date.today() - timedelta(days=29)).strftime("%Y-%m-%d")
    df_30 = get_bitacora(fecha_inicio=inicio_30)

    with col_g1:
        st.markdown("**Registros por laboratorio (últimos 30 días)**")
        if not df_30.empty:
            conteo_lab = df_30["laboratorio"].value_counts().reset_index()
            conteo_lab.columns = ["Laboratorio", "Registros"]
            st.bar_chart(conteo_lab.set_index("Laboratorio"))
        else:
            st.info("Sin datos suficientes.")

    with col_g2:
        st.markdown("**Registros por turno (últimos 30 días)**")
        if not df_30.empty:
            conteo_turno = df_30["turno"].value_counts().reset_index()
            conteo_turno.columns = ["Turno", "Registros"]
            st.bar_chart(conteo_turno.set_index("Turno"))
        else:
            st.info("Sin datos suficientes.")

    st.markdown("---")
    st.markdown("**Ocupación actual de laboratorios**")
    ocupacion_actual = get_ocupacion_actual()
    for edificio, labs in EDIFICIOS.items():
        st.markdown(f"**Edificio {edificio}**")
        cols_labs = st.columns(len(labs))
        for i, lab in enumerate(labs):
            with cols_labs[i]:
                if lab in ocupacion_actual:
                    info = ocupacion_actual[lab]
                    st.markdown(f'<div class="lab-activo">🟢 <b>Lab {lab}</b><br><small>{info["profesor"]}<br>{info["entrada"]}–{info["salida"]}</small></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="lab-libre">⚪ Lab {lab}<br><small>Libre</small></div>', unsafe_allow_html=True)