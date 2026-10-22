"""Punto 8 de la hoja de ruta: el prompt no lleva datos personales.

Origen: ARQUITECTURA.md, capa 2. Se enviaban direccion y telefono de
629 negocios a un proveedor externo. Son datos de terceros que no
dieron consentimiento. Estaban publicados en Google Maps, asi que no
eran secretos -- pero mandarlos afuera era una decision que nadie
habia tomado a proposito.

Estas pruebas NO revisan la lista de campos. Eso seria tautologico:
la lista diria lo que la lista dice. Arman el prompt de verdad con un
negocio que SI tiene telefono y direccion, y comprueban que esos
valores no aparecen en el texto que sale.

Correr con:  python -m pytest tests/test_privacidad.py -v
"""

import inspect
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from grafo import _describir                                    # noqa: E402
from reglas import (CAMPOS_CLASIFICADOR, CAMPOS_PROHIBIDOS,     # noqa: E402
                    CAMPOS_REDACTOR)

# Un negocio inventado, pero con todos los campos llenos. Los valores
# son raros a proposito: si alguno se filtra, se ve en el texto.
NEGOCIO = {
    "nombre": "Super El Ejemplo",
    "categoria": "grocery_store",
    "direccion": "Calle Nunca Jamas 777, contiguo a la nada",
    "canton": "Grecia",
    "provincia": "Alajuela",
    "rating": 4.3,
    "num_resenas": 88,
    "telefono": "+506 8888 7777",
    "sitio_web": "https://ejemplo.cr",
    "es_cadena": False,
    "posible_competidor": False,
    "distancia_km": 23.4,
    "place_id": "ChIJ_ejemplo_no_debe_salir",
}

TODOS = [("clasificador", CAMPOS_CLASIFICADOR),
         ("redactor", CAMPOS_REDACTOR)]


# --- lo que no puede salir -------------------------------------------

@pytest.mark.parametrize("nodo,campos", TODOS)
def test_no_sale_el_telefono(nodo, campos):
    texto = _describir(NEGOCIO, campos)
    assert "8888" not in texto
    assert "telefono" not in texto.lower()


@pytest.mark.parametrize("nodo,campos", TODOS)
def test_no_sale_la_direccion(nodo, campos):
    texto = _describir(NEGOCIO, campos)
    assert "Nunca Jamas" not in texto
    assert "direccion" not in texto.lower()


@pytest.mark.parametrize("nodo,campos", TODOS)
def test_no_sale_el_place_id(nodo, campos):
    """Identificador unico de Google. No le sirve de nada al modelo."""
    assert "ChIJ" not in _describir(NEGOCIO, campos)


def test_el_redactor_no_ve_la_distancia():
    """El bug de la ruta inventada, convertido en candado.

    En una corrida anterior el redactor uso la distancia para afirmar
    "su sucursal nos queda dentro de nuestra ruta". Nadie se lo habia
    dicho. Antes esto estaba solo escrito en un comentario.
    """
    texto = _describir(NEGOCIO, CAMPOS_REDACTOR)
    assert "23.4" not in texto
    assert "istancia" not in texto


# --- lo que si tiene que salir ---------------------------------------
# Sin estas, una lista blanca vacia pasaria todas las de arriba.

@pytest.mark.parametrize("nodo,campos", TODOS)
def test_si_sale_lo_que_el_modelo_necesita(nodo, campos):
    texto = _describir(NEGOCIO, campos)
    assert "Super El Ejemplo" in texto      # para dirigirse al negocio
    assert "Grecia" in texto                # define si hay reparto propio
    assert "grocery_store" in texto         # base de la clasificacion


def test_el_clasificador_si_ve_la_distancia():
    assert "23.4" in _describir(NEGOCIO, CAMPOS_CLASIFICADOR)


# --- candados de arquitectura ----------------------------------------

@pytest.mark.parametrize("nodo,campos", TODOS)
def test_ningun_campo_prohibido_esta_en_la_lista_blanca(nodo, campos):
    assert not set(campos) & set(CAMPOS_PROHIBIDOS)


def test_describir_no_sabe_escribir_campos_prohibidos():
    """La lista blanca sola no alcanza.

    Si alguien agrega una linea con el telefono dentro de _describir,
    sin pasar por la lista, las pruebas de arriba no lo verian cuando
    el campo no esta en el diccionario de ese nodo. Esta lee el codigo
    fuente de la funcion.
    """
    # Sin el docstring: la explicacion de la regla nombra los campos
    # prohibidos, y explicar la regla no es romperla.
    fuente = inspect.getsource(_describir)
    fuente = fuente.replace(_describir.__doc__ or "", "").lower()
    for prohibido in CAMPOS_PROHIBIDOS:
        assert prohibido not in fuente, (
            f"_describir() menciona '{prohibido}'. Ese campo no puede "
            f"llegar al modelo; ver ARQUITECTURA.md capa 2."
        )


def test_los_campos_viven_solo_en_reglas_py():
    """Una regla, un lugar. Igual que CONTEXTO_FABRICA."""
    texto = (RAIZ / "grafo.py").read_text(encoding="utf-8")
    for definicion in ("CAMPOS_CLASIFICADOR = ", "CAMPOS_REDACTOR = "):
        assert definicion not in texto