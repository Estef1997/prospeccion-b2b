"""
Lo que toda pantalla hace antes de mostrar nada.

POR QUE EXISTE

Tres cosas tienen que pasar al abrir cualquier pagina, en este orden:
configurar la pagina, pedir la clave, y decidir donde se guardan las
respuestas.

Podrian copiarse en cada pantalla. Pero si alguien agrega una pantalla
nueva y se le olvida pedir la clave, esa pantalla queda abierta y nadie
se entera.

QUIEN LLAMA A ESTO (cambio del 12/10/2026)

**Solo app.py, una vez.** Antes lo llamaba cada pantalla.

Con `st.navigation` el archivo de entrada corre SIEMPRE antes de la
pantalla elegida, asi que el porton vive ahi y ninguna pantalla puede
saltarselo. Antes dependia de que quien escribiera la pantalla nueva se
acordara; ahora no hay nada que acordarse.

EL ORDEN IMPORTA

set_page_config tiene que ser el PRIMER comando de Streamlit de la
sesion. Si se llama despues de cualquier otro, Streamlit tira error. Por
eso vive aca adentro y no en cada pantalla.
"""

import streamlit as st

import acceso
import estilo
import registro

# Si las respuestas estan yendo a la hoja de Google (True) o al disco
# del servidor (False). Lo fija preparar() y lo leen las pantallas.
#
# Vive aca y no se pasa de mano en mano porque con st.navigation quien
# llama a preparar() -- app.py -- no es quien dibuja la pantalla. Pasarlo
# como argumento obligaria a cada pantalla a ir a buscarlo a app.py, y
# eso es una dependencia al reves.
EN_LA_HOJA = None


@st.cache_resource
def _elegir_almacen():
    """Hoja de Google si se puede; si no, archivo local.

    @st.cache_resource hace que esto corra UNA vez por servidor, no en
    cada interaccion. Streamlit vuelve a correr el script entero cada
    vez que alguien toca algo, y conectarse a Google en cada clic seria
    lento y gastaria cuota.

    Por que la hoja tambien cuando se corre local: para que no haya dos
    lugares con lo mismo. Si local guardara en archivo y la nube en la
    hoja, al primer uso en los dos lados habria dos verdades distintas.
    Es el bug de CONTEXTO_FABRICA otra vez, con datos en vez de reglas.
    """
    try:
        import almacen_sheets

        if almacen_sheets.disponible():
            registro.usar(almacen_sheets)
            return True
    except Exception:
        pass

    registro.usar(None)
    return False


def preparar(titulo, icono):
    """Configura, pide la clave, elige donde guardar.

    Lo llama app.py una sola vez, antes del menu. Devuelve True si las
    respuestas van a la hoja, y lo deja tambien en EN_LA_HOJA para que
    las pantallas no tengan que recibirlo.

    Por que importa avisar cuando NO van: si alguien anota veinte
    respuestas creyendo que se guardan en un lugar seguro y en realidad
    estan en un disco que se borra al reiniciar, eso se tiene que ver.
    """
    global EN_LA_HOJA
    st.set_page_config(page_title=titulo, page_icon=icono,
                       layout="centered")
    estilo.aplicar()
    acceso.pedir()
    EN_LA_HOJA = _elegir_almacen()
    return EN_LA_HOJA


def aviso_de_almacen(en_la_hoja=None):
    """Una linea gris al pie, solo cuando hay algo que advertir.

    Sin argumento usa lo que dejo preparar(), que es lo normal. Se puede
    pasar uno explicito para probarlo sin levantar Streamlit.
    """
    if en_la_hoja is None:
        en_la_hoja = EN_LA_HOJA
    if en_la_hoja:
        return
    st.markdown(
        '<p class="aviso">Las respuestas se están guardando en este '
        'servidor y se pierden si reinicia. Avisale a quien desarrolla.</p>',
        unsafe_allow_html=True,
    )