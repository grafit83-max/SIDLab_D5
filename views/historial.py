# pages/historial.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime

from config.settings import LABORATORIOS, TURNOS, ASIGNATURAS
from database.database import get_connection
from utils.export_excel import exportar_excel
from services.bitacora_service import get_bitacora, analizar_observacion
from services.auditoria_service import registrar_auditoria

def render():
    if st.session_state.profesor_logueado is None:
        st.warning("🔒 Inicia sesión para ver el historial.")
        return

    st.subheader("🔍 Historial y Exportación")

    from config.settings import EDIFICIOS
    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 2, 2, 2])
    with fc1: f_ini  = st.date_input("Desde", value=date.today() - timedelta(days=7))
    with fc2: f_fin  = st.date_input("Hasta", value=date.today())
    with fc3:
        f_edif = st.selectbox("Edificio", ["Todos"] + list(EDIFICIOS.keys()))
        labs_disponibles = EDIFICIOS[f_edif] if f_edif != "Todos" else LABORATORIOS
    with fc4:
        f_lab  = st.selectbox("Laboratorio", ["Todos"] + labs_disponibles)
    with fc5: f_prof = st.text_input("Buscar profesor / empleado", placeholder="Nombre o No. empleado")

    df_hist = get_bitacora(
        fecha_inicio=f_ini.strftime("%Y-%m-%d"),
        fecha_fin=f_fin.strftime("%Y-%m-%d"),
        laboratorio=f_lab if f_lab != "Todos" else None,
        profesor=f_prof if f_prof.strip() else None,
    )

    st.markdown(f"**{len(df_hist)} registros encontrados**")

    if df_hist.empty:
        st.info("No hay registros para los filtros seleccionados.")
    else:
        cols_mostrar = ["fecha", "turno", "laboratorio", "entrada", "salida", "grado_grupo", "no_alum", "asignatura", "tema", "nombre_profesor", "firma_jefe_grupo", "observaciones", "analisis_obs"]
        df_display = df_hist[cols_mostrar].copy()
        df_display.columns = ["Fecha", "Turno", "Lab", "Entrada", "Salida", "Grupo", "Alumnos", "Asignatura", "Tema", "Profesor", "Jefe Grupo", "Observaciones", "Estado"]
        st.dataframe(df_display, width="stretch", hide_index=True)

        if st.session_state.puede_descargar or st.session_state.es_admin:
            st.markdown("---")
            rango_texto = f"Del {f_ini.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}"
            # Determinar edificio real para el encabezado del Excel
            if f_edif != "Todos":
                edificio_excel = f_edif
            elif f_lab != "Todos":
                edificio_excel = next((e for e, ls in EDIFICIOS.items() if f_lab in ls), "D5")
            else:
                edificio_excel = None   # Todos los edificios
            lab_excel = f_lab if f_lab != "Todos" else None
            excel_bytes = exportar_excel(df_hist, titulo_extra=rango_texto,
                                         edificio=edificio_excel, laboratorio=lab_excel)
            nombre_archivo = f"Bitacora_D5_{f_ini.strftime('%Y%m%d')}_{f_fin.strftime('%Y%m%d')}.xlsx"
            st.download_button(
                label="📥 Descargar Excel (.xlsx)",
                data=excel_bytes,
                file_name=nombre_archivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
        else:
            st.info("🔒 La descarga de reportes está disponible para cuentas administrativas.")

        if st.session_state.es_admin:
            st.markdown("---")
            st.markdown("#### ✏️ Editar / Corregir Registro")

            opciones_edicion = {
                f"{r['nombre_profesor']}  |  Lab {r['laboratorio']}  |  {r['fecha']}  {r['entrada']}–{r['salida']}  (ID #{r['id']})": r['id']
                for _, r in df_hist.iterrows()
            }
            etiqueta_sel = st.selectbox("Selecciona el registro a editar:", ["— Elige un registro —"] + list(opciones_edicion.keys()), key="sel_edicion")

            if etiqueta_sel != "— Elige un registro —":
                id_editar = opciones_edicion[etiqueta_sel]
                fila = df_hist[df_hist["id"] == id_editar].iloc[0]

                with st.expander("📋 Datos actuales del registro", expanded=False):
                    dc1, dc2, dc3 = st.columns(3)
                    dc1.markdown(f"**Profesor:** {fila['nombre_profesor']}")
                    dc1.markdown(f"**No. Empleado:** {fila['num_empleado']}")
                    dc2.markdown(f"**Laboratorio:** {fila['laboratorio']}")
                    dc2.markdown(f"**Turno:** {fila['turno']}")
                    dc3.markdown(f"**Fecha:** {fila['fecha']}")
                    dc3.markdown(f"**Entrada:** {fila['entrada']}  |  **Salida:** {fila['salida']}")

                st.markdown("**Campos editables:**")
                with st.form("form_edicion"):
                    fe1, fe2 = st.columns(2)
                    with fe1:
                        e_sal   = st.text_input("Hora de Salida (HH:MM)", value=fila["salida"] or "", placeholder="Ej. 20:30")
                        e_alum  = st.number_input("No. de Alumnos", value=int(fila["no_alum"] or 1), min_value=1, max_value=100)
                        e_turno = st.selectbox("Turno", TURNOS, index=TURNOS.index(fila["turno"]) if fila["turno"] in TURNOS else 0)
                        e_grupo = st.text_input("Grado y Grupo", value=fila["grado_grupo"] or "")
                    with fe2:
                        idx_asig = ASIGNATURAS.index(fila["asignatura"]) if fila["asignatura"] in ASIGNATURAS else len(ASIGNATURAS)-1
                        e_asig  = st.selectbox("Asignatura", ASIGNATURAS, index=idx_asig)
                        e_tema  = st.text_input("Tema / Práctica", value=fila["tema"] or "")
                        e_jefe  = st.text_input("Jefe de Grupo", value=fila["firma_jefe_grupo"] or "")
                    e_obs   = st.text_area("Observaciones", value=fila["observaciones"] or "", height=100)
                    motivo  = st.text_input("Motivo de la corrección (obligatorio)", placeholder="Ej. Error al capturar la hora de salida")

                    if st.form_submit_button("💾 Guardar Corrección", width="stretch"):
                        errores_ed = []
                        if not motivo.strip(): errores_ed.append("Motivo de corrección")
                        if not e_grupo.strip(): errores_ed.append("Grado y Grupo")
                        if not e_tema.strip(): errores_ed.append("Tema / Práctica")

                        hora_valida = False
                        try:
                            datetime.strptime(e_sal.strip(), "%H:%M")
                            hora_valida = True
                        except ValueError:
                            errores_ed.append("Hora de Salida (formato inválido, usa HH:MM)")

                        if hora_valida:
                            try:
                                if datetime.strptime(e_sal.strip(), "%H:%M") <= datetime.strptime(fila["entrada"], "%H:%M"):
                                    errores_ed.append(f"Hora de Salida debe ser posterior a la entrada ({fila['entrada']})")
                            except ValueError:
                                pass

                        if errores_ed:
                            st.error("Corrige los siguientes campos: " + " | ".join(errores_ed))
                        else:
                            analisis_nuevo, falla_nueva = analizar_observacion(e_obs)
                            conn = get_connection()
                            c_db = conn.cursor()
                            c_db.execute('''
                                UPDATE bitacora SET
                                    turno = ?, salida = ?, grado_grupo = ?, no_alum = ?,
                                    asignatura = ?, tema = ?, firma_jefe_grupo = ?,
                                    observaciones = ?, analisis_obs = ?, tiene_falla = ?,
                                    editado = 1, editado_por = ?, fecha_edicion = ?
                                WHERE id = ?
                            ''', (
                                e_turno, e_sal.strip(), e_grupo.strip(), e_alum,
                                e_asig, e_tema.strip(), e_jefe.strip(),
                                e_obs, analisis_nuevo, int(falla_nueva),
                                st.session_state.profesor_logueado,
                                datetime.now().strftime("%Y-%m-%d %H:%M"), id_editar
                            ))
                            conn.commit()
                            conn.close()
                            registrar_auditoria(st.session_state.profesor_logueado, st.session_state.num_empleado, "EDICION", f"ID {id_editar}: {motivo.strip()}")
                            st.success(f"✅ Registro ID #{id_editar} corregido.")
                            st.rerun()