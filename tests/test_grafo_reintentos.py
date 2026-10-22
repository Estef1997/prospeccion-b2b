"""Punto 9: el validador dentro del grafo, con tope de intentos.

Lo que se verifica aqui es la CONDICION DE PARADA. Un bucle sin una no
es un agente, es una fuga de saldo: un mensaje que nunca pasa dejaria
al redactor reescribiendo para siempre.

No llama a ningun modelo. Reemplaza el redactor y el validador por
funciones falsas y cuenta cuantas veces corrio cada uno. La estructura
del grafo es lo que se esta probando, no lo que escribe Claude.

Correr con:  python -m pytest tests/test_grafo_reintentos.py -v
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import grafo                                                    # noqa: E402

NEGOCIO = {"nombre": "Super El Ejemplo", "canton": "Grecia",
           "provincia": "Alajuela", "categoria": "grocery_store"}


@pytest.fixture
def espia(monkeypatch):
    """Cuenta las corridas de cada nodo y deja fijar el veredicto.

    Devuelve un dict con las llamadas; el test decide que contesta el
    validador en cada vuelta.
    """
    reg = {"redactor": 0, "validador": 0, "entradas": [], "veredictos": []}

    def falso_calificador(estado):
        return {"calificacion": "prospecto", "razon": "de prueba",
                "confianza": "alta"}

    def falso_redactor(estado):
        reg["redactor"] += 1
        reg["entradas"].append(estado.get("problemas") or [])
        return {"mensaje": f"borrador {reg['redactor']}",
                "intentos": estado.get("intentos", 0) + 1}

    def falso_validador(estado):
        reg["validador"] += 1
        return reg["veredictos"].pop(0)

    monkeypatch.setattr(grafo, "calificador", falso_calificador)
    monkeypatch.setattr(grafo, "redactor", falso_redactor)
    monkeypatch.setattr(grafo, "validador", falso_validador)
    return reg


RECHAZO = {"valido": False, "problemas": ["menciona clientes actuales"],
           "citas": [("menciona clientes actuales", "ya le vendemos a X")],
           "reintentar": True}
APROBADO = {"valido": True, "problemas": [], "citas": [],
            "reintentar": True}
FALLO_TECNICO = {"valido": False,
                 "problemas": ["fallo tecnico del validador: TimeoutError"],
                 "citas": [], "reintentar": False}


# --- el camino feliz ---------------------------------------------------

def test_si_pasa_a_la_primera_no_reescribe(espia):
    espia["veredictos"] = [APROBADO]
    final = grafo.construir().invoke({"negocio": NEGOCIO})

    assert espia["redactor"] == 1
    assert espia["validador"] == 1
    assert final["valido"] is True


# --- el tope, que es el punto ------------------------------------------

def test_se_detiene_a_los_tres_intentos(espia):
    """Aunque el validador rechace siempre."""
    espia["veredictos"] = [RECHAZO] * 10        # de sobra a proposito

    final = grafo.construir().invoke({"negocio": NEGOCIO})

    assert espia["redactor"] == grafo.MAX_INTENTOS
    assert final["intentos"] == grafo.MAX_INTENTOS
    assert final["valido"] is False


def test_el_mensaje_que_no_paso_igual_sale(espia):
    """Con sus problemas, para que una persona lo revise.

    Descartarlo seria peor: el negocio quedaria sin mensaje y sin
    explicacion de por que.
    """
    espia["veredictos"] = [RECHAZO] * 10
    final = grafo.construir().invoke({"negocio": NEGOCIO})

    assert final["mensaje"]
    assert final["problemas"]


def test_un_fallo_tecnico_no_gasta_reintentos(espia):
    """Reescribir el mensaje no arregla que Jev este caido."""
    espia["veredictos"] = [FALLO_TECNICO]
    final = grafo.construir().invoke({"negocio": NEGOCIO})

    assert espia["redactor"] == 1
    assert final["valido"] is False             # nunca aprobar por defecto


# --- que el reintento sirva de algo ------------------------------------

def test_el_redactor_recibe_los_problemas(espia):
    espia["veredictos"] = [RECHAZO, APROBADO]
    grafo.construir().invoke({"negocio": NEGOCIO})

    assert espia["entradas"][0] == []           # primera vez, sin feedback
    assert "menciona clientes actuales" in espia["entradas"][1]


def test_la_correccion_lleva_la_frase_exacta():
    """_con_citas pega cada problema con su cita."""
    texto = grafo._con_citas({
        "problemas": ["menciona clientes actuales", "sin cita"],
        "citas": [("menciona clientes actuales", "ya le vendemos a X")],
    })
    assert texto[0] == 'menciona clientes actuales: "ya le vendemos a X"'
    assert texto[1] == "sin cita"


# --- los que no son prospecto no entran al bucle -----------------------

def test_un_competidor_no_pasa_por_el_validador(espia, monkeypatch):
    monkeypatch.setattr(grafo, "calificador", lambda e: {
        "calificacion": "competidor", "razon": "fabrica propia",
        "confianza": "alta"})

    grafo.construir().invoke({"negocio": NEGOCIO})

    assert espia["redactor"] == 0
    assert espia["validador"] == 0


# --- a quien se le escribe ---------------------------------------------
# Origen (05/10/2026): de 629 negocios de Alajuela, solo 194 tienen
# celular. Correr el redactor sobre los otros 435 es pagar por un
# mensaje que nadie va a recibir.

def _negocio(pid, telefono, puntaje=50, **kw):
    d = {"place_id": pid, "nombre": f"Super {pid}", "telefono": telefono,
         "puntaje": puntaje, "fuera_de_rubro": False, "cerrado": False,
         "es_cliente": False, "es_cadena": False,
         "posible_competidor": False, "categoria": "grocery_store"}
    d.update(kw)
    return d


def test_solo_entran_los_que_tienen_celular():
    datos = [_negocio("a", "8888 7777"),
             _negocio("b", "2445 1234"),      # fijo
             _negocio("c", None),             # sin telefono
             _negocio("d", "0123 4567")]      # mal formado

    assert [n["place_id"] for n in grafo.con_whatsapp(datos)] == ["a"]


def test_se_respeta_el_filtro_previo_de_prospecto_py():
    """Un cliente actual no recibe mensaje aunque tenga celular."""
    datos = [_negocio("a", "8888 7777", es_cliente=True),
             _negocio("b", "8888 7777", cerrado=True),
             _negocio("c", "8888 7777", fuera_de_rubro=True)]

    assert grafo.con_whatsapp(datos) == []


def test_salen_de_mayor_a_menor_puntaje():
    """El tope corta por abajo: si se procesan 20, son los 20 mejores."""
    datos = [_negocio(str(i), "8888 7777", puntaje=i) for i in range(10)]
    assert [n["puntaje"] for n in grafo.con_whatsapp(datos, tope=3)] == [
        9, 8, 7]


def test_sin_tope_salen_todos():
    datos = [_negocio(str(i), "8888 7777") for i in range(5)]
    assert len(grafo.con_whatsapp(datos)) == 5