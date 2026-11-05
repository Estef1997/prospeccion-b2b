"""
Prospectos por zona, para el vendedor que anda en ruta.

PARA QUE ES

El vendedor sale a repartir y, de paso, busca clientes nuevos. Hoy eso
es entrar a ver que aparece. Esta pantalla le dice, antes de bajarse,
que hay en la zona y a que entra.

El punto no es ahorrar kilometros: es llegar sabiendo.

COMO SE VE Y POR QUE

Las decisiones de diseño estan en estilo.py. Aqui solo se usan.

Lo que hay que saber para tocar esta pantalla: el nombre del negocio es
lo unico grande, y las dos acciones -- Llamar y Como llegar -- son
botones amarillos de altura de pulgar. Todo lo demas se mantiene
callado a proposito.

NO LLAMA AL MODELO

Lee prospectos_crudo.json. El puntaje y las banderas los calculo
prospecto.py con codigo determinista, asi que esto funciona sobre todo
el archivo sin costo y sin esperar. La logica esta en zonas.py.
"""

import streamlit as st

import zonas
from reglas import como_html, es_celular, normalizar

# NO se llama a inicio.preparar() aca. Lo hace app.py una sola vez,
# antes del menu (ver su docstring). Si esta pantalla lo llamara otra
# vez, set_page_config se ejecutaria dos veces y Streamlit tira error.


@st.cache_data
def cargar():
    return zonas.cargar()


def _tel(numero):
    return "".join(c for c in numero if c.isdigit() or c == "+")


def tarjeta(i, n):
    # TODO lo que venga del negocio pasa por como_html() antes de entrar
    # a unsafe_allow_html. El nombre, la categoria y la direccion los
    # escribio Google, o sea un tercero. Ver reglas.como_html().
    st.markdown(
        f'<p class="negocio"><span class="orden">{i}</span>'
        f'{como_html(n["nombre"])}</p>',
        unsafe_allow_html=True,
    )

    donde = [n.get("canton"), n.get("categoria")]
    if n.get("distancia_km") is not None:
        donde.append(f"{n['distancia_km']:.0f} km de Palmares")
    st.markdown(f'<p class="donde">'
                f'{" · ".join(como_html(x) for x in donde if x)}'
                f'</p>', unsafe_allow_html=True)

    direccion = zonas.direccion_corta(n)
    if direccion:
        st.markdown(f'<p class="direccion">{como_html(direccion)}</p>',
                    unsafe_allow_html=True)

    telefono = n.get("telefono")
    izq, der = st.columns(2)

    if telefono:
        izq.link_button(f"Llamar  {telefono}", f"tel:{_tel(telefono)}",
                        use_container_width=True, type="primary")
    else:
        izq.markdown('<p class="donde">Sin teléfono</p>',
                     unsafe_allow_html=True)

    der.link_button("Cómo llegar", zonas.enlace_maps(n),
                    use_container_width=True, type="primary")

    # El canal es un dato; los avisos son advertencias. Distinto peso,
    # distinto color.
    # Hoy canal() y avisos() devuelven frases fijas nuestras, pero las
    # dos reciben el negocio: el dia que alguna interpole el nombre, el
    # agujero vuelve sin que nadie toque esta linea.
    st.markdown(f'<p class="canal">{como_html(zonas.canal(n))}</p>',
                unsafe_allow_html=True)
    for aviso in zonas.avisos(n):
        st.markdown(f'<p class="aviso">{como_html(aviso)}</p>',
                    unsafe_allow_html=True)

    st.markdown('<hr class="corte">', unsafe_allow_html=True)


def main():
    st.title("Prospectos")

    datos = cargar()
    if not datos:
        st.warning(
            f"No encuentro {zonas.ORIGEN} en esta carpeta. "
            f"Lo escribe `python prospecto.py buscar <Provincia>`."
        )
        return

    provincias = sorted({d.get("provincia") for d in datos
                         if d.get("provincia")})
    por_defecto = (provincias.index(zonas.PROVINCIA_POR_DEFECTO)
                   if zonas.PROVINCIA_POR_DEFECTO in provincias else 0)

    provincia = st.selectbox("Provincia", provincias, index=por_defecto)

    visitables = zonas.de_provincia(zonas.visitables(datos), provincia)
    conteo = dict(zonas.cantones_con_conteo(visitables))

    cantones = st.multiselect(
        "Cantón", list(conteo), placeholder="Toda la provincia",
        format_func=lambda c: f"{c} ({conteo[c]})",
    )

    # Sin filtrar por marca, para poder decir cuántas se escondieron.
    completa = zonas.ruta(datos, provincia=provincia, cantones=cantones,
                          por_marca=None)

    with st.expander("Buscar y ordenar"):
        texto = st.text_input(
            "Buscar por nombre",
            placeholder="¿Está este negocio en la lista?")
        orden = st.radio("Ordenar por", ["Puntaje", "Más cerca"],
                         horizontal=True)
        solo_celular = st.checkbox("Solo los que tienen celular",
                                   help="Para llamar antes de ir.")
        todas_sucursales = st.checkbox(
            "Todas las sucursales de cadenas",
            help="Por defecto se muestra una por cadena, para que cinco "
                 "Palís no tapen a los independientes.")

    lista = completa if todas_sucursales else zonas.una_por_marca(completa)
    escondidas = len(completa) - len(lista)

    if texto:
        t = normalizar(texto)
        lista = [n for n in lista if t in normalizar(n.get("nombre"))]
    if solo_celular:
        lista = [n for n in lista if es_celular(n.get("telefono"))]
    if orden == "Más cerca":
        lista = sorted(lista, key=lambda d: (d.get("distancia_km") is None,
                                             d.get("distancia_km") or 0))

    if not lista:
        st.info("No hay negocios con ese filtro.")
        return

    con_cel = sum(1 for n in lista if es_celular(n.get("telefono")))
    st.markdown(
        f'<p class="puntaje">{len(lista)} negocios · {con_cel} se pueden '
        f'llamar al celular antes de ir</p>',
        unsafe_allow_html=True,
    )

    # Esconder sin decirlo seria peor que no esconder.
    if escondidas:
        st.markdown(
            f'<p class="canal">Se muestra una sucursal por cadena. '
            f'Hay {escondidas} sucursales más; se ven marcando '
            f'"Todas las sucursales" arriba.</p>',
            unsafe_allow_html=True,
        )

    st.download_button("Bajar la lista", _csv(lista),
                       file_name=f"prospectos_{normalizar(provincia)}.csv",
                       mime="text/csv", use_container_width=True,
                       help="Para tenerla a mano donde no hay señal.")

    st.markdown('<hr class="corte">', unsafe_allow_html=True)

    tope = 25
    for i, n in enumerate(lista[:tope], 1):
        tarjeta(i, n)

    if len(lista) > tope:
        st.markdown(
            f'<p class="donde">Hay {len(lista) - tope} más. Filtrá por '
            f'cantón para verlos, o bajá la lista completa.</p>',
            unsafe_allow_html=True)

    st.markdown(
        '<p class="donde">El puntaje viene de las reseñas, el rating, la '
        'categoría y si hay forma de contactar. Todavía no está '
        'comprobado contra ventas reales.</p>',
        unsafe_allow_html=True)


def _csv(lista):
    import csv
    import io

    campos = ["nombre", "categoria", "canton", "direccion", "telefono",
              "puntaje", "rating", "num_resenas"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Negocio", "Categoria", "Canton", "Direccion", "Telefono",
                "Puntaje", "Rating", "Resenas", "Avisos"])
    for n in lista:
        w.writerow([n.get(c, "") for c in campos]
                   + ["; ".join(zonas.avisos(n))])
    return buf.getvalue().encode("utf-8-sig")


main()
