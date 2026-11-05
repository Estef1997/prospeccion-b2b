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

# --- la lista no es un censo -------------------------------------------
# Origen (03/11/2026), de una revision externa del repo publico: el
# README presentaba "3.349 candidatos" como una medicion del mercado.
# No lo es. Cada consulta pide TOPE_POR_CONSULTA y Places no pagina,
# asi que una consulta que devuelve justo el tope esta recortada; y las
# consultas fallidas se saltaban con un print, sin dejar rastro.
#
# Nada de esto llama a la API: resumen_consultas() recibe la lista.

def consulta(zona="Palmares, Alajuela, Costa Rica", tipo="supermercado",
             devueltos=5, tope=False, error=None):
    return {"zona": zona, "tipo": tipo, "devueltos": devueltos,
            "tope": tope, "error": error}


def test_sin_fallos_ni_topes_la_lista_si_es_completa():
    """El caso que DEBE pasar: no se avisa de lo que no pasa."""
    r = prospecto.resumen_consultas([consulta(), consulta(devueltos=12)])

    assert r["es_censo"]
    assert r["fallidas"] == 0
    assert r["al_tope"] == 0
    assert r["devueltos"] == 17


def test_una_consulta_al_tope_hace_que_no_sea_censo():
    """Devolver justo el tope quiere decir recortada, no completa."""
    r = prospecto.resumen_consultas([
        consulta(devueltos=prospecto.TOPE_POR_CONSULTA, tope=True)])

    assert not r["es_censo"]
    assert r["al_tope"] == 1


def test_una_consulta_fallida_queda_registrada_con_su_zona():
    """Antes esto era un print y nada mas.

    Sin el registro, un canton entero podia faltar y el total se veia
    igual de redondo.
    """
    r = prospecto.resumen_consultas([
        consulta(zona="Upala, Alajuela, Costa Rica", tipo="minisuper",
                 devueltos=None, error="timeout")])

    assert r["fallidas"] == 1
    assert not r["es_censo"]
    assert "Upala" in r["detalle_fallidas"][0]
    assert "minisuper" in r["detalle_fallidas"][0]
    assert "timeout" in r["detalle_fallidas"][0]


def test_una_consulta_fallida_no_suma_al_conteo():
    """None no puede contar como cero encontrados de verdad."""
    r = prospecto.resumen_consultas([
        consulta(devueltos=3), consulta(devueltos=None, error="503")])

    assert r["devueltos"] == 3
    assert r["consultas"] == 2


def test_sin_consultas_no_se_inventa_un_censo():
    r = prospecto.resumen_consultas([])

    assert r["consultas"] == 0
    assert r["devueltos"] == 0


def test_el_tope_sale_de_buscar_negocios_y_no_de_una_copia():
    """Una constante copiada se desincroniza. Van cuatro veces aca."""
    import buscar_negocios

    assert prospecto.TOPE_POR_CONSULTA is buscar_negocios.TOPE_POR_CONSULTA


def test_a_la_bitacora_no_va_el_mensaje_crudo_de_google(monkeypatch,
                                                        tmp_path):
    """bitacora.jsonl SI se commitea, y el error de Google trae su body.

    buscar_negocios() levanta RuntimeError con respuesta.text adentro.
    Si eso entrara al resumen, el cuerpo de una respuesta de Google
    quedaria en un archivo del repo -- y nadie lo revisa porque el
    archivo se ve lleno de conteos.

    Esta prueba no llama a la API: reemplaza buscar_negocios y recorta
    CANTONES a un solo canton.
    """
    import bitacora

    FUGA = "Carniceria un proveedor regional 24501234"

    def siempre_falla(zona, tipo, **kw):
        raise RuntimeError(f"Places API devolvio 400: {FUGA}")

    monkeypatch.setattr(prospecto, "buscar_negocios", siempre_falla)
    monkeypatch.setattr(prospecto, "CANTONES", {"Alajuela": ["Palmares"]})
    monkeypatch.setattr(prospecto, "TIPOS", ["supermercado"])
    monkeypatch.setattr(bitacora, "ARCHIVO", str(tmp_path / "bit.jsonl"))
    monkeypatch.setattr(prospecto, "anotar", bitacora.anotar)

    prospecto.prospectar(provincias=["Alajuela"])

    escrito = (tmp_path / "bit.jsonl").read_text(encoding="utf-8")
    assert FUGA not in escrito, "el cuerpo de Google quedo en la bitacora"
    assert "24501234" not in escrito
    # Lo que SI tiene que quedar: que fallo, donde, y de que clase.
    assert "RuntimeError" in escrito
    assert "Palmares" in escrito
