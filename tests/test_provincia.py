"""La tanda de WhatsApp tiene que ser un recorrido posible.

Punto 30 (22/10/2026). Lo encontro quien desarrolla el 14/10 mirando la pantalla
de Mensajes: salian un Peri en Escazu, uno en Heredia y dos en
Alajuela. `grafo.py whatsapp 20` ordenaba los 955 del pais entero por
puntaje y se quedaba con los primeros.

Es el mismo problema que los cinco Palis (punto 23) en otra forma: el
puntaje ordena por lo que el cree importante y se come una dimension
que si le importa a quien trabaja. Alla era la marca; aca la
geografia.

Lo que estas pruebas cuidan, y por que cada una:

  - que el filtro exista y realmente filtre
  - que filtre ANTES de llamar al modelo, no al mostrar: filtrando al
    mostrar, ya se pago por redactar mensajes que nadie va a usar
  - que "alajuela" encuentre "Alajuela", porque un filtro que falla en
    silencio es peor que uno que no existe
  - que sin provincia se comporte como antes

Correr con:  python -m pytest tests/test_provincia.py -v
"""

import inspect
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import grafo                                                    # noqa: E402
import zonas                                                    # noqa: E402


def negocio(nombre, provincia, puntaje, **kw):
    # fuera_de_rubro, cerrado y es_cliente se leen con d["..."], no con
    # .get(): candidatos() exige que existan. Un negocio real siempre
    # los trae porque los escribe prospecto.py.
    base = {"nombre": nombre, "provincia": provincia, "canton": "X",
            "categoria": "Supermercado", "telefono": "88880000",
            "direccion": "100 m sur", "puntaje": puntaje,
            "es_cadena": False, "fuera_de_rubro": False,
            "cerrado": False, "es_cliente": False}
    base.update(kw)
    return base


# Los de mayor puntaje son de otras provincias a proposito: es
# exactamente el caso que rompia la tanda.
DATOS = [
    negocio("Peri Escazu", "San José", 99, es_cadena=True),
    negocio("Super Heredia", "Heredia", 95),
    negocio("Super Limon", "Limón", 90),
    negocio("Super Grecia", "Alajuela", 50),
    negocio("Super Palmares", "Alajuela", 40),
    negocio("Super Naranjo", "Alajuela", 30),
    negocio("Fijo Alajuela", "Alajuela", 80, telefono="24501234"),
]


# ─────────────────────────────────────────────────────────────────
# Resolver el nombre
# ─────────────────────────────────────────────────────────────────

def test_sin_tilde_y_en_minuscula_igual_encuentra():
    """`whatsapp 20 san jose` tiene que funcionar: nadie escribe la
    tilde en una terminal."""
    assert zonas.resolver_provincia(DATOS, "san jose") == "San José"
    assert zonas.resolver_provincia(DATOS, "LIMON") == "Limón"


def test_una_provincia_que_no_esta_en_los_datos_devuelve_none():
    """No basta con que exista en Costa Rica: tiene que haber negocios.
    Si no, el comando correria sobre cero y parecia que funciono."""
    assert zonas.resolver_provincia(DATOS, "Cartago") is None


def test_provincias_sale_de_los_datos_no_de_una_lista_fija():
    assert zonas.provincias(DATOS) == ["Alajuela", "Heredia", "Limón",
                                       "San José"]


# ─────────────────────────────────────────────────────────────────
# Filtrar
# ─────────────────────────────────────────────────────────────────

def test_con_provincia_la_tanda_sale_toda_de_ahi():
    elegidos = grafo.con_whatsapp(DATOS, provincia="Alajuela")
    assert {n["provincia"] for n in elegidos} == {"Alajuela"}


def test_sin_provincia_se_comporta_como_antes():
    """El argumento es opcional y no cambia lo que ya existia."""
    elegidos = grafo.con_whatsapp(DATOS)
    assert len({n["provincia"] for n in elegidos}) > 1


def test_el_tope_se_aplica_despues_de_la_provincia():
    """Al reves, el tope se comeria la provincia: los tres primeros del
    pais no son de Alajuela, y la tanda saldria vacia."""
    elegidos = grafo.con_whatsapp(DATOS, tope=2, provincia="Alajuela")
    assert len(elegidos) == 2
    assert {n["provincia"] for n in elegidos} == {"Alajuela"}


def test_dentro_de_la_provincia_sigue_mandando_el_puntaje():
    elegidos = grafo.con_whatsapp(DATOS, provincia="Alajuela")
    puntajes = [n["puntaje"] for n in elegidos]
    assert puntajes == sorted(puntajes, reverse=True)


def test_la_provincia_no_pasa_por_encima_del_canal():
    """Un fijo de Alajuela sigue sin recibir WhatsApp. El filtro de
    provincia se suma al de celular, no lo reemplaza."""
    nombres = {n["nombre"] for n in grafo.con_whatsapp(DATOS,
                                                       provincia="Alajuela")}
    assert "Fijo Alajuela" not in nombres


def test_las_cadenas_tambien_se_pueden_pedir_por_provincia():
    elegidos = grafo.cadenas_con_whatsapp(DATOS, provincia="San José")
    assert [n["nombre"] for n in elegidos] == ["Peri Escazu"]
    assert grafo.cadenas_con_whatsapp(DATOS, provincia="Alajuela") == []


# ─────────────────────────────────────────────────────────────────
# Donde va el filtro
# ─────────────────────────────────────────────────────────────────

def test_el_filtro_va_antes_del_modelo():
    """Si viviera en la pantalla, el modelo ya habria redactado
    mensajes para siete provincias y eso ya se pago."""
    assert "provincia" in inspect.signature(grafo.con_whatsapp).parameters


def test_la_geografia_no_se_reescribe_en_grafo():
    """`de_provincia` vive en zonas.py. Una regla, un lugar."""
    assert grafo.de_provincia is zonas.de_provincia


def test_la_bitacora_guarda_de_que_provincia_fue_la_corrida():
    """Sin eso, dos corridas no son comparables: una tanda nacional y
    una de Alajuela tienen poblaciones distintas."""
    import bitacora
    assert "provincia" in inspect.signature(
        bitacora.anotar_corrida).parameters
