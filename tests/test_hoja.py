"""La hoja de Google es una VISTA, no una fuente.

Quien es el dueno de que:

    respuestas.json   <- lo escribe el app (registro.py)
    la hoja           <- a_sheets.py la llena desde ahi

Antes las columnas Estado y Notas se escribian a mano en la hoja. Con
el app habria dos lugares donde anotar lo mismo y se desincronizarian
al primer cambio -- el mismo bug de CONTEXTO_FABRICA, que vivia en
grafo.py y en validar_claude.py a la vez.

El peor bug posible de este proyecto seria pisar lo que una persona
anoto. Eso es lo que vigilan estas pruebas.

Correr con:  python -m pytest tests/test_hoja.py -v
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import registro                                                 # noqa: E402
from a_sheets import (COLUMNAS, COLUMNAS_MANUALES,              # noqa: E402
                      preservar_manuales)

NEGOCIO = {"nombre": "Supermercados Tres SR", "place_id": "pid_1"}
OTRO = {"nombre": "Mini Super Feng", "place_id": "pid_2"}


class HojaFalsa:
    """Imita lo unico que preservar_manuales le pide a gspread."""

    def __init__(self, filas=()):
        self._filas = list(filas)

    def get_all_records(self):
        return self._filas


@pytest.fixture
def sin_registro(monkeypatch, tmp_path):
    """Aisla respuestas.json: las pruebas no tocan el archivo real."""
    monkeypatch.setattr(registro, "ARCHIVO", str(tmp_path / "r.json"))
    monkeypatch.setattr(registro, "cargar", lambda ruta=None: {})
    return tmp_path


def con_registro(monkeypatch, registros):
    monkeypatch.setattr(registro, "cargar", lambda ruta=None: registros)


# --- el registro es la fuente ------------------------------------------

def test_lo_anotado_en_el_app_llega_a_la_hoja(monkeypatch):
    con_registro(monkeypatch, registro.anotar(
        {}, "pid_1", estado="interesado", enviado="2026-10-05",
        mensaje="tal cual", notas="pidio lista"))

    g = preservar_manuales(HojaFalsa(), [NEGOCIO])
    assert g["Supermercados Tres SR"] == [
        "interesado", "2026-10-05", "tal cual", "pidio lista"]


def test_el_registro_le_gana_a_lo_escrito_a_mano(monkeypatch):
    """Si estan los dos, el de la hoja es el viejo."""
    con_registro(monkeypatch, registro.anotar(
        {}, "pid_1", estado="interesado"))

    hoja = HojaFalsa([{"Negocio": "Supermercados Tres SR",
                       "Estado": "no", "Enviado": "", "Mensaje": "",
                       "Notas": "dato viejo"}])

    assert preservar_manuales(hoja, [NEGOCIO])[
        "Supermercados Tres SR"][0] == "interesado"


# --- no perder lo de antes ---------------------------------------------

def test_lo_escrito_a_mano_antes_del_app_no_se_pierde(sin_registro):
    """Migracion. La hoja de hoy tiene filas llenas a mano.

    Mientras ese negocio no este en respuestas.json, lo de la hoja se
    conserva. Descartarlo seria borrar trabajo sin avisar.
    """
    hoja = HojaFalsa([{"Negocio": "Mini Super Feng", "Estado": "enviado",
                       "Enviado": "", "Mensaje": "", "Notas": "llamar"}])

    g = preservar_manuales(hoja, [OTRO])
    assert g["Mini Super Feng"] == ["enviado", "", "", "llamar"]


def test_una_hoja_vieja_sin_las_columnas_nuevas_no_rompe(sin_registro):
    """La hoja actual solo tiene Estado y Notas."""
    hoja = HojaFalsa([{"Negocio": "Mini Super Feng",
                       "Estado": "enviado", "Notas": "llamar"}])

    assert preservar_manuales(hoja, [OTRO])["Mini Super Feng"] == [
        "enviado", "", "", "llamar"]


def test_una_hoja_inalcanzable_no_borra_lo_del_registro(monkeypatch):
    """Sin red, el registro alcanza: no depende de la hoja."""
    con_registro(monkeypatch, registro.anotar(
        {}, "pid_1", estado="interesado"))

    class Rota:
        def get_all_records(self):
            raise ConnectionError("sin red")

    g = preservar_manuales(Rota(), [NEGOCIO])
    assert g["Supermercados Tres SR"][0] == "interesado"


def test_un_negocio_sin_nada_anotado_no_aparece(sin_registro):
    assert preservar_manuales(HojaFalsa(), [NEGOCIO]) == {}


# --- candados de arquitectura ------------------------------------------

def test_ninguna_columna_manual_la_escribe_el_script():
    """Una columna no puede tener dos duenos."""
    automaticas = {titulo for _, titulo in COLUMNAS}
    assert not automaticas & set(COLUMNAS_MANUALES)


def test_las_columnas_manuales_calzan_con_los_campos_del_registro():
    """Si alguien agrega una columna y se olvida del registro, salta."""
    assert len(COLUMNAS_MANUALES) == len(registro.CAMPOS)


def test_el_vocabulario_vive_solo_en_registro_py():
    """Una regla, un lugar. Igual que CONTEXTO_FABRICA."""
    texto = (RAIZ / "a_sheets.py").read_text(encoding="utf-8")
    for definicion in ("ESTADOS = ", "MENSAJES = "):
        assert definicion not in texto, (
            f"a_sheets.py define {definicion.strip(' =')}. "
            f"Tiene que importarlo de registro.py."
        )