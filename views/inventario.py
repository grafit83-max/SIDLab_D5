# views/inventario.py
# ─────────────────────────────────────────────────────────────────────
# Vista del módulo de Inventario.
# Acceso restringido: solo ManuelEA y ErikaRR (es_admin o puede_descargar).
# Operaciones: consultar (con filtros), agregar, editar, eliminar (lógico).
# ─────────────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
from datetime import datetime
from services.inventario_service import (
    get_inventario, get_item_por_id, get_resumen_por_laboratorio,
    agregar_item, modificar_item, eliminar_item,
    ESTADOS_VALIDOS, CATEGORIAS_VALIDAS, LABORATORIOS_INV,
)
from services.auditoria_service import registrar_auditoria
from utils.export_excel import exportar_excel_inventario

# Colores para el estado del equipo
_COLOR_ESTADO = {
    "BUENO":   ("#E8F5E9", "#2E7D32", "🟢"),
    "REGULAR": ("#FFF8E1", "#F57F17", "🟡"),
    "MALO":    ("#FFEBEE", "#C62828", "🔴"),
}


def _badge_estado(estado: str) -> str:
    bg, fg, icon = _COLOR_ESTADO.get(estado, ("#F5F5F5", "#424242", "⚪"))
    return (
        f'<span style="background:{bg};color:{fg};border-radius:4px;'
        f'padding:2px 10px;font-size:.8rem;font-weight:600">{icon} {estado}</span>'
    )


def render():
    # ── Guard: solo admins y control ────────────────────────────────
    if not (st.session_state.es_admin or st.session_state.puede_descargar):
        st.error("🔒 Acceso restringido. Solo ManuelEA y ErikaRR pueden acceder al inventario.")
        return

    usuario_actual = st.session_state.profesor_logueado

    st.markdown("## 📦 Inventario de Laboratorios D5")
    st.markdown("Gestión de equipos, mobiliario y materiales por laboratorio.")

    # ── KPIs generales ──────────────────────────────────────────────
    df_resumen = get_resumen_por_laboratorio()
    if not df_resumen.empty:
        total_eq  = int(df_resumen["total"].sum())
        total_mal = int(df_resumen["malos"].sum())
        total_reg = int(df_resumen["regulares"].sum())
        total_ok  = int(df_resumen["buenos"].sum())

        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f'<div class="metric-card"><div class="val">{total_eq}</div><div class="lbl">Total de equipos</div></div>', unsafe_allow_html=True)
        k2.markdown(f'<div class="metric-card" style="background:linear-gradient(135deg,#1b5e20,#2e7d32)"><div class="val">{total_ok}</div><div class="lbl">En buen estado</div></div>', unsafe_allow_html=True)
        k3.markdown(f'<div class="metric-card" style="background:linear-gradient(135deg,#e65100,#f57c00)"><div class="val">{total_reg}</div><div class="lbl">En estado regular</div></div>', unsafe_allow_html=True)
        k4.markdown(f'<div class="metric-card" style="background:linear-gradient(135deg,#7f0000,#c62828)"><div class="val">{total_mal}</div><div class="lbl">En mal estado</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Subtabs ─────────────────────────────────────────────────────
    sub_consulta, sub_agregar, sub_editar, sub_eliminar = st.tabs([
        "🔍 Consultar", "➕ Agregar", "✏️ Editar", "🗑️ Eliminar"
    ])

    # ══════════════════════════════════════════════════════════════════
    # SUB-TAB: CONSULTAR
    # ══════════════════════════════════════════════════════════════════
    with sub_consulta:
        st.markdown("### Consulta y filtros")

        fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 3])
        with fc1:
            f_lab = st.selectbox("Laboratorio", ["Todos"] + LABORATORIOS_INV, key="inv_f_lab")
        with fc2:
            f_cat = st.selectbox("Categoría", ["Todas"] + CATEGORIAS_VALIDAS, key="inv_f_cat")
        with fc3:
            f_est = st.selectbox("Estado", ["Todos"] + ESTADOS_VALIDOS, key="inv_f_est")
        with fc4:
            f_bus = st.text_input("Buscar por descripción, marca, serie o N° inventario", key="inv_f_bus", placeholder="Ej: DELL, monitor, 5151...")

        df = get_inventario(
            laboratorio=None if f_lab == "Todos" else f_lab,
            categoria=None if f_cat == "Todas" else f_cat,
            estado=None if f_est == "Todos" else f_est,
            busqueda=f_bus if f_bus.strip() else None,
        )

        st.markdown(f"**{len(df)} registro(s) encontrado(s)**")

        if df.empty:
            st.info("No hay registros que coincidan con los filtros seleccionados.")
        else:
            # Preparar para visualización — reemplazar None por "—"
            cols_mostrar = ["id", "descripcion", "marca", "serie", "estado",
                            "modelo", "num_inventario", "laboratorio", "categoria", "caracteristicas"]
            df_disp = df[cols_mostrar].copy()
            df_disp.columns = ["ID", "Descripción", "Marca", "Serie", "Estado",
                                "Modelo", "N° Inventario", "Laboratorio", "Categoría", "Características"]

            # Reemplazar None / NaN por "—" en todas las columnas de texto
            for col in ["Marca", "Serie", "Modelo", "N° Inventario", "Características"]:
                df_disp[col] = df_disp[col].fillna("—").replace("", "—")

            st.dataframe(
                df_disp,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID":              st.column_config.NumberColumn(width="small"),
                    "Estado":          st.column_config.TextColumn(width="small"),
                    "Descripción":     st.column_config.TextColumn(width="large"),
                    "Marca":           st.column_config.TextColumn(width="medium"),
                    "Serie":           st.column_config.TextColumn(width="medium"),
                    "Modelo":          st.column_config.TextColumn(width="small"),
                    "N° Inventario":   st.column_config.TextColumn(width="medium"),
                    "Laboratorio":     st.column_config.TextColumn(width="small"),
                    "Categoría":       st.column_config.TextColumn(width="medium"),
                    "Características": st.column_config.TextColumn(width="large"),
                },
            )

            # Descarga Excel con formato institucional
            filtro_txt = f"Laboratorio: {f_lab}  |  Categoría: {f_cat}  |  Estado: {f_est}"
            excel_bytes = exportar_excel_inventario(df_disp, titulo_extra=filtro_txt)
            nombre_xlsx = f"Inventario_D5_{f_lab}_{f_cat}_{datetime.now().strftime('%Y%m%d')}.xlsx".replace(" ", "_")
            st.download_button(
                label="📥 Descargar Excel (.xlsx)",
                data=excel_bytes,
                file_name=nombre_xlsx,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )

        # Resumen por laboratorio — tabla + gráfica de barras apiladas
        st.markdown("---")
        st.markdown("#### 📊 Resumen por laboratorio")
        if not df_resumen.empty:
            df_res_disp = df_resumen.copy()
            df_res_disp.columns = ["Laboratorio", "Total", "Buenos", "Regulares", "Malos"]

            # Tabla con barras de progreso para "Buenos"
            st.dataframe(
                df_res_disp,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Laboratorio": st.column_config.TextColumn("Laboratorio", width="medium"),
                    "Total":       st.column_config.NumberColumn("Total", width="small"),
                    "Buenos":      st.column_config.ProgressColumn(
                                       "Buenos 🟢",
                                       min_value=0,
                                       max_value=int(df_res_disp["Total"].max()),
                                       format="%d",
                                       width="medium",
                                   ),
                    "Regulares":   st.column_config.ProgressColumn(
                                       "Regulares 🟡",
                                       min_value=0,
                                       max_value=int(df_res_disp["Total"].max()),
                                       format="%d",
                                       width="medium",
                                   ),
                    "Malos":       st.column_config.ProgressColumn(
                                       "Malos 🔴",
                                       min_value=0,
                                       max_value=int(df_res_disp["Total"].max()),
                                       format="%d",
                                       width="medium",
                                   ),
                },
            )

            # Gráfica de barras apiladas por laboratorio
            import plotly.graph_objects as go
            fig = go.Figure(data=[
                go.Bar(name="🟢 Buenos",    x=df_res_disp["Laboratorio"], y=df_res_disp["Buenos"],    marker_color="#2E7D32"),
                go.Bar(name="🟡 Regulares", x=df_res_disp["Laboratorio"], y=df_res_disp["Regulares"], marker_color="#F57F17"),
                go.Bar(name="🔴 Malos",     x=df_res_disp["Laboratorio"], y=df_res_disp["Malos"],     marker_color="#C62828"),
            ])
            fig.update_layout(
                barmode="stack",
                title="Distribución de estado por laboratorio",
                xaxis_title="Laboratorio",
                yaxis_title="Cantidad de equipos",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                plot_bgcolor="#ffffff",
                paper_bgcolor="#ffffff",
                height=380,
                margin=dict(t=60, b=40, l=40, r=20),
                font=dict(family="IBM Plex Sans, sans-serif", size=12),
            )
            fig.update_xaxes(tickangle=-30)
            st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════
    # SUB-TAB: AGREGAR
    # ══════════════════════════════════════════════════════════════════
    with sub_agregar:
        st.markdown("### Agregar nuevo equipo / bien")

        with st.form("form_inv_agregar"):
            a1, a2 = st.columns(2)
            with a1:
                a_desc  = st.text_input("Descripción *", placeholder="Ej: COMPUTADORA DE ESCRITORIO")
                a_marca = st.text_input("Marca", placeholder="Ej: DELL")
                a_serie = st.text_input("No. de Serie", placeholder="Ej: ABC123XYZ")
                a_est   = st.selectbox("Estado *", ESTADOS_VALIDOS)
                a_mod   = st.text_input("Modelo", placeholder="Ej: OptiPlex 7090")
            with a2:
                a_inv   = st.text_input("N° de Inventario", placeholder="Ej: 5151005425OUPU046")
                a_lab   = st.selectbox("Laboratorio *", LABORATORIOS_INV)
                a_cat   = st.selectbox("Categoría *", CATEGORIAS_VALIDAS)
                a_carac = st.text_area("Características", placeholder="Ej: i5 10ma gen, 8GB RAM, SSD 256GB", height=100)

            st.caption("* Campos obligatorios")
            if st.form_submit_button("💾 Guardar nuevo item", use_container_width=True):
                ok, msg = agregar_item(
                    descripcion=a_desc, marca=a_marca, serie=a_serie,
                    estado=a_est, modelo=a_mod, num_inventario=a_inv,
                    laboratorio=a_lab, categoria=a_cat, caracteristicas=a_carac,
                    usuario=usuario_actual,
                )
                if ok:
                    st.success(f"✅ {msg}")
                    registrar_auditoria(usuario_actual, st.session_state.num_empleado,
                                        "INV_AGREGAR", f"{a_desc} — Lab {a_lab}")
                    st.rerun()
                else:
                    st.error(f"⚠️ {msg}")

    # ══════════════════════════════════════════════════════════════════
    # SUB-TAB: EDITAR
    # ══════════════════════════════════════════════════════════════════
    with sub_editar:
        st.markdown("### Editar / corregir un registro")

        df_edit = get_inventario()
        if df_edit.empty:
            st.info("No hay registros en el inventario.")
        else:
            opciones_edit = {
                f"ID #{r['id']}  |  {r['descripcion']}  |  Lab {r['laboratorio']}  |  {r['estado']}": r['id']
                for _, r in df_edit.iterrows()
            }
            sel_edit = st.selectbox(
                "Selecciona el item a editar:",
                ["— Elige un item —"] + list(opciones_edit.keys()),
                key="inv_sel_edit",
            )

            if sel_edit != "— Elige un item —":
                id_editar = opciones_edit[sel_edit]
                item = get_item_por_id(id_editar)

                if item:
                    # Mostrar datos actuales
                    with st.expander("📋 Datos actuales del item", expanded=False):
                        dc1, dc2 = st.columns(2)
                        dc1.markdown(f"**Descripción:** {item['descripcion']}")
                        dc1.markdown(f"**Marca:** {item.get('marca') or '—'}")
                        dc1.markdown(f"**Serie:** {item.get('serie') or '—'}")
                        dc1.markdown(f"**Estado:** {item['estado']}")
                        dc2.markdown(f"**Laboratorio:** {item['laboratorio']}")
                        dc2.markdown(f"**Categoría:** {item.get('categoria') or '—'}")
                        dc2.markdown(f"**N° Inventario:** {item.get('num_inventario') or '—'}")
                        dc2.markdown(f"**Características:** {item.get('caracteristicas') or '—'}")

                    with st.form("form_inv_editar"):
                        e1, e2 = st.columns(2)
                        with e1:
                            e_desc  = st.text_input("Descripción *", value=item["descripcion"])
                            e_marca = st.text_input("Marca", value=item.get("marca") or "")
                            e_serie = st.text_input("No. de Serie", value=item.get("serie") or "")
                            idx_est = ESTADOS_VALIDOS.index(item["estado"]) if item["estado"] in ESTADOS_VALIDOS else 0
                            e_est   = st.selectbox("Estado *", ESTADOS_VALIDOS, index=idx_est)
                            e_mod   = st.text_input("Modelo", value=item.get("modelo") or "")
                        with e2:
                            e_inv   = st.text_input("N° de Inventario", value=item.get("num_inventario") or "")
                            idx_lab = LABORATORIOS_INV.index(item["laboratorio"]) if item["laboratorio"] in LABORATORIOS_INV else 0
                            e_lab   = st.selectbox("Laboratorio *", LABORATORIOS_INV, index=idx_lab)
                            idx_cat = CATEGORIAS_VALIDAS.index(item["categoria"]) if item.get("categoria") in CATEGORIAS_VALIDAS else len(CATEGORIAS_VALIDAS) - 1
                            e_cat   = st.selectbox("Categoría *", CATEGORIAS_VALIDAS, index=idx_cat)
                            e_carac = st.text_area("Características", value=item.get("caracteristicas") or "", height=100)

                        if st.form_submit_button("💾 Guardar cambios", use_container_width=True):
                            ok, msg = modificar_item(
                                item_id=id_editar,
                                descripcion=e_desc, marca=e_marca, serie=e_serie,
                                estado=e_est, modelo=e_mod, num_inventario=e_inv,
                                laboratorio=e_lab, categoria=e_cat, caracteristicas=e_carac,
                                usuario=usuario_actual,
                            )
                            if ok:
                                st.success(f"✅ {msg}")
                                st.info(f"📝 Modificado por **{usuario_actual}** el {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M')}")
                                registrar_auditoria(usuario_actual, st.session_state.num_empleado,
                                                    "INV_EDITAR", f"ID #{id_editar}: {e_desc}")
                                st.rerun()
                            else:
                                st.error(f"⚠️ {msg}")

    # ══════════════════════════════════════════════════════════════════
    # SUB-TAB: ELIMINAR
    # ══════════════════════════════════════════════════════════════════
    with sub_eliminar:
        st.markdown("### Eliminar item del inventario")
        st.warning("⚠️ La eliminación es **lógica** — el registro queda inactivo pero no se borra físicamente, por trazabilidad.")

        # Filtro previo para acotar la búsqueda
        el1, el2 = st.columns(2)
        with el1:
            f_lab_el = st.selectbox("Filtrar por laboratorio:", ["Todos"] + LABORATORIOS_INV, key="inv_el_lab")
        with el2:
            f_bus_el = st.text_input("Buscar descripción o serie:", key="inv_el_bus", placeholder="Ej: monitor, silla...")

        df_elim = get_inventario(
            laboratorio=None if f_lab_el == "Todos" else f_lab_el,
            busqueda=f_bus_el if f_bus_el.strip() else None,
        )

        if df_elim.empty:
            st.info("No hay registros que coincidan con los filtros.")
        else:
            cols_el = ["id", "descripcion", "marca", "serie", "estado", "laboratorio", "num_inventario"]
            df_el_disp = df_elim[cols_el].copy()
            df_el_disp.columns = ["ID", "Descripción", "Marca", "Serie", "Estado", "Laboratorio", "N° Inventario"]
            st.dataframe(df_el_disp, use_container_width=True, hide_index=True)

            st.markdown("---")
            opciones_elim = {
                f"ID #{r['id']}  |  {r['descripcion']}  |  Lab {r['laboratorio']}  |  {r['estado']}": r['id']
                for _, r in df_elim.iterrows()
            }
            sel_elim = st.selectbox(
                "Selecciona el item a eliminar:",
                ["— Elige un item —"] + list(opciones_elim.keys()),
                key="inv_sel_elim",
            )

            if sel_elim != "— Elige un item —":
                id_eliminar = opciones_elim[sel_elim]
                item_elim = df_elim[df_elim["id"] == id_eliminar].iloc[0]

                # Tarjeta de confirmación
                st.error(
                    f"**ID #{id_eliminar}** — {item_elim['descripcion']} — "
                    f"Lab **{item_elim['laboratorio']}** — Estado: {item_elim['estado']}"
                )

                with st.form("form_inv_eliminar"):
                    confirmar = st.checkbox(f"Confirmo que deseo eliminar el item ID #{id_eliminar} del inventario activo")
                    if st.form_submit_button("🗑️ Eliminar item", use_container_width=True):
                        if not confirmar:
                            st.error("⚠️ Activa la casilla de confirmación para continuar.")
                        else:
                            ok, msg = eliminar_item(id_eliminar, usuario_actual)
                            if ok:
                                st.success(f"✅ {msg}")
                                st.info(f"🗂️ Eliminado por **{usuario_actual}** el {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M')}")
                                registrar_auditoria(usuario_actual, st.session_state.num_empleado,
                                                    "INV_ELIMINAR",
                                                    f"ID #{id_eliminar}: {item_elim['descripcion']} Lab {item_elim['laboratorio']}")
                                st.rerun()
                            else:
                                st.error(f"⚠️ {msg}")
