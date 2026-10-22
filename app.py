"""
Punto de entrada. La clave, el estilo, dónde se guarda, y el menú.

    python -m streamlit run app.py

Este archivo no muestra una pantalla propia. Prepara el app y entrega el
control a Rutas o a Mensajes.

POR QUE SE QUITO LA PORTADA (12/10/2026)

Hasta hoy esto era una portada: tres cifras, un párrafo de "a dónde ir",
y el botón de recargar datos.

quien desarrolla la vio ya desplegada y dijo que con Rutas y Mensajes bastaba.
Tenía razón, y conviene escribir el motivo real en vez del cómodo.

**El cómodo:** dos pantallas no necesitan un índice.

**El real:** la portada existía porque Streamlit exige un archivo
principal, no porque alguien la necesitara. El 08/10 este archivo dejó
de servir para registrar respuestas, hacía falta que fuera *algo*, y se
convirtió en portada con una justificación bien escrita. Una
restricción de la plataforma disfrazada de decisión de producto.

**Y el síntoma que lo delataba:** la portada tenía otro usuario que el
resto del app. "Cuántos contestaron" y "dónde se guardan las
respuestas" son cifras de quien analiza, no del rutero. Él abre el app parado
junto al camión, con una mano ocupada y una sola decisión que tomar.
Que lo primero que vea sea su zona, no un resumen de su zona.

LO QUE HUBO QUE RESCATAR

Tres cosas vivían SOLO en la portada. Si se van con ella, se van en
silencio -- que es el patrón que este proyecto ya repitió cuatro veces.

| qué | a dónde se fue |
|---|---|
| botón de recargar datos | la barra lateral, acá abajo |
| dónde se guardan las respuestas | la barra lateral, acá abajo |
| cuántos contestaron | ya estaba en Mensajes |

POR QUE SE LLAMA app.py Y NO Inicio.py

Porque no se puede cambiar. Streamlit Cloud fija el *Main file path* al
desplegar y **no deja cambiarlo después**: para corregirlo hay que
borrar el app y volver a crearlo. Pasó el 12/10 con `acceso.py`.

El nombre del archivo quedó fijo; el nombre que ve la persona lo pone
`st.Page(title=...)`. Son dos cosas distintas y es mejor así: el menú
dice "Rutas", no "app".

POR QUE LA CARPETA SE LLAMA pantallas/ Y NO pages/

**Esto es seguridad, no estética. No se renombra.**

Streamlit tiene dos formas de armar el menú. La vieja convierte en
pantalla **todo** archivo dentro de una carpeta llamada exactamente
`pages/`. La nueva, `st.navigation`, las declara una por una.

Se pasó a la nueva por tres razones, en orden de peso:

1. **La clave no se puede olvidar.** Antes cada pantalla llamaba a
   `inicio.preparar()`; una pantalla nueva que se olvidara quedaba
   abierta. Ahora el portón está acá, antes del menú.
2. **El accidente del 07/10.** `revisar.py` se copió dentro de `pages/`
   y con la forma vieja habría salido en el menú y reventado al abrirlo.
   Si no está en PANTALLAS, no existe para el app.
3. El nombre que ve la persona deja de depender del nombre del archivo.

**Y acá está el agujero que eso abrió, encontrado el 12/10 probando el
app con un navegador de verdad antes de publicarlo.**

La documentación dice que `st.navigation` hace que Streamlit ignore
`pages/`. Es cierto -- *si se llega a ejecutar*. Pero `acceso.pedir()`
corta con `st.stop()` cuando no hay clave, o sea **antes** de la línea
de `st.navigation`. Streamlit nunca se entera del menú nuevo, vuelve al
mecanismo viejo, y cada archivo de `pages/` pasa a ser un script suelto
que ya no pide la clave.

Medido, no supuesto:

    GET /Rutas  ->  pide clave: NO
                    muestra datos: SI

Cualquiera con el enlace veía los 3.349 negocios.

El arreglo no es reordenar las líneas -- eso deja el agujero esperando
a la próxima vez que algo corte antes del menú. El arreglo es que
**no exista ninguna carpeta llamada `pages/`**, para que no haya nada
que descubrir. Una vulnerabilidad que depende del orden de ejecución
vuelve; una carpeta que no existe, no.

`verificar_estructura.py` falla si `pages/` reaparece.
"""

import streamlit as st

import inicio
import registro

# Antes que cualquier otro comando de Streamlit, y antes del menú: si la
# clave no está, acá se corta y no se llega a ninguna pantalla.
inicio.preparar("Embutidos Artesanales", "📍")

# La lista es la única fuente de verdad del menú. Una pantalla nueva se
# agrega acá; un archivo en pantallas/ que no esté acá, no se muestra.
PANTALLAS = [
    st.Page("pantallas/Rutas.py", title="Rutas", default=True),
    st.Page("pantallas/Mensajes.py", title="Mensajes"),
]


def pie():
    """Lo que vivía en la portada y no tenía otro lugar.

    Va en la barra lateral para que esté en las dos pantallas sin
    repetir el código en cada una.
    """
    with st.sidebar:
        # Sin <hr> propio: Streamlit ya dibuja un separador debajo del
        # menu. Dos lineas seguidas dejaban una banda vacia.

        # Los datos se guardan en memoria con @st.cache_data; si cambia
        # el JSON, sin esto hay que reiniciar el servidor. Hacía falta
        # desde que toolbarMode = "minimal" se llevó "Clear cache".
        if st.button("Recargar datos", use_container_width=True,
                     help="Después de correr prospecto.py o grafo.py."):
            st.cache_data.clear()
            st.rerun()

        # Si quien anota no sabe dónde quedó lo que anotó, no puede
        # confiar en el app.
        st.markdown(
            f'<p class="canal">Las respuestas se guardan en '
            f'{registro.donde()}.</p>', unsafe_allow_html=True)

        inicio.aviso_de_almacen()


st.navigation(PANTALLAS).run()
pie()