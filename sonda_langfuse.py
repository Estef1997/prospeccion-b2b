"""Que manda de verdad la integracion de LangGraph a Langfuse.

    python sonda_langfuse.py            # inspecciona Y manda, SIN mascara
    python sonda_langfuse.py seco       # inspecciona y NO manda nada
    python sonda_langfuse.py mascara    # con la mascara puesta, y verifica

Paso 1 del punto 16 (21/10/2026). No mide nada y no va en el pipeline:
contesta una sola pregunta, y hay que contestarla antes de escribir una
linea de mascara.

La pregunta: **en que atributos viaja la identidad del negocio.**

No se puede adivinar. La mascara de Langfuse es dispersa -- solo cambia
los atributos que uno nombra, y lo que no nombra sube tal cual. Asi que
escribir la mascara contra una lista imaginada de nombres de atributo es
la misma trampa del punto 25: una lista negra que falla en silencio el
dia que aparece un campo nuevo.

El truco de este archivo: `mask_otel_spans` no se usa para enmascarar,
se usa para MIRAR. El hook recibe exactamente los spans que estaban por
salir, con todos sus atributos.

Lo que encontro la primera corrida (21/10/2026, negocio falso):

    22 atributos por span; DOS llevan identidad:
      langfuse.observation.input    (el estado del nodo, o el prompt)
      langfuse.observation.output   (lo que devolvio)
    Los otros 20 son metadata del grafo: nodo, modelo, tokens,
    checkpoint, latencia. Esos SON la observabilidad.

    Seis spans, todos con nombre generico: LangGraph, calificador,
    ruta, RunnableSequence, ChatAnthropic, PydanticToolsParser.

    Y el hallazgo que justifico `mascara.py`: los spans de nodo no
    trazan el prompt, trazan el ESTADO, y el estado lleva el negocio
    entero -- telefono y direccion incluidos, aunque CAMPOS_PROHIBIDOS
    los mantenga fuera del prompt. Son dos caminos distintos.

Para que el inventario no dependa de leer con lupa, el negocio falso
lleva centinelas: cadenas unicas en lugar de nombre, canton, provincia
y categoria. Despues se busca cada centinela en cada atributo.

El modo `mascara` es la prueba de aceptacion: corre lo mismo con
`mascara.py` puesta y verifica, sobre los atributos ya parcheados, que
ningun centinela sobrevivio. La categoria es la excepcion y debe
sobrevivir: la comparten cientos de negocios, no identifica a ninguno,
y dejarla hace la traza legible.

Lo que esta sonda NO puede contestar (hay que mirarlo en el panel, ya
se hizo el 21/10): el NOMBRE del span, los IDs, los eventos y los
enlaces. El hook solo ve y cambia atributos.

Costo: un negocio, tres nodos. Centavos.
"""

import json
import os
import sys
from collections import OrderedDict

from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────
# El negocio falso, con centinelas
# ─────────────────────────────────────────────────────────────────
#
# Ningun dato real. Los valores son cadenas que no existen en ninguna
# parte, para poder buscarlas despues en los atributos.

CENTINELAS = OrderedDict([
    ("nombre", "SONDANOMBRE01"),
    ("canton", "SONDACANTON02"),
    ("provincia", "SONDAPROV03"),
    ("categoria", "SONDACATEG04"),
    ("direccion", "SONDADIRECCION05"),
    ("telefono", "80000001"),
])

# La categoria NO se enmascara, a proposito. Ver mascara.py.
DEBEN_IRSE = ("nombre", "canton", "provincia", "direccion", "telefono")

NEGOCIO_FALSO = {
    "nombre": CENTINELAS["nombre"],
    "canton": CENTINELAS["canton"],
    "provincia": CENTINELAS["provincia"],
    "categoria": CENTINELAS["categoria"],
    "direccion": CENTINELAS["direccion"],
    "telefono": CENTINELAS["telefono"],
    "distancia_km": 12.5,
    "rating": 4.3,
    "num_resenas": 57,
    "sitio_web": None,
    "es_cadena": False,
    "posible_competidor": False,
}

REPORTE = "sonda_langfuse.txt"


# ─────────────────────────────────────────────────────────────────
# El microscopio
# ─────────────────────────────────────────────────────────────────

_visto = []          # (scope, llave, largo, [campos encontrados])
_veces = {"lotes": 0, "spans": 0}


def _texto(valor):
    """Un atributo puede ser str, numero, lista o JSON. Todo a texto."""
    if isinstance(valor, str):
        return valor
    try:
        return json.dumps(valor, ensure_ascii=False, default=str)
    except Exception:
        return str(valor)


def _mirar(scope, atributos):
    for llave, valor in atributos.items():
        texto = _texto(valor)
        hallados = [campo for campo, centinela in CENTINELAS.items()
                    if centinela in texto]
        _visto.append((scope, llave, len(texto), hallados))


def inspeccionar(*, params):
    """Mira el lote que estaba por salir. No cambia nada."""
    _veces["lotes"] += 1
    for _id, span in params.spans.items():
        _veces["spans"] += 1
        _mirar(getattr(span, "instrumentation_scope_name", "?"),
               dict(span.attributes or {}))
    return None


def inspeccionar_y_borrar(*, params):
    """Modo seco: mira todo y no deja salir ni un atributo."""
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

    inspeccionar(params=params)
    return MaskOtelSpansResult(span_patches={
        id_span: OtelSpanPatch(
            delete_attributes=tuple(dict(span.attributes or {}).keys()))
        for id_span, span in params.spans.items()
    })


def enmascarar_y_verificar(*, params):
    """Modo mascara: aplica mascara.py y mira el resultado parcheado.

    Lo que se inspecciona NO son los atributos originales sino los que
    quedan despues del parche. Es la unica forma de afirmar algo sobre
    lo que de verdad sale.
    """
    import mascara

    _veces["lotes"] += 1
    resultado = mascara.enmascarar(params=params)
    parches = resultado.span_patches if resultado else {}

    for id_span, span in params.spans.items():
        _veces["spans"] += 1
        atributos = dict(span.attributes or {})
        parche = parches.get(id_span)
        if parche is not None:
            for llave in (parche.delete_attributes or ()):
                atributos.pop(llave, None)
            atributos.update(parche.set_attributes or {})
        _mirar(getattr(span, "instrumentation_scope_name", "?"), atributos)

    return resultado


# ─────────────────────────────────────────────────────────────────
# El reporte
# ─────────────────────────────────────────────────────────────────

def escribir_reporte(modo):
    lineas = []

    def p(texto=""):
        print(texto)
        lineas.append(texto)

    rotulo = {"normal": "normal (se mando SIN mascara)",
              "seco": "seco (no salio nada)",
              "mascara": "con mascara.py puesta"}[modo]

    p(f"Sonda de Langfuse  --  modo {rotulo}")
    p(f"Lotes inspeccionados: {_veces['lotes']}   "
      f"spans: {_veces['spans']}   atributos: {len(_visto)}")
    p()

    if not _veces["lotes"]:
        p("EL INSPECTOR NUNCA CORRIO.")
        p()
        p("Eso no significa que no se mando nada: significa que el hook")
        p("no esta conectado al cliente que usa el CallbackHandler. Hasta")
        p("resolverlo, cualquier mascara es decorativa. Revisar que el")
        p("cliente se construya ANTES del handler y que flush() corra.")
        return lineas

    con_identidad = [v for v in _visto if v[3]]
    filtrados = [v for v in _visto
                 if any(c in DEBEN_IRSE for c in v[3])]

    if modo == "mascara":
        p("=" * 64)
        p("VEREDICTO")
        p("=" * 64)
        p()
        if filtrados:
            p(f"FALLO. {len(filtrados)} atributos siguen llevando")
            p("identidad DESPUES de la mascara:")
            p()
            for scope, llave, largo, campos in filtrados:
                p(f"    {llave}")
                p(f"      sobrevivio: "
                  f"{', '.join(sorted(set(campos) & set(DEBEN_IRSE)))}")
            p()
            p("No conectar Langfuse al pipeline hasta entender por que.")
        else:
            p("PASA. Ningun centinela de nombre, canton, provincia,")
            p("telefono ni direccion sobrevivio a la mascara.")
            p()
            categoria = [v for v in _visto if "categoria" in v[3]]
            p(f"La categoria sigue visible en {len(categoria)} atributos,")
            p("como debe ser: la comparten cientos de negocios y hace la")
            p("traza legible.")
        p()

    p("=" * 64)
    p("ATRIBUTOS QUE LLEVAN IDENTIDAD")
    p("=" * 64)
    p()
    if not con_identidad:
        p("Ninguno.")
    else:
        for scope, llave, largo, campos in con_identidad:
            p(f"  [{scope}]")
            p(f"    {llave}")
            p(f"      lleva: {', '.join(sorted(set(campos)))}  "
              f"({largo} caracteres)")
    p()

    p("=" * 64)
    p("TODOS LOS ATRIBUTOS, POR SCOPE")
    p("=" * 64)
    p()
    por_scope = {}
    for scope, llave, largo, campos in _visto:
        por_scope.setdefault(scope, {})
        previo = por_scope[scope].get(llave, (0, set()))
        por_scope[scope][llave] = (max(previo[0], largo),
                                   previo[1] | set(campos))

    for scope in sorted(por_scope):
        p(f"  [{scope}]")
        for llave in sorted(por_scope[scope]):
            largo, campos = por_scope[scope][llave]
            graves = campos & set(DEBEN_IRSE)
            marca = ("  <-- IDENTIDAD" if graves
                     else "  (categoria)" if campos else "")
            p(f"    {llave:52} {largo:7}{marca}")
        p()

    return lineas


# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "normal"
    if modo not in ("normal", "seco", "mascara"):
        sys.exit(f"Modo desconocido: {modo}.\n"
                 f"  normal     manda SIN mascara, para inventariar\n"
                 f"  seco       no deja salir ningun atributo\n"
                 f"  mascara    con mascara.py, y verifica el resultado")

    faltan = [k for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY",
                          "LANGFUSE_BASE_URL", "ANTHROPIC_API_KEY")
              if not os.getenv(k)]
    if faltan:
        sys.exit("Falta en el .env: " + ", ".join(faltan) + "\n"
                 "Las tres de Langfuse salen del panel; la region va en\n"
                 "LANGFUSE_BASE_URL y despues no se puede cambiar.")

    # El cliente se construye con el hook ANTES del handler, para que
    # get_client() devuelva este y no uno sin inspector.
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    hook = {"normal": inspeccionar,
            "seco": inspeccionar_y_borrar,
            "mascara": enmascarar_y_verificar}[modo]

    cliente = Langfuse(mask_otel_spans=hook)
    handler = CallbackHandler()

    if modo == "mascara":
        import mascara
        mascara.recordar(NEGOCIO_FALSO)

    import grafo

    print(f"Un negocio falso, modo {modo}. Centinelas:")
    for campo, centinela in CENTINELAS.items():
        marca = "" if campo in DEBEN_IRSE else "   (debe sobrevivir)"
        print(f"  {campo:12} {centinela}{marca}")
    print()

    compilado = grafo.construir()
    final = compilado.invoke({"negocio": dict(NEGOCIO_FALSO)},
                             config={"callbacks": [handler]})

    print(f"\nCalificacion: {final.get('calificacion')}")
    if final.get("mensaje"):
        print(f"Mensaje ({final.get('intentos', 1)} intento):"
              f"\n{final['mensaje']}\n")
    for problema in final.get("problemas") or []:
        print(f"  problema: {problema}")

    # Sin esto el lote puede no salir nunca y el hook no corre.
    cliente.flush()
    print()

    lineas = escribir_reporte(modo)
    with open(REPORTE, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    print(f"Reporte en {REPORTE}")