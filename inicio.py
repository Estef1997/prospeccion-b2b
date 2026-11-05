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

import os

import streamlit as st

import acceso
import estilo
import registro

# Los tres estados posibles del almacen. El app los lee para decidir
# que avisar y si deja guardar.
EN_LA_HOJA_OK = "hoja"
SOLO_LECTURA = "solo_lectura"
LOCAL_DESARROLLO = "local"

# Lo que hay que escribir, a mano y a proposito, para habilitar el
# disco local. Cualquier otro valor -- y la ausencia -- es produccion.
MODO_DESARROLLO = "desarrollo"

# Si las respuestas estan yendo a la hoja de Google (True) o al disco
# del servidor (False). Lo fija preparar() y lo leen las pantallas.
#
# Vive aca y no se pasa de mano en mano porque con st.navigation quien
# llama a preparar() -- app.py -- no es quien dibuja la pantalla. Pasarlo
# como argumento obligaria a cada pantalla a ir a buscarlo a app.py, y
# eso es una dependencia al reves.
EN_LA_HOJA = None

# Cual de los tres estados quedo. Lo fija preparar().
ESTADO_ALMACEN = None


def modo_desarrollo():
    """True solo si alguien lo pidio explicitamente.

    Se lee de los secrets (`modo = "desarrollo"`) o de la variable de
    entorno EMBUTIDOS_MODO. La variable existe para poder correr el app
    local sin tocar los secrets.

    ORIGEN (03/11/2026): antes no habia modo. El disco local era el
    camino por defecto cuando Google no contestaba, y por defecto es
    exactamente donde no tiene que estar -- hospedado, ese disco se
    borra al reiniciar. Ahora el disco local hay que pedirlo
    escribiendolo.
    """
    try:
        if str(st.secrets.get("modo", "")).strip().lower() == MODO_DESARROLLO:
            return True
    except Exception:
        # Sin archivo de secrets, st.secrets lanza en vez de devolver
        # vacio. No tener secrets no es estar en desarrollo.
        pass
    return (os.environ.get("EMBUTIDOS_MODO", "").strip().lower()
            == MODO_DESARROLLO)


@st.cache_resource
def _hoja_conectada():
    """El modulo de la hoja, ya conectado. Solo se cachea el EXITO.

    @st.cache_resource no guarda nada cuando la funcion lanza, asi que
    un fallo se vuelve a intentar en la siguiente interaccion. Eso es el
    arreglo del hallazgo 1b: antes esta funcion devolvia True o False, y
    el False quedaba cacheado para toda la vida del servidor -- un corte
    de red de diez segundos al arrancar condenaba la sesion entera a
    escribir en un disco efimero.

    Se llama a conectar() y no a disponible() porque disponible() se
    come la excepcion y devuelve False, y una funcion que no lanza no se
    puede distinguir de una que funciono. Justo lo que hay que cachear.
    """
    import almacen_sheets

    almacen_sheets.conectar()
    return almacen_sheets


def _fuente_para_leer():
    """El modulo de la hoja, conectado o no, para poder reintentar."""
    try:
        import almacen_sheets

        return almacen_sheets
    except Exception:
        return None


def elegir_almacen():
    """Decide donde van las respuestas. Devuelve uno de los tres estados.

    El orden es deliberado: la hoja primero, siempre. El disco local
    SOLO si alguien pidio el modo desarrollo. Y si no hay ninguno de los
    dos, solo lectura con error visible -- nunca un guardado que se va a
    perder en silencio.

    Por que la hoja tambien cuando se corre local: para que no haya dos
    lugares con lo mismo. Si local guardara en archivo y la nube en la
    hoja, al primer uso en los dos lados habria dos verdades distintas.
    Es el bug de CONTEXTO_FABRICA otra vez, con datos en vez de reglas.
    """
    try:
        registro.usar(_hoja_conectada())
        return EN_LA_HOJA_OK
    except Exception:
        pass

    if modo_desarrollo():
        registro.usar(None)
        return LOCAL_DESARROLLO

    registro.usar(registro.solo_lectura(_fuente_para_leer()))
    return SOLO_LECTURA


def preparar(titulo, icono):
    """Configura, pide la clave, elige donde guardar.

    Lo llama app.py una sola vez, antes del menu. Devuelve True si las
    respuestas van a la hoja, y lo deja tambien en EN_LA_HOJA para que
    las pantallas no tengan que recibirlo.

    Por que importa avisar cuando NO van: si alguien anota veinte
    respuestas creyendo que se guardan en un lugar seguro y en realidad
    estan en un disco que se borra al reiniciar, eso se tiene que ver.
    """
    global EN_LA_HOJA, ESTADO_ALMACEN
    st.set_page_config(page_title=titulo, page_icon=icono,
                       layout="centered")
    estilo.aplicar()
    acceso.pedir()
    ESTADO_ALMACEN = elegir_almacen()
    EN_LA_HOJA = ESTADO_ALMACEN == EN_LA_HOJA_OK
    return EN_LA_HOJA


def texto_de_aviso(estado=None):
    """El aviso que corresponde al estado, o None si no hay que avisar.

    Separado de aviso_de_almacen() para poder probarlo sin levantar
    Streamlit. Devuelve (severidad, texto).
    """
    if estado is None:
        estado = ESTADO_ALMACEN

    if estado == SOLO_LECTURA:
        return ("error",
                "**No se puede guardar nada en este momento.** La hoja de "
                "Google no responde, así que lo que anotés se perdería. "
                "Podés seguir viendo la lista y los mensajes. La conexión "
                "se reintenta sola; si no vuelve, avisale a quien desarrolla.")
    if estado == LOCAL_DESARROLLO:
        return ("aviso",
                "Modo desarrollo: las respuestas se están guardando en "
                "este servidor y se pierden si reinicia.")
    return None


def aviso_de_almacen(estado=None):
    """Lo que hay que advertir sobre donde se guardan las respuestas.

    Sin argumento usa lo que dejo preparar(), que es lo normal. Se puede
    pasar uno explicito para probarlo sin levantar Streamlit.

    El solo lectura va con st.error y no con una linea gris al pie: es
    la diferencia entre "esto se guarda en otro lado" y "esto NO se
    guarda". Un aviso gris para lo segundo es lo mismo que no avisar.
    """
    aviso = texto_de_aviso(estado)
    if aviso is None:
        return

    severidad, texto = aviso
    if severidad == "error":
        st.error(texto)
    else:
        st.warning(texto)
