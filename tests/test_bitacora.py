"""La bitacora: medir sin romper la corrida, y sin guardar nombres.

Punto 15 (20/10/2026). Tres cosas que estas pruebas cuidan, cada una
porque sin ella la bitacora dejaria de servir para lo que se escribio:

1. Que `medir()` sea la unica cuenta. Si grafo.py volviera a contar
   aparte, el numero de la pantalla y el del archivo podrian discrepar
   y no habria forma de saber cual miente.
2. Que no entre ni un nombre de negocio. Eso es lo que hace que el
   archivo se pueda leer, pegar o subir sin pensarlo.
3. Que un fallo al escribir no mate una corrida que costo dinero.

Correr con:  python -m pytest tests/test_bitacora.py -v
"""

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import bitacora                                                 # noqa: E402

MAX = 3


@pytest.fixture
def archivo(tmp_path, monkeypatch):
    """La bitacora apuntando a un archivo de usar y tirar."""
    destino = tmp_path / "bitacora.jsonl"
    monkeypatch.setattr(bitacora, "ARCHIVO", str(destino))
    return destino


def resultado(**kw):
    base = {"nombre": "Super X", "calificacion": "prospecto",
            "mensaje": "Buenas.", "validacion": "ok", "intentos": 1,
            "problemas": []}
    base.update(kw)
    return base


# ─────────────────────────────────────────────────────────────────
# medir
# ─────────────────────────────────────────────────────────────────

def test_cuenta_por_calificacion():
    m = bitacora.medir([resultado(), resultado(),
                        resultado(calificacion="competidor",
                                  mensaje=None, validacion=None)], MAX)
    assert m["negocios"] == 3
    assert m["calificacion"] == {"prospecto": 2, "competidor": 1}
    assert m["con_mensaje"] == 2


def test_un_mensaje_al_primer_intento_no_es_reescrito():
    m = bitacora.medir([resultado(intentos=1)], MAX)
    assert m["reescritos"] == 0


def test_reescrito_es_mas_de_un_intento():
    m = bitacora.medir([resultado(intentos=2), resultado(intentos=3)], MAX)
    assert m["reescritos"] == 2


def test_agotado_es_llegar_al_tope_sin_validar():
    """Llegar al tope no basta: el que llego y paso no esta agotado."""
    m = bitacora.medir([
        resultado(intentos=MAX, validacion="revisar"),   # agotado
        resultado(intentos=MAX, validacion="ok"),        # no
        resultado(intentos=MAX - 1, validacion="revisar"),  # tampoco
    ], MAX)
    assert m["agotados"] == 1
    assert m["reescritos"] == 3


def test_los_problemas_van_de_mas_a_menos_frecuente():
    m = bitacora.medir([
        resultado(problemas=["reparto fuera de zona"]),
        resultado(problemas=["reparto fuera de zona", "falta el canton"]),
        resultado(problemas=["reparto fuera de zona"]),
    ], MAX)
    assert list(m["problemas"].items())[0] == ("reparto fuera de zona", 3)
    assert m["problemas"]["falta el canton"] == 1


def test_una_corrida_vacia_no_revienta():
    m = bitacora.medir([], MAX)
    assert m["negocios"] == 0 and m["con_mensaje"] == 0
    assert m["problemas"] == {}


def test_un_negocio_que_fallo_no_trae_los_campos_y_se_cuenta_igual():
    """El ramal de error en correr() guarda menos campos a proposito."""
    m = bitacora.medir([{"calificacion": "error", "mensaje": None}], MAX)
    assert m["negocios"] == 1
    assert m["con_mensaje"] == 0 and m["agotados"] == 0


# ─────────────────────────────────────────────────────────────────
# Una sola cuenta en todo el proyecto
# ─────────────────────────────────────────────────────────────────

def test_grafo_no_cuenta_por_su_cuenta():
    """Si resumen() volviera a contar aparte, las dos cuentas podrian
    discrepar. La defensa es que no haya una segunda cuenta."""
    import grafo
    assert grafo.medir is bitacora.medir

    fuente = (RAIZ / "grafo.py").read_text(encoding="utf-8")
    cuerpo = fuente.split("def resumen(")[1].split("\ndef ")[0]
    assert "medir(" in cuerpo
    assert "intentos\") or 1) > 1" not in cuerpo, \
        "resumen() volvio a definir 'reescrito' por su cuenta"


# ─────────────────────────────────────────────────────────────────
# Lo que NO se guarda
# ─────────────────────────────────────────────────────────────────

def test_no_guarda_el_nombre_del_negocio(archivo):
    bitacora.anotar_corrida([resultado(nombre="Carniceria La Esquina")],
                            "whatsapp", MAX)
    assert "Esquina" not in archivo.read_text(encoding="utf-8")


def test_no_guarda_telefono_ni_direccion(archivo):
    bitacora.anotar_corrida(
        [resultado(telefono="88887777", direccion="200 m sur del parque")],
        "whatsapp", MAX)
    texto = archivo.read_text(encoding="utf-8")
    assert "88887777" not in texto and "parque" not in texto


def test_no_guarda_el_mensaje_redactado(archivo):
    bitacora.anotar_corrida(
        [resultado(mensaje="Buenas, le escribo de Embutidos Artesanales")],
        "whatsapp", MAX)
    assert "Artesanales" not in archivo.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────
# Escribir y leer
# ─────────────────────────────────────────────────────────────────

def test_una_corrida_es_una_linea(archivo):
    bitacora.anotar_corrida([resultado()], "whatsapp", MAX, tope=20)
    bitacora.anotar_corrida([resultado()], "muestra", MAX)

    lineas = archivo.read_text(encoding="utf-8").strip().split("\n")
    assert len(lineas) == 2
    primera = json.loads(lineas[0])
    assert primera["evento"] == "corrida"
    assert primera["modo"] == "whatsapp" and primera["tope"] == 20
    assert primera["cuando"].startswith("20")


def test_no_sobrescribe_lo_anterior(archivo):
    for _ in range(3):
        bitacora.anotar_corrida([resultado()], "muestra", MAX)
    assert len(bitacora.historial()) == 3


def test_la_calibracion_guarda_cual_caso_fallo(archivo):
    bitacora.anotar_calibracion(7, 8, ["DEBE FALLAR - inventa productos"])
    linea = bitacora.historial("calibracion")[0]
    assert linea["aciertos"] == 7 and linea["casos"] == 8
    assert linea["fallados"] == ["DEBE FALLAR - inventa productos"]


def test_historial_filtra_por_evento(archivo):
    bitacora.anotar_corrida([resultado()], "muestra", MAX)
    bitacora.anotar_calibracion(8, 8, [])
    assert len(bitacora.historial()) == 2
    assert len(bitacora.historial("corrida")) == 1
    assert len(bitacora.historial("calibracion")) == 1


def test_una_linea_corrupta_no_tapa_las_buenas(archivo):
    """Solo append: si una corrida muere a medio write, la linea queda
    cortada. Eso no puede volver ilegible el historial entero."""
    bitacora.anotar_corrida([resultado()], "muestra", MAX)
    with open(archivo, "a", encoding="utf-8") as f:
        f.write('{"evento": "corrida", "nego\n')
    bitacora.anotar_calibracion(8, 8, [])

    assert len(bitacora.historial()) == 2


def test_sin_archivo_el_historial_esta_vacio_no_roto(tmp_path, monkeypatch):
    monkeypatch.setattr(bitacora, "ARCHIVO", str(tmp_path / "no-existe"))
    assert bitacora.historial() == []


# ─────────────────────────────────────────────────────────────────
# Medir es secundario a lo que se mide
# ─────────────────────────────────────────────────────────────────

def test_si_no_se_puede_escribir_la_corrida_sigue(tmp_path, monkeypatch):
    """Una corrida de grafo.py cuesta dinero. Perderla porque la
    bitacora no pudo escribir seria absurdo."""
    monkeypatch.setattr(bitacora, "ARCHIVO",
                        str(tmp_path / "no-existe" / "b.jsonl"))
    assert bitacora.anotar_corrida([resultado()], "muestra", MAX) is False


def test_un_resultado_imposible_de_serializar_no_revienta(archivo):
    class Raro:
        pass

    assert bitacora.anotar("corrida", {"cosa": Raro()}) is False
    assert bitacora.historial() == []
