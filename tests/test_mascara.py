"""La mascara: que no salga la identidad, y que falle cerrada.

Punto 16 (21/10/2026). Estas pruebas existen porque "creo que esta
enmascarado" no es una afirmacion verificable y "el test se pone rojo
si deja de estarlo" si lo es.

La que mas importa es la ultima: abre prospectos_crudo.json, saca los
nombres REALES, y afirma que ninguno sobrevive a la mascara. Esa es la
unica que prueba lo que de verdad nos preocupa; las demas prueban el
mecanismo.

Correr con:  python -m pytest tests/test_mascara.py -v
"""

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import mascara                                                  # noqa: E402

NEGOCIO = {
    "nombre": "Super Dos",
    "canton": "Grecia",
    "provincia": "Alajuela",
    "categoria": "Supermercado",
    "telefono": "88887777",
    "direccion": "200 m sur del parque",
}


@pytest.fixture(autouse=True)
def registro_limpio():
    """Cada prueba arranca sin registro y no ensucia a la siguiente."""
    mascara.olvidar()
    yield
    mascara.olvidar()


class Span:
    """Lo minimo que el hook le pide a un span de OpenTelemetry."""

    def __init__(self, atributos):
        self.attributes = atributos
        self.resource_attributes = {}
        self.instrumentation_scope_name = "langfuse-sdk"


class Lote:
    def __init__(self, spans):
        self.spans = spans


def patch_de(resultado, id_span):
    return resultado.span_patches[id_span]


# ─────────────────────────────────────────────────────────────────
# Sustituir
# ─────────────────────────────────────────────────────────────────

def test_el_nombre_se_va():
    mascara.recordar(NEGOCIO)
    salida = mascara.limpiar("Mensaje para Super Dos, gracias.")
    assert "Dos" not in salida
    assert "neg_" in salida


def test_el_seudonimo_es_estable():
    """Dos corridas distintas tienen que dar el mismo seudonimo, o no
    se puede seguir a un negocio en el tiempo."""
    mascara.recordar(NEGOCIO)
    primero = mascara.limpiar("Super Dos")
    mascara.olvidar()
    mascara.recordar(NEGOCIO)
    assert mascara.limpiar("Super Dos") == primero


def test_dos_negocios_no_comparten_seudonimo():
    mascara.recordar(NEGOCIO)
    mascara.recordar({**NEGOCIO, "nombre": "Supermercado Tres"})
    a = mascara.limpiar("Super Dos")
    b = mascara.limpiar("Supermercado Tres")
    assert a != b


def test_telefono_y_direccion_se_tapan_sin_seudonimo():
    """Saber CUAL telefono no ayuda a depurar: no lleva seudonimo."""
    mascara.recordar(NEGOCIO)
    salida = mascara.limpiar("tel 88887777, en 200 m sur del parque")
    assert "88887777" not in salida and "parque" not in salida
    assert "[telefono]" in salida and "[direccion]" in salida


def test_la_categoria_se_queda():
    """La comparten cientos de negocios: no identifica a ninguno, y
    dejarla hace la traza legible."""
    mascara.recordar(NEGOCIO)
    assert "Supermercado" in mascara.limpiar("Categoria: Supermercado")


def test_el_nombre_largo_gana_sobre_el_canton_que_contiene():
    """Si 'Grecia' se sustituyera primero, quedaria 'Super Dos
    zona_7b11' y el nombre del negocio seguiria ahi."""
    mascara.recordar(NEGOCIO)
    salida = mascara.limpiar("Super Dos")
    assert "Super Dos" not in salida
    assert salida.startswith("neg_")


def test_no_importa_la_caja():
    mascara.recordar(NEGOCIO)
    assert "DOS" not in mascara.limpiar("SUPER DOS GRECIA")


def test_atrapa_la_forma_escapada_de_un_json():
    """Segun quien serialice, 'Alajuela' puede ir con el acento
    escapado. Si solo se busca una forma, la otra pasa de largo."""
    mascara.recordar({**NEGOCIO, "nombre": "Carniceria Guadalupe"})
    crudo = json.dumps({"nombre": "Carniceria Guadalupe"},
                       ensure_ascii=True)
    assert "Guadalupe" not in mascara.limpiar(crudo)


def test_un_valor_de_dos_letras_no_se_registra():
    """Sustituir 'La' destrozaria la traza sin proteger nada."""
    mascara.recordar({"nombre": "La", "canton": "Grecia"})
    assert "La" in mascara.limpiar("La lista de precios")


def test_sin_registro_el_texto_no_cambia():
    assert mascara.limpiar("cualquier cosa") == "cualquier cosa"


# ─────────────────────────────────────────────────────────────────
# El hook
# ─────────────────────────────────────────────────────────────────

def test_el_hook_limpia_input_y_output():
    mascara.recordar(NEGOCIO)
    span = Span({
        "langfuse.observation.input":
            '{"negocio": {"nombre": "Super Dos"}}',
        "langfuse.observation.output":
            '{"mensaje": "Buenas, Super Dos"}',
    })
    r = mascara.enmascarar(params=Lote({"s1": span}))

    puesto = patch_de(r, "s1").set_attributes
    assert "Dos" not in puesto["langfuse.observation.input"]
    assert "Dos" not in puesto["langfuse.observation.output"]


def test_el_hook_no_toca_la_metadata():
    """Los otros 20 atributos SON la observabilidad: nodo, modelo,
    tokens, latencia. Taparlos seria perder lo que se vino a medir."""
    mascara.recordar(NEGOCIO)
    span = Span({
        "langfuse.observation.input": '{"nombre": "Super Dos"}',
        "langfuse.observation.metadata.langgraph_node": "calificador",
        "langfuse.observation.model.name": "claude-sonnet-4-5",
        "langfuse.observation.usage_details": '{"input": 900}',
    })
    r = mascara.enmascarar(params=Lote({"s1": span}))

    patch = patch_de(r, "s1")
    assert set(patch.set_attributes) == {"langfuse.observation.input"}
    assert not patch.delete_attributes


def test_el_telefono_del_estado_no_sale():
    """El hallazgo de la sonda: los spans de nodo trazan el ESTADO, y
    el estado lleva el negocio entero -- telefono y direccion incluidos,
    aunque el prompt no los vea."""
    mascara.recordar(NEGOCIO)
    estado = json.dumps({"negocio": NEGOCIO}, ensure_ascii=False)
    span = Span({"langfuse.observation.input": estado})

    salida = patch_de(mascara.enmascarar(params=Lote({"s1": span})),
                      "s1").set_attributes["langfuse.observation.input"]
    assert "88887777" not in salida
    assert "200 m sur del parque" not in salida
    assert "Dos" not in salida


def test_sin_registro_el_hook_borra_en_vez_de_dejar_pasar():
    """Falla cerrada. Si alguien conecta Langfuse sin llamar a
    recordar(), un error de cableado cuesta trazas, nunca datos."""
    span = Span({
        "langfuse.observation.input": '{"nombre": "Super Dos"}',
        "langfuse.observation.metadata.langgraph_node": "calificador",
    })
    patch = patch_de(mascara.enmascarar(params=Lote({"s1": span})), "s1")

    assert "langfuse.observation.input" in patch.delete_attributes
    assert not patch.set_attributes


def test_un_span_sin_identidad_no_genera_parche():
    mascara.recordar(NEGOCIO)
    span = Span({"langfuse.observation.metadata.langgraph_step": 1})
    assert mascara.enmascarar(params=Lote({"s1": span})) is None


# ─────────────────────────────────────────────────────────────────
# Contra los datos de verdad
# ─────────────────────────────────────────────────────────────────

CRUDO = RAIZ / "prospectos_crudo.json"

# Por tandas, del tamano de una corrida real, y no el corpus entero de
# una sentada. No es para que la prueba corra rapido: es que asi es
# como vive la mascara. El registro tiene los negocios de la tanda que
# se esta procesando, nunca los 3.485 juntos.
#
# La diferencia no es chica. El costo esta casi todo en el regex, que
# crece con la cantidad de valores registrados, asi que la tanda manda:
#
#     3.485 de una vez   70 s
#     tandas de 500      24 s
#     tandas de 100       6 s
#     tandas de 40        3 s
#     tandas de 20      1,7 s
#
# Veinte es el numero de `grafo.py whatsapp 20`. Que ademas sea el mas
# rapido es suerte, pero el motivo para elegirlo es el primero.
#
# Importa mas de lo que parece: una prueba que tarda un minuto es una
# prueba que alguien va a saltarse "porque es lenta", y eso ya costo
# seis dias en este proyecto.
TANDA = 20


def _por_tandas(datos):
    for i in range(0, len(datos), TANDA):
        tanda = datos[i:i + TANDA]
        mascara.olvidar()
        for negocio in tanda:
            mascara.recordar(negocio)
        yield tanda


@pytest.mark.skipif(not CRUDO.exists(),
                    reason="prospectos_crudo.json no esta en esta copia")
def test_ningun_nombre_real_sobrevive():
    """La prueba que importa. Si manana aparece un campo nuevo o
    alguien cambia la mascara, esto se pone rojo antes de que un solo
    nombre salga de la maquina."""
    with open(CRUDO, encoding="utf-8") as f:
        datos = json.load(f)

    sobrevivientes = []
    for tanda in _por_tandas(datos):
        for negocio in tanda:
            nombre = str(negocio.get("nombre") or "").strip()
            if len(nombre) < mascara.LARGO_MINIMO:
                continue
            estado = json.dumps({"negocio": negocio}, ensure_ascii=False)
            if nombre.lower() in mascara.limpiar(estado).lower():
                sobrevivientes.append(nombre)

    assert not sobrevivientes, (
        f"{len(sobrevivientes)} nombres sobrevivieron, "
        f"por ejemplo: {sobrevivientes[:5]}")


@pytest.mark.skipif(not CRUDO.exists(),
                    reason="prospectos_crudo.json no esta en esta copia")
def test_ningun_telefono_real_sobrevive():
    with open(CRUDO, encoding="utf-8") as f:
        datos = json.load(f)

    sobrevivientes = []
    for tanda in _por_tandas(datos):
        for negocio in tanda:
            tel = str(negocio.get("telefono") or "").strip()
            if len(tel) < mascara.LARGO_MINIMO:
                continue
            estado = json.dumps({"negocio": negocio}, ensure_ascii=False)
            if tel in mascara.limpiar(estado):
                sobrevivientes.append(tel)

    assert not sobrevivientes, f"{len(sobrevivientes)} telefonos salieron"