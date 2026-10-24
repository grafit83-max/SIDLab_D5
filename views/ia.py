# pages/ia.py
import streamlit as st
from datetime import date
from services.ia_service import consultar_ia, ejecutar_sql_seguro
from services.auditoria_service import registrar_auditoria

def render():
    if st.session_state.profesor_logueado is None:
        st.warning("🔒 Inicia sesión para usar el asistente.")
        return

    st.subheader("🤖 Asistente de Consulta — Bitácora D5")
    st.markdown("Haz preguntas en lenguaje natural sobre los registros. El asistente genera y ejecuta el SQL automáticamente.")

    with st.expander("💡 Ejemplos de preguntas que puedes hacer"):
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.markdown("""
            - ¿Qué profesor usó más el Lab 204 este mes?
            - ¿Cuántas sesiones hubo hoy?
            - ¿Cuántas fallas se reportaron en noviembre?
            - ¿Qué laboratorio tiene más registros históricos?
            """)
        with col_e2:
            st.markdown("""
            - Lista los 5 profesores con más sesiones registradas
            - ¿Cuántas sesiones del turno vespertino hubo esta semana?
            - ¿Qué asignatura se imparte más en el Lab 212?
            - Muéstrame las últimas 10 fallas reportadas
            """)

    st.markdown("---")

    for msg in st.session_state.chat_historia:
        with st.chat_message(msg["rol"]):
            st.markdown(msg["contenido"])
            if msg.get("sql") and st.session_state.es_admin:
                with st.expander("🔍 Ver SQL generado"):
                    st.code(msg["sql"], language="sql")
            if msg.get("dataframe") is not None:
                df_chat = msg["dataframe"]
                if not df_chat.empty:
                    st.dataframe(df_chat, width="stretch", hide_index=True)
                    st.caption(f"{len(df_chat)} registro(s) encontrado(s).")
                else:
                    st.info("La consulta no devolvió resultados.")

    pregunta = st.chat_input("Escribe tu pregunta sobre la bitácora...")

    if pregunta:
        with st.chat_message("user"):
            st.markdown(pregunta)
        st.session_state.chat_historia.append({"rol": "user", "contenido": pregunta, "sql": None, "dataframe": None})

        with st.chat_message("assistant"):
            with st.spinner("Consultando la bitácora..."):
                respuesta, sql_generado = consultar_ia(pregunta, st.session_state.chat_historia)
                df_resultado = None

                if sql_generado:
                    df_resultado, error_sql = ejecutar_sql_seguro(sql_generado)
                    if error_sql:
                        respuesta += f"\n\n⚠️ {error_sql}"
                        df_resultado = None

                st.markdown(respuesta)

                if sql_generado and st.session_state.es_admin:
                    with st.expander("🔍 Ver SQL generado"):
                        st.code(sql_generado, language="sql")

                if df_resultado is not None:
                    if not df_resultado.empty:
                        st.dataframe(df_resultado, width="stretch", hide_index=True)
                        st.caption(f"{len(df_resultado)} registro(s) encontrado(s).")
                        if st.session_state.puede_descargar or st.session_state.es_admin:
                            csv = df_resultado.to_csv(index=False).encode("utf-8")
                            st.download_button(
                                "📥 Descargar resultados (.csv)",
                                data=csv,
                                file_name=f"consulta_ia_{date.today().strftime('%Y%m%d')}.csv",
                                mime="text/csv",
                            )
                    else:
                        st.info("La consulta no devolvió resultados para esos criterios.")

        st.session_state.chat_historia.append({
            "rol": "assistant", "contenido": respuesta, "sql": sql_generado, "dataframe": df_resultado,
        })

        registrar_auditoria(st.session_state.profesor_logueado, st.session_state.num_empleado, "CONSULTA_IA", pregunta[:100])

    if st.session_state.chat_historia:
        st.markdown("---")
        if st.button("🗑️ Limpiar conversación", width="content"):
            st.session_state.chat_historia = []
            st.rerun()