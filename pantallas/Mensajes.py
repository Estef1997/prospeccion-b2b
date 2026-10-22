"""
Mensajes de WhatsApp, solo para quien puede recibirlos.

EL OTRO CANAL

De 629 negocios de Alajuela, 194 tienen celular (31%). A esos se les
puede escribir. A los otros 435 hay que ir o llamar al fijo, y esos
viven en la pantalla de Rutas.

El codigo decide el canal mirando un campo -- es_celular() en
reglas.py. El modelo solo escribe para los que ya pasaron ese filtro.

QUE HACE EL BOTON

"Abrir WhatsApp" arma un enlace wa.me con el mensaje ya escrito. Se
toca, abre WhatsApp con el texto puesto, y la persona lo revisa y lo
manda. No se envia nada solo: mandar en frio de forma automatica es la
via rapida a que bloqueen el numero.

Despues se marca que paso. Eso es el ancla: hasta que alguien conteste,
el puntaje que ordena los 629 es una hipotesis.
"""

from urllib.parse import quote

import streamlit as st

import inicio
import registro
import zonas
from reglas import es_celular

# NO se llama a inicio.preparar() aca. Lo hace app.py una sola vez,
# antes del menu (ver su docstring).

ORIGEN = "prospectos_calificados.json"


@st.cache_data
def cargar():
    import json
    import os

    if not os.path.exists(ORIGEN):
        return []
    with open(ORIGEN, encoding="utf-8") as f:
        datos = json.load(f)

    # Tres condiciones: tiene mensaje, paso el validador, y se le puede
    # escribir. Un mensaje que no paso no se manda -- para eso se hizo
    # el validador.
    listos = [d for d in datos
              if d.get("mensaje")
              and d.get("validacion") != "revisar"
              and es_celular(d.get("telefono"))]
    listos.sort(key=lambda x: x.get("puntaje") or 0, reverse=True)
    return listos


def enlace_whatsapp(negocio):
    numero = "".join(c for c in (negocio.get("telefono") or "")
                     if c.isdigit())[-8:]
    return f"https://wa.me/506{numero}?text={quote(negocio['mensaje'])}"


def tarjeta(i, n, anotado):
    estado = anotado.get("estado", "")
    marca = {"interesado": "🟢", "no": "🔴", "enviado": "🟡",
             "sin respuesta": "⚪", "mal numero": "⚫"}.get(estado, "")

    with st.expander(
        f"{marca} {i}. {n['nombre']} — {n.get('canton', '')} · "
        f"{n.get('puntaje', 0):.0f} pts",
        expanded=not estado,
    ):
        st.code(n["mensaje"], language=None, wrap_lines=True)

        st.link_button("💬 Abrir WhatsApp", enlace_whatsapp(n),
                       use_container_width=True, type="primary")
        st.caption(f"{n['telefono']} · se abre con el mensaje escrito, "
                   f"para revisarlo antes de mandar")

        st.divider()

        pid = n["place_id"]
        nuevo_estado = st.radio(
            "Qué pasó", registro.ESTADOS,
            index=registro.ESTADOS.index(estado),
            format_func=lambda e: e or "sin tocar",
            key=f"e_{pid}", horizontal=True,
        )

        mandado = anotado.get("mensaje", "")
        nuevo_mensaje = st.radio(
            "Qué mandaste", registro.MENSAJES,
            index=registro.MENSAJES.index(mandado),
            format_func=lambda m: m or "sin tocar",
            key=f"m_{pid}", horizontal=True,
            help="Si casi todos salen 'editado', el redactor no sirve. "
                 "Es la cifra que lo mide.",
        )

        notas = st.text_input(
            "Notas — sobre todo si pidió otro producto",
            value=anotado.get("notas", ""),
            placeholder="ej: no compra salchichón, preguntó por chorizo",
            key=f"n_{pid}",
        )

        if st.button("Guardar", key=f"g_{pid}", use_container_width=True):
            enviado = anotado.get("enviado", "")
            if nuevo_estado and not enviado:
                enviado = registro.fecha_de_hoy()

            st.session_state.registros = registro.anotar(
                st.session_state.registros, pid,
                estado=nuevo_estado, enviado=enviado,
                mensaje=nuevo_mensaje, notas=notas,
                # Para que la hoja se pueda leer. Ver registro.anotar().
                nombre=n.get("nombre", ""), canton=n.get("canton", ""),
            )
            registro.guardar(st.session_state.registros)
            st.rerun()


def main():
    st.title("💬 Mensajes")
    inicio.aviso_de_almacen()

    if "registros" not in st.session_state:
        st.session_state.registros = registro.cargar()

    negocios = cargar()
    if not negocios:
        st.warning(
            "No hay mensajes validados para negocios con celular.\n\n"
            "Corré `python grafo.py whatsapp 20` para generarlos."
        )
        _cuantos_hay()
        return

    provincias = sorted({d.get("provincia") for d in negocios
                         if d.get("provincia")})
    provincia = st.selectbox("Provincia", provincias)
    lista = [n for n in negocios if n.get("provincia") == provincia]

    cantones = sorted({d.get("canton") for d in lista if d.get("canton")})
    elegidos = st.multiselect("Cantón", cantones,
                              placeholder="Toda la provincia")
    if elegidos:
        lista = [n for n in lista if n.get("canton") in elegidos]

    r = registro.resumen(st.session_state.registros)
    a, b, c = st.columns(3)
    a.metric("Listos", len(lista))
    b.metric("Enviados", r["enviados"])
    if r["tasa_respuesta"] is not None:
        c.metric("Contestaron", f"{r['tasa_respuesta']:.0%}")

    if r["tasa_tal_cual"] is not None and r["enviados"] >= 5:
        st.caption(
            f"**{r['tasa_tal_cual']:.0%} se mandaron sin editar.** "
            f"Si eso es bajo, el redactor no está sirviendo aunque haya "
            f"respuestas."
        )

    st.divider()

    for i, n in enumerate(lista, 1):
        tarjeta(i, n, st.session_state.registros.get(n["place_id"], {}))

    st.divider()
    st.caption(
        "Solo aparecen los negocios con celular. A los demás se les "
        "llega por la pantalla de Rutas: llamando al fijo o visitando."
    )


def _cuantos_hay():
    """Para que el aviso diga cuantos habria, no solo que no hay."""
    datos = zonas.cargar()
    if not datos:
        return
    v = zonas.visitables(datos)
    con = sum(1 for d in v if es_celular(d.get("telefono")))
    st.caption(f"Hay {con} negocios con celular de {len(v)} visitables "
               f"({con / len(v):.0%}) esperando mensaje.")


main()