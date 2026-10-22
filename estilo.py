"""
El aspecto del app, en un solo lugar.

PARA QUIEN ES

Un rutero parado junto al camion, con sol en la pantalla, una mano
ocupada, decidiendo una sola cosa: entro aqui o no.

LAS DECISIONES Y POR QUE

Fondo blanco puro, no crema. El crema se ve bien en una oficina y
pierde contraste bajo sol directo.

Amarillo señal (#F2B705) en los botones de accion. Es el color mas
visible al aire libre -- el de las señales de transito. El ladrillo
oscuro de la marca queda para los controles, que se tocan menos.

Archivo, una sola familia. Es una grotesca compacta hecha para rotulos
y letra chica: aguanta pantalla sucia y poca luz. Tres pesos alcanzan;
una segunda familia aqui seria decoracion.

El nombre del negocio es lo unico grande. Es el dato que se busca con
la vista, y en una lista de veinte es lo unico que distingue una
tarjeta de otra.

Sin cajas con sombra. Una linea fina entre negocios alcanza, y en un
telefono las cajas anidadas se comen el ancho. Lo que diferencia una
tarjeta de otra es lo que dice, no su marco.

CUIDADO

Streamlit cambia los nombres internos de sus clases entre versiones.
Esto apunta a elementos y a data-testid, que son mas estables, pero si
algun dia el app se ve raro despues de actualizar Streamlit, el
sospechoso es este archivo -- no la logica.
"""

import streamlit as st

TINTA = "#241414"
LADRILLO = "#8C1C13"
AMARILLO = "#F2B705"
GRIS = "#6B625E"
LINEA = "#E8E0DB"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&display=swap');

html, body, button, input, textarea, select,
[data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{
    font-family: 'Archivo', system-ui, sans-serif;
}}

/* Los iconos de Streamlit son una fuente de ligaduras: el navegador
   recibe el texto "keyboard_arrow_right" y la fuente lo dibuja como
   flecha. Si se les cambia la familia, se ve el nombre escrito.
   Paso del 06/10: le habia puesto Archivo a todo y aparecia
   "_arrow_right" encima del titulo de los expanders. */
[data-testid="stIconMaterial"],
span.material-icons, span.material-icons-outlined,
[data-testid*="Icon"] span {{
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}}

/* La cabecera de Streamlit no dice nada util en un telefono. */
header[data-testid="stHeader"] {{ display: none; }}
footer {{ display: none; }}

.block-container {{
    padding-top: 1.2rem;
    padding-bottom: 4rem;
    max-width: 46rem;
}}

h1 {{
    font-weight: 700;
    letter-spacing: -0.02em;
    font-size: 1.75rem;
    color: {TINTA};
}}

/* Botones: altura de pulgar, no de mouse. */
.stButton > button,
.stLinkButton > a,
.stDownloadButton > button {{
    min-height: 3rem;
    font-weight: 600;
    font-size: 1rem;
    border-radius: 0.5rem;
    border: 1.5px solid {LINEA};
}}

/* Las dos acciones que se tocan con sol encima. */
.stLinkButton > a[kind="primary"],
.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {{
    background: {AMARILLO} !important;
    color: {TINTA} !important;
    border: none !important;
}}

/* El nombre del negocio: lo unico grande de la tarjeta. */
.negocio {{
    font-size: 1.3rem;
    font-weight: 600;
    line-height: 1.2;
    letter-spacing: -0.015em;
    color: {TINTA};
    margin: 0 0 0.15rem 0;
}}
.negocio .orden {{
    color: {GRIS};
    font-weight: 400;
    font-size: 0.95rem;
    margin-right: 0.4rem;
}}
.donde {{
    color: {GRIS};
    font-size: 0.9rem;
    margin: 0 0 0.5rem 0;
}}
.direccion {{
    color: {TINTA};
    font-size: 0.95rem;
    margin: 0 0 0.8rem 0;
}}
/* El canal es informacion: como se le llega a este negocio. */
.canal {{
    color: {GRIS};
    font-size: 0.85rem;
    margin: 0.7rem 0 0 0;
}}

/* El aviso es una advertencia: algo que puede cambiar la decision. */
.aviso {{
    color: {LADRILLO};
    font-size: 0.85rem;
    margin: 0.25rem 0 0 0;
}}
.corte {{
    border: none;
    border-top: 1px solid {LINEA};
    margin: 1.6rem 0 1.2rem 0;
}}

/* El puntaje existe, pero el orden de la lista ya dice el ranking. */
.puntaje {{
    color: {GRIS};
    font-size: 0.9rem;
    font-variant-numeric: tabular-nums;
}}
</style>
"""


def aplicar():
    st.markdown(CSS, unsafe_allow_html=True)