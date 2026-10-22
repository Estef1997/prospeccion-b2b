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

FALLA CERRADA

Si no hay clave configurada, el app NO abre. Podria abrirse sin clave
"porque todavia no la configuraron", pero esa es exactamente la forma
en que algo queda publico sin que nadie se entere.

Para correrlo en la maquina de desarrollo hay que crear
`.streamlit/secrets.toml` con:

    clave = "lo que sea"

Ese archivo esta en .gitignore y no sube nunca.
"""

import hmac

import streamlit as st

MENSAJE_SIN_CLAVE = """
**El app no tiene clave configurada y por eso no abre.**

En Streamlit Cloud: Settings → Secrets, y agregar
`clave = "..."`.

En esta máquina: crear el archivo `.streamlit/secrets.toml` con la
misma línea.
"""


def _clave_configurada():
    try:
        return st.secrets.get("clave")
    except Exception:
        # Sin archivo de secrets, st.secrets lanza excepcion en vez de
        # devolver vacio.
        return None


def pedir():
    """Muestra la puerta y corta la pagina si no pasa.

    Se llama al principio de cada pantalla. En Streamlit no hay forma de
    proteger "el app entero" desde un solo lugar: cada pagina es un
    script aparte y se puede abrir por su URL directa. Olvidarlo en una
    pagina deja esa pagina abierta.
    """
    esperada = _clave_configurada()

    if not esperada:
        st.error(MENSAJE_SIN_CLAVE)
        st.stop()

    if st.session_state.get("adentro"):
        return

    st.markdown("### Embutidos Artesanales")
    st.caption("Lista de prospectos. Pedí la clave a quien desarrolla.")

    with st.form("entrar"):
        intento = st.text_input("Clave", type="password")
        if st.form_submit_button("Entrar", use_container_width=True,
                                 type="primary"):
            # compare_digest en vez de ==: compara en tiempo constante.
            # A esta escala no cambia nada en la practica, pero es la
            # forma correcta de comparar un secreto y no cuesta mas.
            if hmac.compare_digest(intento, str(esperada)):
                st.session_state["adentro"] = True
                st.rerun()
            else:
                st.error("Clave incorrecta.")

    st.stop()