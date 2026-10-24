# pages/administracion.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime

from database.database import get_connection
from services.auth_service import resetear_usuario_db
from services.auditoria_service import registrar_auditoria
from services.bitacora_service import get_bitacora

def render():
    if not st.session_state.es_admin:
        st.error("🔒 Acceso denegado.")
        return

    st.subheader("🛡️ Panel de Administración")

    sub1, sub2, sub3 = st.tabs(["👥 Usuarios", "📋 Auditoría", "🗑️ Gestión de Registros"])

    with sub1:
        st.markdown("### Docentes registrados")
        conn = get_connection()
        df_users = pd.read_sql_query("SELECT num_empleado, nombre, requiere_cambio, activo FROM usuarios ORDER BY nombre", conn)
        conn.close()

        if df_users.empty:
            st.info("No hay docentes registrados.")
        else:
            df_users.columns = ["No. Empleado", "Nombre", "Requiere cambio pwd", "Activo"]
            st.dataframe(df_users, width="stretch", hide_index=True)

            st.markdown("---")
            col_acc1, col_acc2 = st.columns(2)

            with col_acc1:
                st.markdown("**Resetear contraseña**")
                with st.form("form_reset"):
                    emp_reset = st.selectbox("Empleado", df_users["No. Empleado"].tolist(), key="sel_reset")
                    if st.form_submit_button("Resetear a '1234'"):
                        resetear_usuario_db(emp_reset)
                        registrar_auditoria(st.session_state.profesor_logueado, st.session_state.num_empleado, "RESET_PWD", emp_reset)
                        st.success(f"Cuenta {emp_reset} reseteada.")
                        st.rerun()

            with col_acc2:
                st.markdown("**Activar / Desactivar cuenta**")
                with st.form("form_toggle"):
                    emp_toggle = st.selectbox("Empleado", df_users["No. Empleado"].tolist(), key="sel_toggle")
                    nuevo_estado = st.radio("Estado", ["Activar", "Desactivar"])
                    if st.form_submit_button("Aplicar"):
                        val = 1 if nuevo_estado == "Activar" else 0
                        conn = get_connection()
                        c_db = conn.cursor()
                        c_db.execute("UPDATE usuarios SET activo = %s WHERE num_empleado = %s", (val, emp_toggle))
                        conn.commit()
                        conn.close()
                        registrar_auditoria(st.session_state.profesor_logueado, st.session_state.num_empleado, "TOGGLE_CUENTA", f"{emp_toggle} -> {nuevo_estado}")
                        st.success(f"Cuenta {emp_toggle} {nuevo_estado.lower()}da.")
                        st.rerun()

    with sub2:
        st.markdown("### Bitácora de auditoría del sistema")
        dias_aud = st.slider("Últimos N días", 1, 90, 7)
        inicio_aud = (date.today() - timedelta(days=dias_aud)).strftime("%Y-%m-%d")
        conn = get_connection()
        df_aud = pd.read_sql_query(
            "SELECT timestamp, usuario, num_empleado, accion, detalle FROM auditoria WHERE timestamp >= %s ORDER BY id DESC",
            conn, params=(inicio_aud,)
        )
        conn.close()
        if df_aud.empty:
            st.info("Sin actividad reciente.")
        else:
            df_aud.columns = ["Timestamp", "Usuario", "No. Empleado", "Acción", "Detalle"]
            st.dataframe(df_aud, width="stretch", hide_index=True)

    with sub3:
        st.markdown("### Eliminar registros de bitácora")
        st.warning("⚠️ Esta acción es **irreversible**. Solo para correcciones de errores graves.")

        ge1, ge2 = st.columns(2)
        with ge1: g_ini = st.date_input("Desde", value=date.today() - timedelta(days=30), key="gest_ini")
        with ge2: g_fin = st.date_input("Hasta", value=date.today(), key="gest_fin")

        df_gest = get_bitacora(fecha_inicio=g_ini.strftime("%Y-%m-%d"), fecha_fin=g_fin.strftime("%Y-%m-%d"))

        if df_gest.empty:
            st.info("No hay registros en el rango de fechas seleccionado.")
        else:
            st.markdown(f"**{len(df_gest)} registros en el período — selecciona el que deseas eliminar:**")
            cols_gest = ["id", "fecha", "laboratorio", "entrada", "salida", "nombre_profesor", "grado_grupo", "asignatura", "observaciones"]
            df_gest_disp = df_gest[cols_gest].copy()
            df_gest_disp.columns = ["ID", "Fecha", "Lab", "Entrada", "Salida", "Profesor", "Grupo", "Asignatura", "Observaciones"]
            st.dataframe(df_gest_disp, width="stretch", hide_index=True)

            st.markdown("---")
            opciones_gest = {
                f"ID #{r['id']}  |  {r['nombre_profesor']}  |  Lab {r['laboratorio']}  |  {r['fecha']}  {r['entrada']}–{r['salida']}": r['id']
                for _, r in df_gest.iterrows()
            }
            etiqueta_elim = st.selectbox("Registro a eliminar:", ["— Elige un registro —"] + list(opciones_gest.keys()), key="sel_eliminar")

            if etiqueta_elim != "— Elige un registro —":
                id_eliminar = opciones_gest[etiqueta_elim]
                fila_elim = df_gest[df_gest["id"] == id_eliminar].iloc[0]

                st.markdown("**📋 Registro seleccionado:**")
                st.error(
                    f"**ID #{id_eliminar}** — Prof. **{fila_elim['nombre_profesor']}** — "
                    f"Lab **{fila_elim['laboratorio']}** — {fila_elim['fecha']} "
                    f"{fila_elim['entrada']}–{fila_elim['salida']} — Grupo: {fila_elim['grado_grupo']}"
                )

                with st.form("form_eliminar"):
                    motivo_elim = st.text_input("Motivo de eliminación (obligatorio)", placeholder="Ej. Registro duplicado por error del sistema")
                    confirmar_elim = st.checkbox(f"Confirmo que deseo eliminar permanentemente el registro ID #{id_eliminar}")
                    if st.form_submit_button("🗑️ Eliminar Registro Definitivamente", width="stretch"):
                        if not confirmar_elim:
                            st.error("⚠️ Activa la casilla de confirmación para continuar.")
                        elif not motivo_elim.strip():
                            st.error("⚠️ Escribe el motivo de la eliminación.")
                        else:
                            conn = get_connection()
                            c_db = conn.cursor()
                            c_db.execute("DELETE FROM bitacora WHERE id = %s", (id_eliminar,))
                            afectados = c_db.rowcount
                            conn.commit()
                            conn.close()
                            if afectados:
                                registrar_auditoria(
                                    st.session_state.profesor_logueado, st.session_state.num_empleado, "ELIMINAR",
                                    f"ID {id_eliminar} ({fila_elim['nombre_profesor']} Lab {fila_elim['laboratorio']} {fila_elim['fecha']}): {motivo_elim}"
                                )
                                st.success(f"✅ Registro ID #{id_eliminar} eliminado correctamente.")
                            else:
                                st.error("No se encontró ese ID en la base de datos.")
                            st.rerun()