"""
Prospectos ordenados por zona, para que un repartidor los visite.

OTRA PREGUNTA, OTRO ORDEN

El pipeline de WhatsApp pregunta "¿es buen prospecto?" y ordena todo el
pais por puntaje. Un repartidor pregunta otra cosa: "¿que me queda de
paso hoy?". Al de Palmares no le sirve el mejor prospecto de Limon.

Por eso aca la ZONA filtra y el puntaje solo ordena lo que quedo. Es el
orden inverso al del resto del proyecto, y es a proposito.

SIN MODELO

Esto lee prospectos_crudo.json, no prospectos_calificados.json. Las
banderas y el puntaje los calculo prospecto.py con codigo determinista,
asi que esta pantalla funciona sobre los 3.349 sin gastar un centavo ni
esperar una corrida.

La contra: estos negocios NO pasaron por el calificador, asi que puede
haber competidores que el nombre no delata. Por eso las banderas se
muestran en pantalla en vez de filtrarse en silencio -- el repartidor
decide con el negocio enfrente, que es mas de lo que puede hacer el
modelo.
"""

import json
import os
import re

from reglas import POR_MARCA, es_celular, marca, una_por_marca  # noqa: F401

ORIGEN = "prospectos_crudo.json"
PROVINCIA_POR_DEFECTO = "Alajuela"


def cargar(ruta=ORIGEN):
    if not os.path.exists(ruta):
        return []
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def visitables(datos):
    """Lo que tiene sentido que alguien visite.

    Mismo criterio que grafo.candidatos(), mas una condicion propia de
    este canal: tiene que haber direccion. Sin direccion el repartidor
    no sabe adonde ir, por bueno que sea el puntaje.
    """
    return [d for d in datos
            if not d.get("fuera_de_rubro")
            and not d.get("cerrado")
            and not d.get("es_cliente")
            and (d.get("direccion") or "").strip()]


def de_provincia(datos, provincia=PROVINCIA_POR_DEFECTO):
    return [d for d in datos if d.get("provincia") == provincia]


def de_cantones(datos, cantones):
    """Varios cantones a la vez: una ruta cruza mas de uno."""
    elegidos = set(cantones or [])
    if not elegidos:
        return list(datos)
    return [d for d in datos if d.get("canton") in elegidos]


def por_puntaje(datos):
    return sorted(datos, key=lambda d: d.get("puntaje") or 0, reverse=True)


# una_por_marca vive en reglas.py: la usan los dos canales. Se reexporta
# aca para que las pantallas y las pruebas la pidan por zonas.


def cantones_con_conteo(datos):
    """Cantones presentes y cuantos visitables hay en cada uno.

    Ordenado por cantidad: la ruta que mas rinde aparece de primera.
    """
    conteo = {}
    for d in datos:
        c = d.get("canton")
        if c:
            conteo[c] = conteo.get(c, 0) + 1
    return sorted(conteo.items(), key=lambda kv: (-kv[1], kv[0]))


def enlace_maps(negocio):
    """Para abrir la direccion en el telefono, de camino.

    Se usa el place_id cuando esta: lleva al negocio exacto en vez de a
    una busqueda por texto, que con nombres repetidos se equivoca.
    """
    pid = negocio.get("place_id")
    if pid:
        return ("https://www.google.com/maps/search/?api=1"
                f"&query=Google&query_place_id={pid}")

    from urllib.parse import quote_plus
    consulta = ", ".join(x for x in (negocio.get("nombre"),
                                     negocio.get("direccion")) if x)
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(consulta)}"


# Codigo de ubicacion de Google ("XJJC+WCJ"). Aparece en la direccion
# cuando el negocio no tiene una calle registrada, y no le sirve a
# nadie: no se puede leer ni preguntar por el.
PLUS_CODE = re.compile(r"\b[23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,3}\b",
                       re.I)

# "Provincia de Alajuela" sobra: la provincia ya se eligio en pantalla.
RELLENO = re.compile(r"\b(provincia de|province|costa rica)\b[,\s]*", re.I)


def direccion_corta(negocio):
    """La direccion sin lo que no se puede usar para llegar.

    Google devuelve cosas como "XJJC+WCJ, 3, Provincia de Alajuela,
    Atenas". El codigo no sirve, la provincia ya se sabe, y lo que
    queda es lo unico que alguien podria preguntarle a un vecino.
    """
    d = PLUS_CODE.sub("", negocio.get("direccion") or "")
    d = RELLENO.sub("", d)
    partes = [p.strip() for p in d.split(",")]
    partes = [p for p in partes if len(p) > 1]       # fuera los "3" sueltos
    return ", ".join(dict.fromkeys(partes))          # sin repetidos


def avisos(negocio):
    """Lo que conviene pensar ANTES de entrar.

    Solo van aqui las cosas que podrian cambiar la decision. El canal
    de contacto no: eso es un dato y se muestra aparte.
    """
    marcas = []
    if negocio.get("posible_competidor"):
        marcas.append("El nombre sugiere que hacen embutidos propios")
    if negocio.get("es_cadena"):
        marcas.append("Es cadena: la compra suele decidirse en oficinas "
                      "centrales")
    return marcas


def canal(negocio):
    """Como se le puede llegar. Es un dato, no una advertencia."""
    if es_celular(negocio.get("telefono")):
        return "Celular: se le puede escribir por WhatsApp"
    if negocio.get("telefono"):
        return "Solo teléfono fijo: llamar o visitar"
    return "Sin teléfono: visitar"


def ruta(datos, provincia=PROVINCIA_POR_DEFECTO, cantones=None, tope=None,
         por_marca=POR_MARCA):
    """La lista lista para imprimir o mirar en el telefono.

    `por_marca=None` muestra todas las sucursales. El tope se aplica al
    final, sobre la lista ya filtrada: si no, un tope de 20 se gastaria
    en sucursales que despues se esconden y devolveria menos de 20.
    """
    r = por_puntaje(de_cantones(de_provincia(visitables(datos), provincia),
                                cantones))
    r = una_por_marca(r, por_marca)
    return r[:tope] if tope else r


def resumen(datos, provincia=PROVINCIA_POR_DEFECTO):
    """Cifras de la provincia, para saber con que se cuenta."""
    v = de_provincia(visitables(datos), provincia)
    return {
        "total": len(de_provincia(datos, provincia)),
        "visitables": len(v),
        "con_celular": sum(1 for d in v if es_celular(d.get("telefono"))),
        "cadenas": sum(1 for d in v if d.get("es_cadena")),
        "posibles_competidores": sum(1 for d in v
                                     if d.get("posible_competidor")),
        "cantones": len(cantones_con_conteo(v)),
    }