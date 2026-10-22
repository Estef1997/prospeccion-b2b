"""
Los bugs reales del proyecto, convertidos en verificacion automatica.

Cada test de aqui salio de un error que ya paso. No son pruebas
genericas: son candados para que esos errores no puedan volver.

    pytest

Cuando aparezca un bug nuevo, se agrega aqui antes de arreglarlo.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from reglas import (  # noqa: E402
    CADENAS,
    CLIENTES_ACTUALES,
    PALABRAS_REPARTO,
    PROHIBIDAS_SIEMPRE,
    SENALES_COMPETIDOR,
    contexto_para,
    contiene_palabra,
    normalizar,
    prohibidas_para,
    tiene_reparto_propio,
)


def es_cadena(nombre):
    return contiene_palabra(CADENAS, normalizar(nombre))


def es_cliente(nombre):
    return contiene_palabra(CLIENTES_ACTUALES, normalizar(nombre))


# ═══════════════════════════════════════════════════════════════
# BUG 1 — "peri " con espacio nunca coincidia
#
# Google devuelve las sucursales como "Peri - San Ramon". La lista
# tenia "peri •" y "peri ", y ninguno coincide nunca: contiene_palabra
# pone \b al final, y despues de un espacio o un simbolo no hay limite
# de palabra. Las tres sucursales de Peri pasaron el filtro.
# ═══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("nombre", [
    "Peri - San Ramón",
    "Perimercado Central",
    "Súper Peri",
    "PERI Grecia",
])
def test_peri_se_detecta(nombre):
    assert es_cadena(nombre), f"{nombre!r} deberia marcarse como cadena"


@pytest.mark.parametrize("nombre", [
    "Pulpería La Esquina",
    "Abastecedor Prosperidad",
    "Comercial Periférico",
    "Supermercado Superior",
])
def test_peri_no_atrapa_falsos_positivos(nombre):
    """El lado que se olvida: lo que NO debe coincidir.

    "peri" como subcadena atrapa Pulperia, Prosperidad, Periferico y
    Superior. Por eso hace falta limite de palabra.
    """
    assert not es_cadena(nombre), f"{nombre!r} NO es una cadena"


# ═══════════════════════════════════════════════════════════════
# BUG 2 — "super molina" no atrapaba "Supermercado Molina"
#
# El patron era la frase completa. Un cliente actual estuvo a punto de
# recibir un mensaje de presentacion en frio.
# ═══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("nombre", [
    "Supermercado Molina",
    "Super Molina San Ramón",
    "Molina y Hermanos",
])
def test_molina_se_detecta_como_cliente(nombre):
    assert es_cliente(nombre), f"{nombre!r} es cliente actual"


# ═══════════════════════════════════════════════════════════════
# BUG 3 — "Mega Súper • Poás" escapaba por la tilde
#
# La lista decia "mega super" sin acento y el nombre venia con acento.
# ═══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("nombre", [
    "Mega Súper Poás",
    "Mega Super Poas",
    "MEGASÚPER Grecia",
])
def test_acentos_no_dejan_escapar_cadenas(nombre):
    assert es_cadena(nombre), f"{nombre!r} deberia marcarse como cadena"


# ═══════════════════════════════════════════════════════════════
# INVARIANTE — ningun patron puede terminar mal
#
# Generaliza el bug 1: en vez de verificar solo el caso conocido,
# impide que vuelva a introducirse uno igual con otro nombre.
# ═══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("patron", CADENAS + CLIENTES_ACTUALES)
def test_ningun_patron_termina_mal(patron):
    """Un patron que termina en espacio o simbolo nunca coincide.

    Origen: "peri " y "peri •" estuvieron meses en la lista sin
    coincidir jamas con nada.
    """
    assert patron == patron.strip(), (
        f"{patron!r} tiene espacios al borde: nunca va a coincidir"
    )
    assert patron[-1].isalnum(), (
        f"{patron!r} termina en simbolo: el \\b final nunca se cumple"
    )


# ═══════════════════════════════════════════════════════════════
# SENALES DE COMPETIDOR — subcadena a proposito
#
# Es la unica excepcion al limite de palabra, y es deliberada: tienen
# que atrapar el plural.
# ═══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("nombre", [
    "Embutidos Lucy",
    "Chorizos Don Beto",
    "Salchichonería El Trigal",
])
def test_senales_competidor_atrapan_plural(nombre):
    texto = normalizar(nombre)
    assert any(s in texto for s in SENALES_COMPETIDOR), (
        f"{nombre!r} deberia encender la senal de competidor"
    )


# ═══════════════════════════════════════════════════════════════
# REPARTO PROPIO — el caso que rompio el contrato compartido
#
# El redactor podia mencionar reparto en Palmares, San Ramon y Naranjo,
# pero el validador lo tenia prohibido en su lista fija.
# ═══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("canton", ["Palmares", "San Ramón", "Naranjo"])
def test_zonas_con_reparto_propio(canton):
    assert tiene_reparto_propio({"canton": canton})


@pytest.mark.parametrize("canton", ["Grecia", "Alajuela", "Heredia", None])
def test_zonas_sin_reparto_propio(canton):
    assert not tiene_reparto_propio({"canton": canton})


def test_redactor_solo_ve_reparto_donde_es_cierto():
    """Dato que no ve, dato que no puede inventar."""
    con = contexto_para({"canton": "Palmares"})
    sin = contexto_para({"canton": "Grecia"})

    assert "reparto propio" in con
    assert "reparto propio" not in sin


def test_validador_y_redactor_coinciden():
    """El candado del contrato compartido.

    Si el redactor puede mencionar reparto, el validador NO puede
    prohibirlo. Y al reves.
    """
    for canton in ("Palmares", "San Ramón", "Naranjo", "Grecia", "Limón"):
        negocio = {"canton": canton}
        puede_mencionar = tiene_reparto_propio(negocio)
        esta_prohibido = "reparto" in prohibidas_para(negocio)

        assert puede_mencionar != esta_prohibido, (
            f"{canton}: el redactor y el validador no coinciden"
        )


def test_clientes_actuales_prohibidos_en_toda_zona():
    """Que haya reparto propio no habilita mencionar a otros clientes.

    Es una decision comercial, no logistica.
    """
    for canton in ("Palmares", "Grecia"):
        prohibidas = prohibidas_para({"canton": canton})
        assert "ejemplo uno" in prohibidas
        assert "certificad" in prohibidas


# ═══════════════════════════════════════════════════════════════
# REGLA ARQUITECTONICA — una regla, un lugar
#
# Esto no verifica comportamiento: verifica que nadie vuelva a
# duplicar las reglas. Leccion 10: las reglas arquitectonicas
# tienen que ser ejecutables, no comentarios pidiendo disciplina.
# ═══════════════════════════════════════════════════════════════

RAIZ = Path(__file__).parent.parent

# Todos los archivos vivos que usan reglas de negocio.
#
# Antes esta lista tenia solo grafo.py y validar_claude.py -- los dos
# donde habia pasado el bug. prospecto.py, que es EL QUE ESCRIBE las
# banderas, nunca se reviso, y tenia su propia copia desincronizada.
#
# Leccion del 07/10/2026: una prueba escrita para el caso que paso no
# cubre la clase de error. Cuando se agregue un archivo que importe de
# reglas.py, va aqui.
MODULOS_CON_REGLAS = ["prospecto.py", "grafo.py", "validar.py",
                      "validar_claude.py", "zonas.py"]


@pytest.mark.parametrize("archivo", MODULOS_CON_REGLAS)
def test_las_reglas_viven_solo_en_reglas_py(archivo):
    """Ningun otro archivo define el contexto ni las listas.

    Origen: CONTEXTO_FABRICA estaba escrito en grafo.py y en
    validar_claude.py, con un comentario pidiendo mantenerlas
    identicas a mano. Se desincronizaron al primer cambio.
    """
    ruta = RAIZ / archivo
    if not ruta.exists():
        pytest.skip(f"{archivo} no esta en esta carpeta")

    texto = ruta.read_text(encoding="utf-8")

    for definicion in ("CONTEXTO_FABRICA = ", "PROHIBIDAS = ",
                       "CADENAS = ", "CLIENTES_ACTUALES = "):
        assert definicion not in texto, (
            f"{archivo} define {definicion.strip(' =')}. "
            f"Tiene que importarlo de reglas.py."
        )


# ═══════════════════════════════════════════════════════════════
# "salchicha" no es "salchichon"
#
# Origen (05/10/2026): en una corrida real el redactor abrio con
# "salchicha criolla" y dos frases despues escribio "salchichon
# criollo". El validador lo aprobo -- Jev le dio 0.02 a
# inventa_productos, porque semanticamente son casi lo mismo.
#
# Lo que puede ser una regla, debe ser una regla.
# ═══════════════════════════════════════════════════════════════

def test_salchicha_esta_prohibida():
    assert "salchicha" in prohibidas_para({"canton": "Grecia"})


def test_salchicha_se_detecta_en_un_mensaje():
    """Como lo compara la capa 1: subcadena en minuscula."""
    mensaje = "26 anos de producir salchicha criolla ahumada en lena"
    assert any(p in mensaje.lower()
               for p in prohibidas_para({"canton": "Grecia"}))


def test_el_plural_se_detecta_sin_listarlo():
    """La capa 1 usa subcadena, asi que "salchichas" cae sola."""
    assert "salchicha" in "hacemos salchichas criollas".lower()


@pytest.mark.parametrize("mensaje", [
    "produce unicamente salchichon criollo ahumado en lena",
    "salchichon en tripa de res y tripa plastica",
    "nuestro salchichon lleva 26 anos",
])
def test_salchichon_el_producto_real_no_se_marca(mensaje):
    """El falso positivo que arruinaria la regla.

    "salchicha" no aparece dentro de "salchichon": difieren en la
    novena letra. Si alguna vez alguien escribe el patron como
    "salchich", esta prueba lo atrapa.
    """
    assert not any(p in mensaje.lower()
                   for p in prohibidas_para({"canton": "Grecia"}))


def test_la_regla_aplica_tambien_en_zona_de_reparto_propio():
    """No depende del canton: el producto es el mismo en todo el pais."""
    assert "salchicha" in prohibidas_para({"canton": "Palmares"})


# ═══════════════════════════════════════════════════════════════
# "procesadora" — una planta no es un punto de venta
#
# Origen (05/10/2026): al buscar en Guanacaste aparecio
# "Distribuidora La Anexion (Planta procesadora)" en Canas, con 59
# puntos y sin ningun aviso en la pantalla de Rutas.
#
# Esa pantalla no llama al calificador -- lee datos crudos -- asi que
# la unica defensa es la senal por nombre.
# ═══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("nombre", [
    "Distribuidora La Anexión (Planta procesadora)",
    "PROCESADORA DE CARNES DEL SUR",
    "Procesadora Avícola",
])
def test_procesadora_enciende_la_senal(nombre):
    assert any(normalizar(s) in normalizar(nombre)
               for s in SENALES_COMPETIDOR)


@pytest.mark.parametrize("nombre", [
    "Distribuidora La Anexión",
    "Distribuidora de Alimentos Cañas",
])
def test_distribuidora_sola_no_enciende_nada(nombre):
    """Una distribuidora compra al por mayor y revende: es cliente.

    Lo que la vuelve sospechosa es "procesadora", no "distribuidora".
    Si alguien agrega "distribuidora" a la lista, esta prueba falla.
    """
    assert not any(normalizar(s) in normalizar(nombre)
                   for s in SENALES_COMPETIDOR)


# --- el bug de AM PM ---------------------------------------------------
# Origen (07/10/2026): `revisar.py repetidos` mostro "AM PM • Cartago
# Centrale" 6 veces entre los nombres que NO estan en CADENAS. El patron
# "ampm" si estaba en la lista -- pero Google escribe la marca con un
# espacio en medio, y \bampm\b nunca coincide con "am pm".
#
# Es el mismo bug que "peri •", en otra forma: el patron existia, se veia
# correcto, y no coincidia con nada. Un patron muerto no da error.

@pytest.mark.parametrize("nombre", [
    "AM PM • Cartago Centrale",
    "AM PM • El Guarco",
    "AMPM Centro",
    "ampm Escazú",
])
def test_ampm_se_detecta_con_y_sin_espacio(nombre):
    assert contiene_palabra(CADENAS, normalizar(nombre))


def test_am_pm_no_atrapa_palabras_comunes():
    """"am" y "pm" sueltos son palabras de hora.

    El patron son las dos juntas, asi que un nombre que solo tiene una
    no debe coincidir.
    """
    for nombre in ["Super El Amanecer", "Pulperia PM", "Carniceria Amparo"]:
        assert not contiene_palabra(["am pm", "ampm"], normalizar(nombre)), \
            nombre


# --- las cadenas que aparecieron el 07/10 ------------------------------
# Origen: `revisar.py repetidos` sobre los 3.349 del archivo nacional.
# Seis marcas con sucursales que la lista no conocia. Los nombres de
# abajo son los reales, tal como los devuelve Google.

@pytest.mark.parametrize("nombre", [
    "Súper Compro El Coco", "Super Compro Coronado", "Súper Compro Liberia",
    "Supermercado BM", "Supermercado BM • Daniel Flores",
    "Supermercado BM Quepos",
    "Súper Dos • La Fortuna", "Súper dos ciudad Quesada",
    "Ancyfer Market • Escazú", "Ancyfer Market • Curridabat",
    "Supermercado CoopeAgri Central (San Isidro)",
    "Supermercado CoopeAgri Villa Ligia",
    "Supermercado Cadesur • Daniel Flores", "Supermercado Cadesur Quepos",
])
def test_las_cadenas_nuevas_se_detectan(nombre):
    assert contiene_palabra(CADENAS, normalizar(nombre)), nombre


@pytest.mark.parametrize("nombre", [
    "Mini Super San Luis",
    "Supermercado El Marino",
    "Súper La Plaza",
    "Pulpería La Esquina",
    "Carnicería Don Pedro",
    "Abastecedor El Pueblo",
])
def test_los_independientes_siguen_sin_marcarse(nombre):
    """El riesgo real de agregar patrones es atrapar de mas.

    Hay 630 negocios con "mini super" en el nombre y 23 con
    "supermercado el". Un patron generico se los lleva a todos y el
    sistema deja de ver justo a los negocios que busca.
    """
    assert not contiene_palabra(CADENAS, normalizar(nombre)), nombre


# --- el candado que de verdad hacia falta ------------------------------
# Origen (07/10/2026): se agregaron 6 cadenas y el patron "am pm",
# pytest dio 209 passed, y `prospecto.py reetiquetar` dijo "Cambiaron 0".
#
# La causa: prospecto.py definia sus propias CADENAS. Las pruebas
# verificaban reglas.py, que estaba perfecto, mientras el archivo que
# escribe las banderas usaba otra lista.
#
# El escaneo de texto de arriba previene que vuelva a escribirse. Esto
# verifica que de verdad sea EL MISMO OBJETO en memoria, que es lo que
# habria fallado ese dia.

def test_los_modulos_usan_las_listas_de_reglas_no_una_copia():
    """`is`, no `==`: una copia igual hoy se desincroniza manana."""
    import prospecto

    import reglas

    for nombre in ("CADENAS", "CLIENTES_ACTUALES", "SENALES_COMPETIDOR"):
        assert getattr(prospecto, nombre) is getattr(reglas, nombre), (
            f"prospecto.{nombre} no es el de reglas.py. "
            f"Cambiar la regla no va a tener efecto al reetiquetar."
        )


def test_el_cliente_actual_que_se_desincronizo():
    """Caso real: 'feria ejemplo dos' estaba en reglas.py y no en
    la copia de prospecto.py.

    D'Feria Ejemplo Dos es cliente de la fabrica. Con la bandera
    mal puesta queda como prospecto y puede recibir un mensaje de
    presentacion en frio.

    Es la segunda vez que este cliente casi recibe uno: la primera fue
    el patron "super molina" que no coincidia con "Supermercado Molina".
    """
    from prospecto import etiquetar

    r = etiquetar({"nombre": "D'Feria Ejemplo Dos",
                   "categoria": "carniceria", "estado": "OPERATIONAL"})
    assert r["es_cliente"], "Un cliente actual quedo marcado como prospecto"