"""
Registro de lo que paso con cada mensaje enviado.

Esta es la logica; la pantalla esta en app.py. Separado a proposito:
asi se puede probar sin levantar Streamlit.

QUIEN ES EL DUENO DE QUE

    las respuestas    <- las escribe el app, y NADIE mas
    la hoja           <- es una vista; a_sheets.py la llena desde aca

Antes las columnas Estado y Notas se escribian a mano en la hoja. Con
el app habria dos lugares donde anotar lo mismo, y se desincronizarian
al primer cambio -- es el mismo bug de CONTEXTO_FABRICA, que vivia en
grafo.py y en validar_claude.py a la vez.

Una regla, un lugar. Tambien vale para los datos.

DONDE SE GUARDAN (cambio del 08/10/2026)

En la maquina de desarrollo: `respuestas.json`, al lado del codigo.

Hospedado: en la hoja de Google. **En Streamlit Cloud el disco es
efimero** -- lo que el app escribe se borra cuando el servidor
reinicia, y solo sobrevive lo que esta en GitHub. respuestas.json es
el UNICO archivo del proyecto que no se puede volver a generar: los
otros tres salen de una corrida, este guarda lo que contestaron los
negocios de verdad.

Guardarlo en disco alla seria perder el ancla sin enterarse.

El cambio es solo por dentro. Las cuatro funciones de abajo
(cargar, guardar, anotar, resumen) se usan igual desde las pantallas;
lo unico que cambia es a donde van los bytes.
"""

import json
import os
from datetime import date

ARCHIVO = "respuestas.json"

# Donde se guarda. None = archivo local.
#
# Un backend es cualquier objeto con leer() y escribir(registros). El
# app hospedado llama a usar(almacen_sheets) al arrancar; las pruebas
# nunca lo tocan, asi que siguen trabajando contra archivos temporales.
BACKEND = None


def usar(backend):
    """Cambia donde se guardan las respuestas. None vuelve al archivo."""
    global BACKEND
    BACKEND = backend


def donde():
    """Para mostrarlo en pantalla. Si el usuario no sabe donde quedo lo
    que anoto, no puede confiar en el app."""
    return getattr(BACKEND, "NOMBRE", ARCHIVO) if BACKEND else ARCHIVO

# Vocabulario cerrado. Vive aca y a_sheets.py lo importa.
ESTADOS = [
    "",               # todavia no se envio
    "enviado",        # se mando, sin respuesta aun
    "interesado",     # contesto y quiere saber mas
    "no",             # contesto que no
    "sin respuesta",  # paso una semana y nada
    "mal numero",     # el numero no existe o no es del negocio
]

# Que se mando en realidad. Esta columna mide al redactor: si todos los
# mensajes salen "editado", el agente no sirve -- y sin este dato nadie
# se entera, porque igual habria respuestas.
MENSAJES = ["", "tal cual", "editado", "propio"]

# QUE PASO con el negocio. Son los que van a las columnas manuales de la
# hoja principal, que ya tiene el nombre en su propia columna.
CAMPOS = ("estado", "enviado", "mensaje", "notas")

# QUIEN ERA. No los usa el sistema -- la llave es el place_id -- pero sin
# ellos la pestaña de Respuestas es una lista de codigos. Ver anotar().
CAMPOS_LECTURA = ("nombre", "canton")


def cargar(ruta=ARCHIVO):
    """Lo anotado hasta ahora, indexado por place_id.

    Si el archivo no existe todavia, devuelve vacio: la primera corrida
    del app no es un error.
    """
    if BACKEND:
        return BACKEND.leer()
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def guardar(registros, ruta=ARCHIVO):
    """Escribe el archivo completo.

    Primero a un temporal y despues renombra: si el proceso muere a
    mitad de la escritura, el archivo viejo queda intacto en vez de
    quedar partido. Es una tarde de trabajo lo que hay adentro.
    """
    if BACKEND:
        return BACKEND.escribir(registros)
    tmp = str(ruta) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)


def anotar(registros, place_id, estado="", enviado="", mensaje="",
           notas="", nombre="", canton=""):
    """Agrega o actualiza un negocio. Valida el vocabulario.

    Devuelve un dict nuevo en vez de mutar el que recibe, para que un
    error a mitad de camino no deje el registro a medias.

    NOMBRE Y CANTON (09/10/2026)

    No los necesita el sistema: la llave es el place_id, que es unico y
    estable. Se guardan para que una PERSONA pueda leer esto.

    Origen: la primera fila que escribio el app en la hoja decia
    `ChIJ_ejemplo_redactado | enviado | 2026-10-09`. Surgio la pregunta:
    que se supone que hace con eso, y tenia razon.

    El argumento para guardar en la hoja y no en una base de datos fue
    "el papa la puede abrir". Una hoja ilegible no cumple eso, y entonces
    la decision de usar la hoja pierde su razon de ser.

    Van vacios si no se pasan: el place_id sigue siendo lo que identifica
    al negocio, y el nombre es para leer.
    """
    if estado not in ESTADOS:
        raise ValueError(f"Estado desconocido: {estado!r}. "
                         f"Los validos son {ESTADOS}")
    if mensaje not in MENSAJES:
        raise ValueError(f"Mensaje desconocido: {mensaje!r}. "
                         f"Los validos son {MENSAJES}")

    # Lo que ya estaba, si lo habia: asi anotar() dos veces sobre el
    # mismo negocio no borra el nombre cuando la segunda no lo pasa.
    antes = registros.get(place_id, {})

    nuevo = dict(registros)
    nuevo[place_id] = {"estado": estado, "enviado": enviado,
                       "mensaje": mensaje, "notas": notas,
                       "nombre": nombre or antes.get("nombre", ""),
                       "canton": canton or antes.get("canton", "")}
    return nuevo


def fecha_de_hoy():
    return date.today().isoformat()


def para_la_hoja(registros, place_id):
    """Las cuatro columnas manuales de la hoja, en orden.

    a_sheets.py llama a esto en vez de leer lo que haya escrito en la
    hoja. La hoja dejo de ser una fuente.
    """
    r = registros.get(place_id)
    if not r:
        return ["", "", "", ""]
    return [r.get(c, "") for c in CAMPOS]


# ─────────────────────────────────────────────────────────────────
# Lo que se puede medir con esto
# ─────────────────────────────────────────────────────────────────

def resumen(registros):
    """Conteos por estado, y las dos cifras que importan.

    `tasa_respuesta` es sobre los que de verdad se enviaron: incluir
    los que nunca se mandaron la haria parecer peor de lo que es.

    `tal_cual` mide al REDACTOR, no a los prospectos. Es la cifra que
    dice si el agente produjo algo usable o si una persona tuvo que
    arreglarlo.
    """
    por_estado = {}
    for r in registros.values():
        e = r.get("estado") or "(vacio)"
        por_estado[e] = por_estado.get(e, 0) + 1

    enviados = [r for r in registros.values()
                if r.get("estado") and r["estado"] != "mal numero"]
    contestaron = [r for r in enviados
                   if r.get("estado") in ("interesado", "no")]
    tal_cual = [r for r in enviados if r.get("mensaje") == "tal cual"]

    return {
        "por_estado": por_estado,
        "enviados": len(enviados),
        "contestaron": len(contestaron),
        "tasa_respuesta": (len(contestaron) / len(enviados)
                           if enviados else None),
        "tal_cual": len(tal_cual),
        "tasa_tal_cual": (len(tal_cual) / len(enviados)
                          if enviados else None),
    }