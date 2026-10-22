"""La busqueda no puede borrar lo que ya se pago.

Origen (05/10/2026): para rankear zonas hace falta buscar en todas las
provincias, no solo Alajuela. Pero prospecto.py escribia el JSON con
"w" y los resultados de la corrida: buscar en Puntarenas habria borrado
los 629 de Alajuela, que ya costaron 48 llamadas a Places.

Esto no llama a la API. Prueba la fusion, el conteo de costo y el
guardado, que es donde esta el riesgo.

Correr con:  python -m pytest tests/test_busqueda.py -v
"""

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import prospecto                                                # noqa: E402


def n(pid, nombre="Super", puntaje=50, **kw):
    d = {"place_id": pid, "nombre": nombre, "puntaje": puntaje}
    d.update(kw)
    return d


# --- no perder lo ya pagado --------------------------------------------

def test_lo_viejo_sobrevive_a_una_busqueda_nueva():
    """El caso que motivo todo esto."""
    alajuela = [n("a1", "Palmares 1"), n("a2", "Grecia 1")]
    puntarenas = [n("p1", "Esparza 1")]

    salida, agregados = prospecto.fusionar(alajuela, puntarenas)

    assert len(salida) == 3
    assert agregados == 1
    assert {d["place_id"] for d in salida} == {"a1", "a2", "p1"}


def test_un_negocio_repetido_no_se_duplica():
    salida, agregados = prospecto.fusionar([n("a1")], [n("a1")])
    assert len(salida) == 1
    assert agregados == 0


def test_el_dato_nuevo_le_gana_al_viejo():
    """Trae rating y telefono mas frescos."""
    viejo = [n("a1", "Super X", telefono=None, rating=3.0)]
    nuevo = [n("a1", "Super X", telefono="8888 7777", rating=4.5)]

    salida, _ = prospecto.fusionar(viejo, nuevo)
    assert salida[0]["telefono"] == "8888 7777"
    assert salida[0]["rating"] == 4.5


def test_la_salida_queda_ordenada_por_puntaje():
    salida, _ = prospecto.fusionar([n("a", puntaje=10)],
                                   [n("b", puntaje=90),
                                    n("c", puntaje=50)])
    assert [d["puntaje"] for d in salida] == [90, 50, 10]


def test_fusionar_con_un_archivo_vacio_funciona():
    salida, agregados = prospecto.fusionar([], [n("a1")])
    assert len(salida) == 1 and agregados == 1


# --- el guardado no deja el archivo a medias ---------------------------

def test_guardar_y_cargar_da_lo_mismo(tmp_path):
    ruta = tmp_path / "crudo.json"
    datos = [n("a1"), n("a2")]
    prospecto.guardar(datos, ruta)
    assert prospecto.cargar_existente(ruta) == datos


def test_un_fallo_al_guardar_deja_intacto_lo_anterior(tmp_path,
                                                      monkeypatch):
    ruta = tmp_path / "crudo.json"
    bueno = [n("a1")]
    prospecto.guardar(bueno, ruta)

    def explotar(*a, **k):
        raise OSError("disco lleno")

    monkeypatch.setattr(prospecto.os, "replace", explotar)
    with pytest.raises(OSError):
        prospecto.guardar(bueno + [n("a2")], ruta)

    assert prospecto.cargar_existente(ruta) == bueno


def test_cargar_sin_archivo_no_rompe(tmp_path):
    assert prospecto.cargar_existente(tmp_path / "no_existe.json") == []


# --- saber el costo antes de gastarlo ----------------------------------

def test_el_costo_es_cantones_por_tipos():
    cantones = len(prospecto.CANTONES["Puntarenas"])
    assert prospecto.costo_estimado(["Puntarenas"]) == (
        cantones * len(prospecto.TIPOS))


def test_el_costo_de_varias_provincias_se_suma():
    a = prospecto.costo_estimado(["Alajuela"])
    b = prospecto.costo_estimado(["Limón"])
    assert prospecto.costo_estimado(["Alajuela", "Limón"]) == a + b


def test_estan_las_siete_provincias():
    """Si falta una, el ranking por zona queda cojo."""
    assert len(prospecto.CANTONES) == 7
    for p in ("San José", "Alajuela", "Cartago", "Heredia",
              "Guanacaste", "Puntarenas", "Limón"):
        assert prospecto.CANTONES[p], f"{p} sin cantones"


def test_el_total_son_84_cantones():
    """El numero que aparece en la documentacion."""
    assert sum(len(c) for c in prospecto.CANTONES.values()) == 84