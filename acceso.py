"""
La puerta del app. Una clave, compartida.

POR QUE HAY CLAVE

No es por los negocios: sus nombres, telefonos y direcciones son
publicos en Google Maps, y cualquiera los puede buscar uno por uno.

Es por la LISTA. 3.485 negocios encontrados, filtrados, puntuados y
ordenados por zona es trabajo acumulado, y es un activo comercial del
negocio. Un enlace abierto se lo regala a quien lo encuentre.

Conviene tener clara la diferencia al explicarselo a alguien: no se
esta protegiendo la privacidad de terceros, se esta protegiendo el
trabajo propio.

POR QUE UNA SOLA CLAVE Y NO USUARIOS

Son tres o cuatro ruteros y el papa. Un sistema de usuarios serian
correos, recuperacion de contraseña y una tabla mas, para distinguir
entre personas que de todas formas ven lo mismo.

**Lo que se pierde, y conviene saberlo:** no hay forma de saber quien
entro, y si alguien se va hay que cambiarle la clave a todos. A esta
escala es el intercambio correcto; a veinte personas, no.

CAMBIAR LA CLAVE EXPULSA A TODOS (03/11/2026)

Antes no. Se cambiaba la clave en los secrets y las sesiones ya abiertas
seguian adentro, asi que "cambiar la clave porque alguien se fue" no
echaba a nadie: solo le impedia volver a entrar la proxima vez.

Ahora la sesion guarda una huella de la clave con la que entro. Si la
configurada deja de coincidir, la sesion se cae y hay que entrar de
nuevo. Se guarda la huella y no la clave: no hace falta tener el
secreto en la sesion para saber si cambio.

LIMITE DE INTENTOS, Y HASTA DONDE ALCANZA

Cinco intentos por sesion y un minuto de espera.

**Lo que NO hace, y conviene decirlo:** el contador vive en la sesion,
asi que alguien con un script abre una sesion nueva y el contador
vuelve a cero. Esto frena el tanteo a mano, no un ataque automatizado.

Se hizo per-sesion a proposito. Un contador compartido por todo el
servidor si frenaria el script, pero entonces cualquiera con el enlace
puede dejar a los tres ruteros afuera errando la clave veinte veces. A
esta escala, quedarse sin app en medio de la ruta es un dano mas
probable que el ataque que evitaria.

Lo que de verdad protege es que la clave sea larga. El limite es para
que el tanteo casual no sea gratis.

FALLA CERRADA

Si no hay clave configurada, el app NO abre. Podria abrirse sin clave
"porque todavia no la configuraron", pero esa es exactamente la forma
en que algo queda publico sin que nadie se entere.

Para correrlo en la maquina de desarrollo hay que crear
`.streamlit/secrets.toml` con:

    clave = "lo que sea"

Ese archivo esta en .gitignore y no sube nunca.
"""

import hashlib
import hmac
import time

import streamlit as st

MENSAJE_SIN_CLAVE = """
**El app no tiene clave configurada y por eso no abre.**

En Streamlit Cloud: Settings → Secrets, y agregar
`clave = "..."`.

En esta máquina: crear el archivo `.streamlit/secrets.toml` con la
misma línea.
"""


# Cinco intentos y un minuto. Ver el docstring del modulo para lo que
# este limite alcanza a frenar y lo que no.
MAX_INTENTOS = 5
ESPERA_SEGUNDOS = 60


def huella(clave):
    """Identifica la clave configurada SIN guardarla.

    Alcanza para detectar que cambio, que es lo unico que hace falta.
    Guardar la clave en la sesion para compararla seria tener el secreto
    en un lugar mas, sin ganar nada.
    """
    return hashlib.sha256(str(clave).encode("utf-8")).hexdigest()


def sesion_vigente(estado, huella_actual):
    """True si la sesion entro Y lo hizo con la clave que rige hoy."""
    return (bool(estado.get("adentro"))
            and estado.get("huella") == huella_actual)


def abrir(estado, huella_actual):
    """Deja la sesion adentro y anota con cual clave."""
    estado["adentro"] = True
    estado["huella"] = huella_actual
    estado["intentos"] = 0


def cerrar(estado):
    """Saca la sesion. No toca el contador de intentos."""
    estado["adentro"] = False
    estado["huella"] = None


def segundos_de_bloqueo(estado, ahora):
    """Cuanto falta para poder volver a intentar. 0 si no esta bloqueada."""
    return max(0, int(estado.get("bloqueada_hasta", 0) - ahora))


def anotar_fallo(estado, ahora):
    """Suma un intento fallido. Devuelve los segundos de bloqueo, o 0.

    El contador se reinicia al bloquear: la espera ya es el castigo, y
    dejarlo arriba haria que el intento siguiente bloquee de nuevo al
    primer error.
    """
    estado["intentos"] = int(estado.get("intentos", 0)) + 1
    if estado["intentos"] >= MAX_INTENTOS:
        estado["intentos"] = 0
        estado["bloqueada_hasta"] = ahora + ESPERA_SEGUNDOS
        return ESPERA_SEGUNDOS
    return 0


def intentos_restantes(estado):
    return MAX_INTENTOS - int(estado.get("intentos", 0))


def _clave_configurada():
    try:
        return st.secrets.get("clave")
    except Exception:
        # Sin archivo de secrets, st.secrets lanza excepcion en vez de
        # devolver vacio.
        return None


def pedir():
    """Muestra la puerta y corta la pagina si no pasa.

    Lo llama app.py una sola vez, antes del menu. En Streamlit no hay
    forma de proteger "el app entero" desde un solo lugar si las
    pantallas son scripts sueltos; por eso el porton vive en el archivo
    de entrada y la carpeta NO se llama pages/ (ver app.py).
    """
    esperada = _clave_configurada()

    if not esperada:
        st.error(MENSAJE_SIN_CLAVE)
        st.stop()

    actual = huella(esperada)
    estado = st.session_state

    if sesion_vigente(estado, actual):
        return

    # Entro con una clave que ya no rige: la cambiaron en los secrets.
    # Se cae la sesion aunque estuviera adentro.
    if estado.get("adentro"):
        cerrar(estado)
        st.warning("La clave cambió. Hay que entrar de nuevo.")

    st.markdown("### Embutidos Artesanales")
    st.caption("Lista de prospectos. Pedí la clave a quien desarrolla.")

    faltan = segundos_de_bloqueo(estado, time.time())
    if faltan:
        st.error(f"Demasiados intentos. Probá de nuevo en {faltan} "
                 f"segundos.")
        st.stop()

    with st.form("entrar"):
        intento = st.text_input("Clave", type="password")
        if st.form_submit_button("Entrar", use_container_width=True,
                                 type="primary"):
            # compare_digest en vez de ==: compara en tiempo constante.
            # A esta escala no cambia nada en la practica, pero es la
            # forma correcta de comparar un secreto y no cuesta mas.
            if hmac.compare_digest(intento, str(esperada)):
                abrir(estado, actual)
                st.rerun()
            else:
                espera = anotar_fallo(estado, time.time())
                if espera:
                    st.error(f"Demasiados intentos. Esperá {espera} "
                             f"segundos.")
                else:
                    st.error(f"Clave incorrecta. Quedan "
                             f"{intentos_restantes(estado)} intentos.")

    st.stop()
