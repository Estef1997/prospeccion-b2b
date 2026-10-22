"""Lo que sale hacia Langfuse, sin la identidad del negocio.

Punto 16 (21/10/2026). Se escribio DESPUES de medir, no antes: la
sonda (`sonda_langfuse.py`) corrio un negocio con centinelas y mostro
exactamente por donde viaja la identidad. Lo que encontro:

  - 22 atributos por span, y solo DOS llevan identidad:
    `langfuse.observation.input` y `langfuse.observation.output`
  - los otros 20 son metadata del grafo (nodo, modelo, tokens,
    checkpoint, latencia). Esos son la observabilidad: se conservan.
  - los seis nombres de span son genericos (LangGraph, calificador,
    ruta, RunnableSequence, ChatAnthropic, PydanticToolsParser), asi
    que no hace falta tocar nombres -- y menos mal, porque el hook no
    puede cambiarlos.

**El hallazgo que justifica todo este archivo:** los spans de nodo no
trazan el prompt, trazan el ESTADO que entra y sale de cada nodo. Y el
estado lleva `negocio` entero, con telefono y direccion adentro. O sea
que CAMPOS_PROHIBIDOS protege lo que ve el modelo y no protege lo que
ve el tracing: son dos caminos distintos. Conectar Langfuse siguiendo
cualquier tutorial habria mandado los telefonos de 3.485 negocios a la
nube, sin un solo error en pantalla.

Como funciona: `recordar(negocio)` anota los valores identificadores
antes de invocar el grafo; el hook los reemplaza en los dos atributos.

  Super Dos   ->  neg_a3f2      (seudonimo estable)
  Grecia                ->  zona_7b11
  88887777              ->  [telefono]    (sin seudonimo: no sirve)
  200 m sur del parque  ->  [direccion]

Tres decisiones:

1. **Sustituir, no borrar.** Borrar input/output protegeria igual pero
   dejaria el panel sin el texto del mensaje, que es justo lo que se
   quiere leer cuando el validador rechaza algo. El seudonimo es
   estable (hash del valor) para poder seguir un mismo negocio entre
   spans y buscarlo localmente si hace falta.

2. **La categoria NO se sustituye.** "Supermercado" la comparten
   cientos de negocios: no identifica a ninguno, y dejarla hace la
   traza legible.

3. **Falla cerrada.** Si el registro esta vacio -- porque alguien
   conecto Langfuse sin llamar a `recordar()` -- el hook BORRA los dos
   atributos en vez de dejarlos pasar. Un error de cableado tiene que
   costar trazas, nunca datos.

Lo que esta mascara NO puede: una parafrasis. Si el modelo escribe "la
zona cafetalera" en vez de "Grecia", no hay valor que sustituir. Es
poco probable con un prompt tan acotado -- el modelo solo puede
escribir sobre lo que se le dio -- pero no es imposible, y esta dicho
aca en vez de dejarlo implicito.
"""

import hashlib
import json
import re

# ─────────────────────────────────────────────────────────────────

LLAVES_CON_IDENTIDAD = (
    "langfuse.observation.input",
    "langfuse.observation.output",
)

# Se sustituyen por un seudonimo estable: sirven para agrupar.
CAMPOS_SEUDONIMO = {
    "nombre": "neg",
    "canton": "zona",
    "provincia": "zona",
}

# Se tapan sin seudonimo: saber CUAL telefono no ayuda a depurar nada.
CAMPOS_TAPADOS = {
    "telefono": "[telefono]",
    "direccion": "[direccion]",
    "place_id": "[place_id]",
    "url_maps": "[url_maps]",
}

# Un valor de uno o dos caracteres aparece en cualquier texto por
# casualidad. Sustituirlo destrozaria la traza sin proteger nada.
LARGO_MINIMO = 3

_REGISTRO = {}      # valor crudo -> con que se reemplaza
_EN_MINUSCULA = {}  # el mismo registro en minuscula, para buscar en O(1)
_PATRON = None      # regex compilado, se invalida al registrar

# El registro guarda los negocios de UNA corrida (20, 40), no el corpus
# entero. Importa para la velocidad: el patron es un solo regex con una
# alternativa por valor, y el costo crece con la cantidad. Con los 3.485
# a la vez, limpiar el corpus tarda ~70 s; por tandas de 40, 1 s. En
# produccion nunca se da el primer caso, y la prueba del corpus tampoco
# debe darlo: ver tests/test_mascara.py.


# ─────────────────────────────────────────────────────────────────
# Registrar
# ─────────────────────────────────────────────────────────────────

def _seudonimo(prefijo, valor):
    """Estable entre corridas y entre spans: es hash del valor."""
    h = hashlib.sha256(valor.encode("utf-8")).hexdigest()[:4]
    return f"{prefijo}_{h}"


def _formas(valor):
    """El valor tal cual, y como queda escrito dentro de un JSON.

    Los atributos viajan como JSON. Segun quien los serialice, "Super"
    puede ir como `S\\u00faper`. Si solo se busca la forma con tilde,
    la otra pasa de largo.
    """
    formas = {valor}
    escapado = json.dumps(valor)[1:-1]      # sin las comillas
    formas.add(escapado)
    escapado_ascii = json.dumps(valor, ensure_ascii=True)[1:-1]
    formas.add(escapado_ascii)
    return {f for f in formas if len(f) >= LARGO_MINIMO}


def _anotar(valor, reemplazo):
    global _PATRON
    for forma in _formas(valor):
        if forma not in _REGISTRO:
            _REGISTRO[forma] = reemplazo
            _EN_MINUSCULA.setdefault(forma.lower(), reemplazo)
            _PATRON = None


def recordar(negocio):
    """Anota los valores de UN negocio. Se llama antes de invocar."""
    for campo, prefijo in CAMPOS_SEUDONIMO.items():
        valor = str(negocio.get(campo) or "").strip()
        if len(valor) >= LARGO_MINIMO:
            _anotar(valor, _seudonimo(prefijo, valor))

    for campo, marcador in CAMPOS_TAPADOS.items():
        valor = str(negocio.get(campo) or "").strip()
        if len(valor) >= LARGO_MINIMO:
            _anotar(valor, marcador)


def olvidar():
    """Vacia el registro. Para las pruebas y para empezar limpio."""
    global _PATRON
    _REGISTRO.clear()
    _EN_MINUSCULA.clear()
    _PATRON = None


def registrados():
    return dict(_REGISTRO)


# ─────────────────────────────────────────────────────────────────
# Limpiar
# ─────────────────────────────────────────────────────────────────

def _patron():
    """Un solo regex con todo, de mas largo a mas corto.

    El orden importa y no es cosmetico: si "Grecia" se sustituyera
    antes que "Super Dos", el nombre quedaria partido en
    "Super Dos zona_7b11" y el nombre del negocio seguiria ahi.
    """
    global _PATRON
    if _PATRON is None and _REGISTRO:
        piezas = sorted(_REGISTRO, key=len, reverse=True)
        _PATRON = re.compile("|".join(re.escape(p) for p in piezas),
                             re.IGNORECASE)
    return _PATRON


def limpiar(texto):
    """Reemplaza todo lo registrado. Insensible a mayusculas."""
    patron = _patron()
    if patron is None:
        return texto

    def cambiar(m):
        hallado = m.group(0)
        # El segundo diccionario no es optimizacion prematura: sin el,
        # un valor que viene con otra caja ("GRECIA") obliga a recorrer
        # el registro entero en cada coincidencia.
        return (_REGISTRO.get(hallado)
                or _EN_MINUSCULA.get(hallado.lower())
                or hallado)

    return patron.sub(cambiar, texto)


# ─────────────────────────────────────────────────────────────────
# El hook
# ─────────────────────────────────────────────────────────────────

def enmascarar(*, params):
    """Lo que Langfuse llama justo antes de exportar el lote."""
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

    hay_registro = bool(_REGISTRO)
    parches = {}

    for id_span, span in params.spans.items():
        atributos = dict(span.attributes or {})
        poner, borrar = {}, []

        for llave in LLAVES_CON_IDENTIDAD:
            if llave not in atributos:
                continue
            if not hay_registro:
                # Falla cerrada: nadie llamo a recordar().
                borrar.append(llave)
                continue
            valor = atributos[llave]
            if not isinstance(valor, str):
                valor = json.dumps(valor, ensure_ascii=False, default=str)
            limpio = limpiar(valor)
            if limpio != atributos[llave]:
                poner[llave] = limpio

        if poner or borrar:
            parches[id_span] = OtelSpanPatch(
                delete_attributes=tuple(borrar), set_attributes=poner)

    return MaskOtelSpansResult(span_patches=parches) if parches else None