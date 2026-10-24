import streamlit as st
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
# ── IMPORTS DE NUESTRA ARQUITECTURA ──
from config.settings import EDIFICIOS
from database.init_db import init_db, migrar_db
from services.auth_service import verificar_admin, verificar_o_crear_usuario
from services.auditoria_service import registrar_auditoria
from services.dashboard_service import get_ocupacion_actual

# ── IMPORTS DE LAS VISTAS (PÁGINAS) ──
from views import registro, dashboard, historial, ia, administracion, inventario

# ─────────────────────────────────────────────────────────────────────
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS (CSS)
# ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Bitácora",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap');

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

.stTabs [data-baseweb="tab"] {
    font-family: 'IBM Plex Sans', sans-serif;
    font-weight: 600;
    font-size: 0.9rem;
    letter-spacing: .03em;
}

.metric-card {
    background: linear-gradient(135deg, #1a2f4e 0%, #1F4E78 100%);
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    color: white;
    margin-bottom: 1rem;
    box-shadow: 0 4px 15px rgba(31,78,120,0.3);
}
.metric-card .val {
    font-size: 2.4rem;
    font-weight: 700;
    line-height: 1;
    font-family: 'IBM Plex Mono', monospace;
}
.metric-card .lbl { font-size: .85rem; opacity: .8; margin-top: .3rem; }

.falla-badge { background: #FFEBEE; color: #C62828; border: 1px solid #EF9A9A; border-radius: 6px; padding: 2px 10px; font-size: .8rem; font-weight: 600; }
.ok-badge { background: #E8F5E9; color: #2E7D32; border: 1px solid #A5D6A7; border-radius: 6px; padding: 2px 10px; font-size: .8rem; font-weight: 600; }
.lab-activo { background: #E3F2FD; border-left: 4px solid #1565C0; border-radius: 0 8px 8px 0; padding: .7rem 1rem; margin: .4rem 0; font-size: .9rem; }
.lab-libre { background: #F5F5F5; border-left: 4px solid #BDBDBD; border-radius: 0 8px 8px 0; padding: .7rem 1rem; margin: .4rem 0; font-size: .9rem; color: #757575; }
.firma-code { font-family: 'IBM Plex Mono', monospace; background: #F8F9FA; border: 1px solid #DEE2E6; border-radius: 6px; padding: .6rem 1rem; font-size: .85rem; color: #1F4E78; word-break: break-all; }

/* Sidebar — fondo oscuro azul marino */
[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(180deg, #0d1f35 0%, #1a2f4e 100%) !important;
}
[data-testid="stSidebar"] { color: #E8F0FE; }
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] small,
[data-testid="stSidebar"] div:not([class*="stForm"]) > div > span { color: #E8F0FE !important; }
[data-testid="stSidebar"] .stButton button { background: #1F4E78 !important; border: 1px solid #4A90D9 !important; color: white !important; width: 100%; }
/* Inputs del login — fondo legible */
[data-testid="stSidebar"] input { background: #ffffff !important; color: #0d1f35 !important; border: 1px solid #4A90D9 !important; border-radius: 6px !important; }
[data-testid="stSidebar"] input::placeholder { color: #90A4AE !important; }
/* Lab activo en sidebar — texto oscuro sobre fondo claro */
[data-testid="stSidebar"] .lab-activo { color: #0d1f35 !important; }
[data-testid="stSidebar"] .lab-activo b { color: #0d1f35 !important; }
[data-testid="stSidebar"] .lab-activo small { color: #1565C0 !important; }
/* Lab libre en sidebar — texto visible */
[data-testid="stSidebar"] .lab-libre { color: #757575 !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# 2. INICIALIZACIÓN DE BASE DE DATOS Y VARIABLES DE SESIÓN
# ─────────────────────────────────────────────────────────────────────
init_db()
migrar_db()

defaults = {
    "profesor_logueado": None,
    "num_empleado": None,
    "requiere_cambio": 0,
    "es_admin": False,
    "puede_descargar": False,
    "hora_entrada_fija": datetime.now().time(),
    "login_intentos": 0,
    "login_bloqueado_hasta": None,
    "chat_historia": [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────
# 3. BARRA LATERAL (SIDEBAR) — AUTENTICACIÓN
# ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🖥️ Bitácora")
    st.markdown("**Laboratorios de Cómputo**")
    st.markdown("---")

    if st.session_state.profesor_logueado is None:
        st.markdown("### 🔑 Iniciar Sesión")

        bloqueado = False
        if st.session_state.login_bloqueado_hasta:
            if datetime.now() < st.session_state.login_bloqueado_hasta:
                segundos_restantes = int((st.session_state.login_bloqueado_hasta - datetime.now()).total_seconds())
                st.error(f"🔒 Demasiados intentos fallidos. Espera {segundos_restantes} segundos.")
                bloqueado = True
            else:
                st.session_state.login_bloqueado_hasta = None
                st.session_state.login_intentos = 0

        if not bloqueado:
            with st.form("form_login", clear_on_submit=False):
                user_input  = st.text_input("Usuario / Nombre Completo", placeholder="Nombre o usuario")
                num_emp_inp = st.text_input("No. de Empleado", placeholder="Solo profesores")
                pin_input   = st.text_input("Contraseña / PIN", type="password", placeholder="••••")
                enviado = st.form_submit_button("Iniciar Sesión", use_container_width=True)

            if enviado:
                if user_input and pin_input:
                    admin_info = verificar_admin(user_input, pin_input)
                    if admin_info:
                        rol = admin_info.get("rol", "admin")
                        st.session_state.profesor_logueado = user_input
                        st.session_state.num_empleado      = f"ADMIN_{user_input.upper()}"
                        st.session_state.es_admin          = (rol == "admin")
                        st.session_state.puede_descargar   = True
                        st.session_state.requiere_cambio   = 0
                        st.session_state.hora_entrada_fija = datetime.now().time()
                        st.session_state.login_intentos    = 0
                        for k in ["cerrando_sesion", "ultima_firma", "ultimo_registro",
                                  "pendiente_confirmacion", "form_borrador"]:
                            st.session_state.pop(k, None)
                        registrar_auditoria(user_input, f"ADMIN_{user_input.upper()}", "LOGIN", f"Rol: {rol}")
                        st.success(f"Bienvenido, {user_input}.")
                        st.rerun()
                    else:
                        if not num_emp_inp.strip():
                            st.error("Los docentes deben ingresar su Número de Empleado.")
                        else:
                            res = verificar_o_crear_usuario(num_emp_inp.strip(), user_input.strip(), pin_input)
                            if res["valido"]:
                                st.session_state.profesor_logueado = res["nombre"]
                                st.session_state.num_empleado      = num_emp_inp.strip()
                                st.session_state.requiere_cambio   = res["requiere_cambio"]
                                st.session_state.es_admin          = False
                                st.session_state.puede_descargar   = False
                                st.session_state.hora_entrada_fija = datetime.now().time()
                                st.session_state.login_intentos    = 0
                                for k in ["cerrando_sesion", "ultima_firma", "ultimo_registro",
                                          "pendiente_confirmacion", "form_borrador"]:
                                    st.session_state.pop(k, None)
                                registrar_auditoria(res["nombre"], num_emp_inp, "LOGIN", "Profesor")
                                st.success("Acceso concedido.")
                                st.rerun()
                            else:
                                st.session_state.login_intentos += 1
                                intentos_restantes = 5 - st.session_state.login_intentos
                                if st.session_state.login_intentos >= 5:
                                    st.session_state.login_bloqueado_hasta = datetime.now() + timedelta(minutes=2)
                                    registrar_auditoria(user_input, num_emp_inp.strip(), "LOGIN_BLOQUEADO", "5 intentos fallidos")
                                    st.error("🔒 Cuenta bloqueada por 2 minutos tras 5 intentos fallidos.")
                                else:
                                    st.error(f"{res['msg']} ({intentos_restantes} intento(s) restante(s))")
            elif enviado:
                st.warning("Completa los campos de Usuario y Contraseña.")
    else:
        st.markdown(f"### 👤 {st.session_state.profesor_logueado}")
        if st.session_state.es_admin:
            st.markdown('<span style="background:#2E7D32;color:white;padding:2px 8px;border-radius:4px;font-size:.8rem">ADMIN</span>', unsafe_allow_html=True)
        elif st.session_state.puede_descargar:
            st.markdown('<span style="background:#1565C0;color:white;padding:2px 8px;border-radius:4px;font-size:.8rem">CONTROL</span>', unsafe_allow_html=True)
        else:
            st.markdown(f'<span style="background:#4A4A4A;color:white;padding:2px 8px;border-radius:4px;font-size:.8rem">EMP {st.session_state.num_empleado}</span>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("**Estado de Laboratorios**")
        ocupacion = get_ocupacion_actual()

        # Color de título por edificio — solo el encabezado cambia, labs igual que antes
        color_titulo = {"D5": "#64B5F6", "K5": "#4DB6AC"}

        for edificio, labs in EDIFICIOS.items():
            color = color_titulo.get(edificio, "#90CAF9")
            st.markdown(
                f'<div style="font-size:.75rem;font-weight:700;color:{color};' +
                f'letter-spacing:.08em;margin:10px 0 4px">🏢 EDIFICIO {edificio}</div>',
                unsafe_allow_html=True
            )
            for lab in labs:
                if lab in ocupacion:
                    info = ocupacion[lab]
                    st.markdown(f'<div class="lab-activo">🟢 Lab <b>{lab}</b><br><small>{info["profesor"]}<br>{info["entrada"]}–{info["salida"]}</small></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="lab-libre">⚪ Lab {lab} — Libre</div>', unsafe_allow_html=True)

        st.markdown("---")
        if st.button("Cerrar Sesión", use_container_width=True):
            registrar_auditoria(st.session_state.profesor_logueado, st.session_state.num_empleado, "LOGOUT")
            for k in defaults:
                st.session_state[k] = defaults[k]
            # Limpiar estados de registro que no están en defaults
            # para que no contaminen la siguiente sesión de cualquier usuario
            for k in ["cerrando_sesion", "ultima_firma", "ultimo_registro",
                      "pendiente_confirmacion", "form_borrador"]:
                st.session_state.pop(k, None)
            st.rerun()

# ─────────────────────────────────────────────────────────────────────
# 4. ENCABEZADO PRINCIPAL Y ENRUTADOR DE PESTAÑAS (TABS)
# ─────────────────────────────────────────────────────────────────────
st.markdown("# 🖥️ Bitácora de Laboratorios")
st.markdown("Sistema digital de registro con firma criptográfica — División de Tecnologías de la Información")
st.markdown("---")

# Renderizado condicional según el rol del usuario
# Inventario visible solo para ManuelEA (admin) y ErikaRR (control)
if st.session_state.es_admin:
    tabs = st.tabs(["📝 Registro", "📊 Dashboard", "🔍 Historial", "🤖 Consulta IA", "📦 Inventario", "🛡️ Administración"])
    with tabs[0]: registro.render()
    with tabs[1]: dashboard.render()
    with tabs[2]: historial.render()
    with tabs[3]: ia.render()
    with tabs[4]: inventario.render()
    with tabs[5]: administracion.render()

elif st.session_state.puede_descargar:
    tabs = st.tabs(["📊 Dashboard", "🔍 Historial", "🤖 Consulta IA", "📦 Inventario"])
    with tabs[0]: dashboard.render()
    with tabs[1]: historial.render()
    with tabs[2]: ia.render()
    with tabs[3]: inventario.render()

else:
    # Profesores — solo el formulario de registro, sin barra de navegación
    registro.render()