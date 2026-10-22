"""Una corrida interrumpida no se vuelve a pagar.

Punto 10 (22/10/2026). La hoja de ruta pedia un checkpointer
persistente de LangGraph; al ir a hacerlo aparecio que ese no era el
problema. Un checkpointer salva la invocacion en curso -- tres nodos,
unos segundos. Lo caro de perder son los cincuenta negocios que ya se
calificaron y se pagaron.

La verificacion que pedia la propia hoja de ruta era: matar el proceso
a mitad de corrida, volver a arrancarlo y que retome donde iba. Eso es
lo que prueban estas.

Correr con:  python -m pytest tests/test_reanudar.py -v
"""

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import reanudar                                                 # noqa: E402


def negocio(nombre, place_id=None, canton="Grecia"):
    return {"nombre": nombre, "canton": canton, "place_id": place_id}


def resultado(nombre, place_id=None, **kw):
    base = {**negocio(nombre, place_id), "calificacion": "prospecto",
            "mensaje": "Buenas."}
    base.update(kw)
    return base


@pytest.fixture
def destino(tmp_path):
    return str(tmp_path / "prospectos_calificados.json")


# ─────────────────────────────────────────────────────────────────
# Quien es quien
# ─────────────────────────────────────────────────────────────────

def test_la_identidad_es_el_place_id():
    """Lo pone Google y es exacto."""
    assert reanudar.clave(negocio("Super X", "ChIJ123")) == "ChIJ123"


def test_sin_place_id_cae_a_nombre_y_canton():
    """Dos sucursales se llaman igual; el canton las separa."""
    a = reanudar.clave(negocio("Super X", canton="Grecia"))
    b = reanudar.clave(negocio("Super X", canton="Naranjo"))
    assert a != b


def test_el_place_id_gana_sobre_el_nombre():
    """Si Google corrige el nombre, sigue siendo el mismo negocio."""
    viejo = negocio("Super X", "ChIJ123")
    nuevo = negocio("Supermercado X", "ChIJ123")
    assert reanudar.clave(viejo) == reanudar.clave(nuevo)


# ─────────────────────────────────────────────────────────────────
# Retomar
# ─────────────────────────────────────────────────────────────────

def test_sin_parcial_no_hay_nada_hecho(destino):
    assert reanudar.hechos(destino) == []


def test_lo_anotado_se_lee_de_vuelta(destino):
    reanudar.anotar(destino, resultado("Super A", "ChIJ1"))
    reanudar.anotar(destino, resultado("Super B", "ChIJ2"))

    leidos = reanudar.hechos(destino)
    assert [r["nombre"] for r in leidos] == ["Super A", "Super B"]


def test_los_pendientes_son_los_que_faltan(destino):
    tanda = [negocio("A", "ChIJ1"), negocio("B", "ChIJ2"),
             negocio("C", "ChIJ3")]
    reanudar.anotar(destino, resultado("A", "ChIJ1"))

    faltan = reanudar.pendientes(tanda, reanudar.hechos(destino))
    assert [n["nombre"] for n in faltan] == ["B", "C"]


def test_los_pendientes_conservan_el_orden():
    """El orden es por puntaje. Reanudar no puede reordenar la tanda."""
    tanda = [negocio(n, f"ChIJ{n}") for n in "ABCDE"]
    hechos = [resultado("C", "ChIJC")]
    faltan = reanudar.pendientes(tanda, hechos)
    assert [n["nombre"] for n in faltan] == ["A", "B", "D", "E"]


def test_si_ya_estan_todos_no_queda_ninguno(destino):
    tanda = [negocio("A", "ChIJ1")]
    reanudar.anotar(destino, resultado("A", "ChIJ1"))
    assert reanudar.pendientes(tanda, reanudar.hechos(destino)) == []


# ─────────────────────────────────────────────────────────────────
# Morir a mitad de camino
# ─────────────────────────────────────────────────────────────────

def test_una_linea_cortada_no_tapa_las_anteriores(destino):
    """El proceso puede morir escribiendo. Las 50 lineas enteras de
    antes tienen que seguir sirviendo."""
    reanudar.anotar(destino, resultado("A", "ChIJ1"))
    reanudar.anotar(destino, resultado("B", "ChIJ2"))
    with open(reanudar.ruta_parcial(destino), "a", encoding="utf-8") as f:
        f.write('{"nombre": "C", "place_')

    leidos = reanudar.hechos(destino)
    assert [r["nombre"] for r in leidos] == ["A", "B"]


def test_el_negocio_de_la_linea_cortada_se_vuelve_a_hacer(destino):
    """Que es lo correcto: ese no se termino de guardar."""
    reanudar.anotar(destino, resultado("A", "ChIJ1"))
    with open(reanudar.ruta_parcial(destino), "a", encoding="utf-8") as f:
        f.write('{"nombre": "B", "place_')

    tanda = [negocio("A", "ChIJ1"), negocio("B", "ChIJ2")]
    faltan = reanudar.pendientes(tanda, reanudar.hechos(destino))
    assert [n["nombre"] for n in faltan] == ["B"]


def test_es_solo_append_lo_viejo_no_se_reescribe(destino):
    """Un JSON entero hay que reescribirlo cada vez, y morir a mitad de
    esa escritura pierde TODO justo cuando mas importa."""
    reanudar.anotar(destino, resultado("A", "ChIJ1"))
    antes = Path(reanudar.ruta_parcial(destino)).read_text(encoding="utf-8")

    reanudar.anotar(destino, resultado("B", "ChIJ2"))
    despues = Path(reanudar.ruta_parcial(destino)).read_text(
        encoding="utf-8")

    assert despues.startswith(antes)


def test_guardar_el_avance_nunca_rompe_la_corrida(tmp_path):
    imposible = str(tmp_path / "no-existe" / "x.json")
    assert reanudar.anotar(imposible, resultado("A", "ChIJ1")) is False


# ─────────────────────────────────────────────────────────────────
# Terminar
# ─────────────────────────────────────────────────────────────────

def test_al_terminar_el_parcial_se_borra(destino):
    reanudar.anotar(destino, resultado("A", "ChIJ1"))
    assert Path(reanudar.ruta_parcial(destino)).exists()

    reanudar.terminar(destino)
    assert not Path(reanudar.ruta_parcial(destino)).exists()


def test_terminar_sin_parcial_no_revienta(destino):
    reanudar.terminar(destino)


def test_el_parcial_vive_al_lado_del_destino(destino):
    """Para que se vea. Un archivo de avance escondido en temp es un
    archivo que nadie borra nunca."""
    assert reanudar.ruta_parcial(destino).startswith(destino)


# ─────────────────────────────────────────────────────────────────
# Como lo usa el grafo
# ─────────────────────────────────────────────────────────────────

def test_el_grafo_guarda_apenas_sale_no_al_final():
    """Si guardara al final, morir en el negocio 51 perderia los 50
    anteriores: exactamente lo que esto viene a evitar."""
    fuente = (RAIZ / "grafo.py").read_text(encoding="utf-8")
    cuerpo = fuente.split("def correr(")[1].split("\ndef ")[0]
    assert "reanudar.anotar(destino, resultado)" in cuerpo


def test_el_grafo_borra_el_parcial_despues_de_escribir_el_json():
    """Al reves, un fallo al escribir el JSON dejaria la corrida sin
    avance y sin resultado."""
    fuente = (RAIZ / "grafo.py").read_text(encoding="utf-8")
    assert fuente.index("json.dump(resultados") < fuente.index(
        "reanudar.terminar(destino)")


def test_sin_destino_correr_se_comporta_como_antes():
    """El argumento es opcional: las pruebas y cualquier uso como
    biblioteca no tienen por que escribir un parcial."""
    import inspect
    import grafo
    assert inspect.signature(grafo.correr).parameters["destino"].default \
        is None
