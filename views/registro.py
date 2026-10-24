import time
import streamlit as st
from datetime import datetime, date
from zoneinfo import ZoneInfo
from config.settings import EDIFICIOS, TURNOS, ASIGNATURAS, HORARIO_APERTURA, HORARIO_CIERRE
from database.database import get_connection
from utils.firmas import generar_firma_digital
from services.auth_service import actualizar_password_db
from services.auditoria_service import registrar_auditoria
from services.bitacora_service import (
    verificar_sesion_activa_profesor,
    verificar_conflicto_lab,
    analizar_observacion,
    enviar_alerta_falla
)
from services.dashboard_service import get_ocupacion_actual
import pandas as pd

def render():
    if st.session_state.profesor_logueado is None:
        st.warning("🔒 Inicia sesión para registrar una sesión de laboratorio.")
        return

    # ── Pantalla de cuenta regresiva — sustituye toda la interfaz ──────
    if st.session_state.get("cierre_pendiente"):
        st.markdown("### ✅ Registro guardado correctamente")
        st.success(
            f"Tu sesión de laboratorio quedó registrada exitosamente. "
            f"Gracias, **{st.session_state.profesor_logueado}**."
        )
        contenedor = st.empty()
        for segundos in range(60, 0, -1):
            contenedor.warning(f"🔒 Cerrando sesión en **{segundos}** segundo(s)...")
            time.sleep(1)
        contenedor.empty()

        from services.auditoria_service import registrar_auditoria as _audit
        _audit(st.session_state.profesor_logueado, st.session_state.num_empleado,
               "LOGOUT_AUTO", "Cierre automático tras guardar registro")
        defaults = {
            "profesor_logueado": None, "num_empleado": None,
            "requiere_cambio": 0, "es_admin": False,
            "puede_descargar": False,
            "hora_entrada_fija": datetime.now(ZoneInfo("America/Mexico_City")).time(),        
            "login_intentos": 0, "login_bloqueado_hasta": None,
            "chat_historia": [], "pendiente_confirmacion": None,
            "cierre_pendiente": False,
        }
        for k, v in defaults.items():
            st.session_state[k] = v
        st.rerun()
        return

    if st.session_state.requiere_cambio == 1:
        st.subheader("⚠️ Configuración de Contraseña Obligatoria")
        st.info("Es tu primer acceso. Debes establecer una contraseña personalizada antes de continuar.")
        with st.form("form_cambio_pwd"):
            nueva_pwd   = st.text_input("Nueva Contraseña", type="password")
            confirmar   = st.text_input("Confirmar Contraseña", type="password")
            if st.form_submit_button("Guardar Contraseña"):
                if not nueva_pwd:
                    st.error("La contraseña no puede estar vacía.")
                elif nueva_pwd == "1234":
                    st.error("No puedes reutilizar la contraseña genérica.")
                elif len(nueva_pwd) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres.")
                elif nueva_pwd != confirmar:
                    st.error("Las contraseñas no coinciden.")
                else:
                    actualizar_password_db(st.session_state.num_empleado, nueva_pwd)
                    registrar_auditoria(st.session_state.profesor_logueado, st.session_state.num_empleado, "CAMBIO_PWD")
                    st.session_state.requiere_cambio = 0
                    st.success("✅ Contraseña actualizada. Ya puedes registrar sesiones.")
                    time.sleep(1)
                    st.rerun()
        return

    st.subheader("Nueva Sesión de Laboratorio")

    # ── Pantalla de cierre — solo para profesores, nunca para admin/control ──
    # Debe ir ANTES de verificar sesión activa porque el registro que
    # acaba de guardarse aparecerá como sesión activa en la BD,
    # lo que haría que el if sesion_activa interceptara el render
    # antes de llegar aquí.
    es_admin_o_control = st.session_state.es_admin or st.session_state.puede_descargar

    if st.session_state.get("cerrando_sesion") and not es_admin_o_control:
        st.subheader("✅ Registro guardado correctamente")
        if st.session_state.get("ultima_firma"):
            st.markdown(
                f'<div class="firma-code">🔐 Token de Firma: {st.session_state["ultima_firma"]}</div>',
                unsafe_allow_html=True
            )
        if st.session_state.get("ultimo_registro"):
            st.caption(f"Sesión registrada: {st.session_state['ultimo_registro']}")
        contenedor_cuenta = st.empty()
        for segundos in range(60, 0, -1):
            contenedor_cuenta.warning(
                f"🔒 La sesión se cerrará en **{segundos}** segundo(s). "
                f"Puedes cerrar esta ventana o esperar."
            )
            time.sleep(1)
        contenedor_cuenta.empty()
        from services.auditoria_service import registrar_auditoria as _audit
        _audit(
            st.session_state.profesor_logueado,
            st.session_state.num_empleado,
            "LOGOUT_AUTO",
            "Cierre automático tras guardar registro"
        )
        for k, v in {
            "profesor_logueado": None, "num_empleado": None,
            "requiere_cambio": 0, "es_admin": False,
            "puede_descargar": False, "login_intentos": 0,
            "login_bloqueado_hasta": None, "chat_historia": [],
            "pendiente_confirmacion": None, "cerrando_sesion": False,
            "ultima_firma": None, "ultimo_registro": None,
            "hora_entrada_fija": datetime.now(ZoneInfo("America/Mexico_City")).time(),
        }.items():
            st.session_state[k] = v
        st.rerun()
        return

    # ── Verificar sesión activa — SOLO para profesores, nunca admin/control ──
    fecha_hoy   = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    ahora_str   = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%H:%M")
    ahora_time  = datetime.now(ZoneInfo("America/Mexico_City")).time()

    sesion_activa = None
    if not es_admin_o_control:
        from datetime import timedelta
        ahora_mas_margen = (datetime.now(ZoneInfo("America/Mexico_City")) - timedelta(minutes=1)).strftime("%H:%M")
        conn_check = get_connection()
        c_check = conn_check.cursor()
        c_check.execute(
            """SELECT id, laboratorio, entrada, salida FROM bitacora
               WHERE num_empleado = %s AND fecha = %s
               AND entrada <= %s
               AND (salida > %s OR salida IS NULL OR salida = \'\')
               ORDER BY id DESC LIMIT 1""",
            (st.session_state.num_empleado, fecha_hoy, ahora_str, ahora_mas_margen)
        )
        sesion_activa = c_check.fetchone()
        conn_check.close()

    if sesion_activa:
        sid, slab, sent, ssal = sesion_activa
        from config.settings import EDIFICIOS as _ED
        sedif = next((e for e, ls in _ED.items() if slab in ls), "?")

        # Calcular segundos restantes hasta 1 minuto después de la hora de salida
        try:
            h_sal, m_sal = map(int, ssal.split(":"))
            ahora_dt = datetime.now(ZoneInfo("America/Mexico_City"))
            salida_dt = ahora_dt.replace(hour=h_sal, minute=m_sal, second=0, microsecond=0)
            # +1 minuto de margen: el formulario se habilita a salida+1min
            from datetime import timedelta as _td
            umbral_dt = salida_dt + _td(minutes=1)
            segundos_restantes = max(0, int((umbral_dt - ahora_dt).total_seconds()))
        except Exception:
            segundos_restantes = None

        if segundos_restantes is not None and segundos_restantes > 0:
            minutos = segundos_restantes // 60
            segs    = segundos_restantes % 60
            tiempo_txt = f"{minutos} min {segs} seg" if minutos > 0 else f"{segs} seg"
            st.warning(
                f"🔒 **Registro deshabilitado — tienes una sesión activa.**\n\n"
                f"Actualmente estás registrado en **Edificio {sedif} Lab {slab}** "
                f"de **{sent}** a **{ssal}** (ID #{sid}).\n\n"
                f"⏱️ Tiempo restante: **{tiempo_txt}**. "
                f"El formulario se habilitará 1 minuto después de que concluya la sesión."
            )
            # Auto-refresco cada 30 segundos para actualizar el tiempo restante
            # y detectar cuando la sesión termina
            time.sleep(30)
            st.rerun()
        else:
            # La sesión ya terminó según el horario registrado — refrescar ya
            st.info(
                f"✅ Tu sesión en **Edificio {sedif} Lab {slab}** "
                f"({sent}–{ssal}) ha concluido. El formulario ya está disponible."
            )
            time.sleep(2)
            st.rerun()
    elif st.session_state.get("pendiente_confirmacion"):
        # ── PANTALLA DE CONFIRMACIÓN — reemplaza completamente el formulario ──
        p = st.session_state["pendiente_confirmacion"]
        st.markdown("### ✅ Verificación de datos — ¿Todo es correcto?")
        st.info(
            f"**Edificio:** {p['edificio']}  |  **Laboratorio:** Lab {p['laboratorio']}  |  **Turno:** {p['turno']}\n\n"
            f"**Fecha:** {p['fecha_hoy']}  |  **Entrada:** {p['entrada_str']}  |  **Salida estimada:** {p['salida_str']}\n\n"
            f"**Grado/Grupo:** {p['grado_grupo']}  |  **Alumnos:** {p['no_alum']}\n\n"
            f"**Asignatura:** {p['asignatura']}\n\n"
            f"**Tema:** {p['tema']}\n\n"
            f"**Jefe de Grupo:** {p['firma_alumno']}\n\n"
            f"**Observaciones:** {p['obs_completa']}"
        )
        col_conf, col_canc = st.columns(2)
        with col_conf:
            if st.button("✍️ Confirmar y Guardar Registro", use_container_width=True, type="primary"):
                analisis, tiene_falla = analizar_observacion(p["obs_completa"])
                firma = generar_firma_digital(
                    st.session_state.profesor_logueado,
                    p["laboratorio"], p["fecha_hoy"], p["entrada_str"],
                    st.session_state.num_empleado
                )
                conn = get_connection()
                c_db = conn.cursor()
                c_db.execute('''
                    INSERT INTO bitacora
                    (fecha, turno, laboratorio, entrada, salida, grado_grupo, no_alum,
                     asignatura, tema, nombre_profesor, num_empleado, firma_hash,
                     firma_jefe_grupo, observaciones, tiene_falla, analisis_obs)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ''', (
                    p["fecha_hoy"], p["turno"], p["laboratorio"],
                    p["entrada_str"], p["salida_str"],
                    p["grado_grupo"], p["no_alum"], p["asignatura"], p["tema"],
                    st.session_state.profesor_logueado, st.session_state.num_empleado,
                    firma, p["firma_alumno"], p["obs_completa"],
                    int(tiene_falla), analisis,
                ))
                conn.commit()
                conn.close()
                registrar_auditoria(
                    st.session_state.profesor_logueado,
                    st.session_state.num_empleado, "REGISTRO",
                    f"Edif {p['edificio']} Lab {p['laboratorio']} {p['entrada_str']}-{p['salida_str']}"
                )
                if tiene_falla:
                    enviar_alerta_falla(st.session_state.profesor_logueado, p["laboratorio"], p["obs_completa"])
                    st.warning("⚠️ Se detectó una posible falla. Se notificó al responsable.")
                st.session_state.pop("pendiente_confirmacion", None)
                st.session_state.pop("form_borrador", None)
                st.session_state.hora_entrada_fija = datetime.now(ZoneInfo("America/Mexico_City")).time()

                es_solo_profesor = (
                    not st.session_state.es_admin and
                    not st.session_state.puede_descargar
                )
                if es_solo_profesor:
                    # Guardar datos para mostrar en pantalla de cierre y hacer rerun
                    st.session_state["cerrando_sesion"] = True
                    st.session_state["ultima_firma"]    = firma
                    st.session_state["ultimo_registro"] = (
                        f"Edif {p['edificio']} Lab {p['laboratorio']} "
                        f"{p['entrada_str']}–{p['salida_str']}"
                    )
                st.rerun()
        with col_canc:
            if st.button("✏️ Corregir datos", use_container_width=True):
                st.session_state.pop("pendiente_confirmacion", None)
                st.rerun()

    else:
        # ── FORMULARIO DE REGISTRO ────────────────────────────────────
        # Recuperar valores previos si el usuario volvió desde "Corregir datos"
        prev = st.session_state.get("form_borrador", {})

        edifs    = list(EDIFICIOS.keys())
        idx_edif = edifs.index(prev["edificio"]) if prev.get("edificio") in edifs else 0

        # Inicializar selección guardada (persiste al volver de "Corregir datos")
        if "edificio_sel" not in st.session_state:
            st.session_state.edificio_sel = edifs[idx_edif]

        # ── Tarjetas de Edificio ──────────────────────────────────────
        st.markdown('<p style="font-size:.9rem;font-weight:600;margin-bottom:6px">Selecciona el Edificio donde impartirás clase</p>', unsafe_allow_html=True)
        estilos_edif = {
            "D5": {"color": "#1565C0", "fondo_act": "#E3F2FD", "fondo_in": "#F0F4F8", "txt_in": "#90A4AE"},
            "K5": {"color": "#00897B", "fondo_act": "#E0F2F1", "fondo_in": "#F0F4F8", "txt_in": "#90A4AE"},
        }
        cols_edif = st.columns(len(edifs))
        for i, edif in enumerate(edifs):
            with cols_edif[i]:
                es        = estilos_edif.get(edif, {"color":"#7B1FA2","fondo_act":"#F3E5F5","fondo_in":"#F0F4F8","txt_in":"#CE93D8"})
                activo    = (st.session_state.edificio_sel == edif)
                bg        = es["fondo_act"] if activo else es["fondo_in"]
                color     = es["color"]     if activo else es["txt_in"]
                borde     = f"3px solid {es['color']}" if activo else "2px dashed #CFD8DC"
                sombra    = "0 4px 12px rgba(0,0,0,0.12)" if activo else "none"
                icono     = "🏢" if activo else "🏛️"
                check     = f'<div style="color:{es["color"]};font-size:.7rem;font-weight:700;margin-top:2px">✔ SELECCIONADO</div>' if activo else ""
                st.markdown(f"""
                <div style="background:{bg};border:{borde};border-radius:12px;
                            padding:16px 8px 10px;text-align:center;
                            box-shadow:{sombra};margin-bottom:4px;">
                    <div style="font-size:2rem">{icono}</div>
                    <div style="font-size:1rem;font-weight:700;color:{color};margin-top:4px">
                        Edificio {edif}
                    </div>
                    <div style="font-size:.72rem;color:{color};opacity:.75;margin-top:2px">
                        Labs: {', '.join(EDIFICIOS[edif])}
                    </div>
                    {check}
                </div>""", unsafe_allow_html=True)
                if st.button("Seleccionar" if not activo else "✔ Activo",
                             key=f"btn_edif_{edif}", use_container_width=True,
                             disabled=activo):
                    st.session_state.edificio_sel = edif
                    st.rerun()

        edificio = st.session_state.edificio_sel
        st.markdown("---")
        entrada_fija = datetime.now(ZoneInfo("America/Mexico_City")).replace(second=0, microsecond=0).time()
        entrada_str  = entrada_fija.strftime("%H:%M")

        # Turno automático: 07:00–11:59 → Matutino | 12:00–21:00 → Vespertino
        turno_auto = "Matutino" if entrada_fija.hour < 12 else "Vespertino"

        # Generar lista de horas de salida de 07:00 a 21:00 en pasos de 5 min
        horas_salida = []
        for h in range(7, 21):
            for m in range(0, 60, 5):
                horas_salida.append(f"{h:02d}:{m:02d}")
        horas_salida.append("21:00")

        # Calcular la siguiente hora cerrada (en punto) respecto a la entrada
        # Ej: 17:12 → 18:00 | 17:00 → 18:00 | 17:30 → 18:00
        sig_hora = entrada_fija.hour + 1
        salida_auto = f"{sig_hora:02d}:00" if sig_hora <= 21 else "21:00"
        idx_salida_auto = horas_salida.index(salida_auto) if salida_auto in horas_salida else len(horas_salida) - 1

        # Si el profesor volvió desde "Corregir datos", restaurar su selección previa
        salida_prev = prev.get("salida_str")
        if salida_prev and salida_prev in horas_salida:
            idx_salida_auto = horas_salida.index(salida_prev)

        with st.form("form_registro", clear_on_submit=False):
            c1, c2, c3 = st.columns(3)

            with c1:
                st.markdown("**Control de Sesión**")
                labs_edif = EDIFICIOS[edificio]
                idx_lab = labs_edif.index(prev["laboratorio"]) if prev.get("laboratorio") in labs_edif else 0
                laboratorio = st.selectbox("Laboratorio", labs_edif,
                                  index=idx_lab,
                                  format_func=lambda l: f"Lab {l}")
                turno = turno_auto
                st.text_input("Turno (automático)", value=turno_auto, disabled=True)
                grado_grupo = st.text_input("Grado y Grupo",
                                  value=prev.get("grado_grupo", ""),
                                  placeholder="Ej. 3-A")
                no_alum     = st.number_input("No. de Alumnos", min_value=1, max_value=100,
                                  value=prev.get("no_alum", 20))

            with c2:
                st.markdown("**Horario y Contenido**")
                st.text_input("Hora de Entrada (fija — hora actual)",
                              value=entrada_str, disabled=True)
                # Restaurar hora de salida previa si existe
                salida_str_sel = st.selectbox(
                    "Hora de Salida (estimada)",
                    horas_salida,
                    index=idx_salida_auto,
                )
                salida = datetime.strptime(salida_str_sel, "%H:%M").time()
                idx_asig = ASIGNATURAS.index(prev["asignatura"]) if prev.get("asignatura") in ASIGNATURAS else 0
                asignatura_sel = st.selectbox("Asignatura", ASIGNATURAS, index=idx_asig)
                asignatura_custom = ""
                if asignatura_sel == "Otra (especificar en Tema)":
                    asignatura_custom = st.text_input("Especifica la asignatura",
                                          value=prev.get("asignatura_custom", ""))
                tema = st.text_input("Tema / Práctica",
                          value=prev.get("tema", ""),
                          placeholder="Ej. Práctica 3: Sockets TCP")

            with c3:
                st.markdown("**Validación y Observaciones**")
                firma_alumno    = st.text_input("Nombre / Matrícula del Jefe de Grupo",
                                                value=prev.get("firma_alumno", ""),
                                                placeholder="Ej. García López / A210345")
                # Restaurar observaciones sin el sufijo de equipo si lo tenía
                obs_prev = prev.get("observaciones", "")
                observaciones   = st.text_area("Observaciones",
                                               value=obs_prev,
                                               placeholder="Todo funcionando correctamente / Falla en equipo #7",
                                               height=120)
                no_equipo_falla = st.text_input("No. de equipo con falla (si aplica)",
                                                value=prev.get("no_equipo_falla", ""),
                                                placeholder="Ej. 7, 12, 15")

            enviado = st.form_submit_button("📋 Revisar y Confirmar Registro", use_container_width=True)

            if enviado:
                asignatura_final = asignatura_custom.strip() if asignatura_sel == "Otra (especificar en Tema)" else asignatura_sel
                obs_completa = observaciones.strip()
                if no_equipo_falla.strip():
                    obs_completa += f" [Equipos reportados: {no_equipo_falla.strip()}]"
                salida_str = salida_str_sel

                errores = []
                if not grado_grupo.strip():  errores.append("Grado y Grupo")
                if not asignatura_final:     errores.append("Asignatura")
                if not tema.strip():         errores.append("Tema / Práctica")
                if not firma_alumno.strip(): errores.append("Jefe de Grupo")
                if not obs_completa:         errores.append("Observaciones")
                ap = datetime.strptime(HORARIO_APERTURA, "%H:%M").time()
                cl = datetime.strptime(HORARIO_CIERRE,   "%H:%M").time()
                if not (ap <= salida <= cl):
                    errores.append(f"Hora de salida fuera del horario ({HORARIO_APERTURA}–{HORARIO_CIERRE})")
                elif datetime.strptime(salida_str, "%H:%M") <= datetime.strptime(entrada_str, "%H:%M"):
                    errores.append("La hora de salida debe ser posterior a la entrada")

                if errores:
                    st.error("Campos sin llenar o con error:\n- " + "\n- ".join(errores))
                else:
                    conflicto_lab = verificar_conflicto_lab(laboratorio, fecha_hoy, entrada_str, salida_str)
                    if conflicto_lab:
                        st.error(conflicto_lab)
                    else:
                        # Guardar borrador para restaurar si el usuario vuelve a corregir
                        st.session_state["form_borrador"] = {
                            "edificio":        edificio,
                            "laboratorio":     laboratorio,
                            "turno":           turno,
                            "grado_grupo":     grado_grupo.strip(),
                            "no_alum":         no_alum,
                            "salida_str":      salida_str,
                            "asignatura":      asignatura_final,
                            "asignatura_custom": asignatura_custom,
                            "tema":            tema.strip(),
                            "firma_alumno":    firma_alumno.strip(),
                            "observaciones":   observaciones.strip(),
                            "no_equipo_falla": no_equipo_falla.strip(),
                        }
                        st.session_state["pendiente_confirmacion"] = {
                            "edificio": edificio, "laboratorio": laboratorio,
                            "turno": turno, "grado_grupo": grado_grupo.strip(),
                            "no_alum": no_alum, "entrada_str": entrada_str,
                            "salida_str": salida_str, "asignatura": asignatura_final,
                            "tema": tema.strip(), "firma_alumno": firma_alumno.strip(),
                            "obs_completa": obs_completa, "fecha_hoy": fecha_hoy,
                        }
                        st.rerun()

    # Mini historial del día
    st.markdown("---")
    st.markdown("#### Mis registros de hoy")
    hoy_str = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    conn = get_connection()
    df_hoy = pd.read_sql_query(
        "SELECT laboratorio, turno, entrada, salida, asignatura, grado_grupo, observaciones, analisis_obs "
        "FROM bitacora WHERE fecha = %s AND num_empleado = %s ORDER BY id DESC",
        conn, params=(hoy_str, st.session_state.num_empleado)
    )
    conn.close()
    if df_hoy.empty:
        st.info("No tienes registros hoy todavía.")
    else:
        df_hoy.columns = ["Lab", "Turno", "Entrada", "Salida", "Asignatura", "Grupo", "Observaciones", "Estado"]
        # Agregar columna Edificio resolviendo por lab
        def _edificio(lab):
            for edif, labs in EDIFICIOS.items():
                if lab in labs:
                    return edif
            return "?"
        df_hoy.insert(0, "Edificio", df_hoy["Lab"].apply(_edificio))
        st.dataframe(df_hoy, width="stretch", hide_index=True)