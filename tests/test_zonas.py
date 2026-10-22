"""Prospectos por zona, para visitar.

Origen (05/10/2026): Se noto que la mayoria de los telefonos que
devuelve Google son fijos. A un fijo no se le puede mandar WhatsApp, y
todo el pipeline producia mensajes de WhatsApp.

De ahi salio otro canal: que los repartidores del papa, que ya hacen la
ruta, entren a los negocios que les quedan de paso.

Eso invierte el orden del resto del proyecto. Antes el puntaje mandaba
y la zona no importaba; aca la ZONA filtra y el puntaje solo ordena lo
que quedo. Estas pruebas cuidan ese orden.

Correr con:  python -m pytest tests/test_zonas.py -v
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import zonas                                                    # noqa: E402
from reglas import es_celular, es_fijo                          # noqa: E402


def negocio(**kw):
    base = {"nombre": "Super X", "provincia": "Alajuela",
            "canton": "Palmares", "direccion": "200 m norte de la iglesia",
            "telefono": "8888 7777", "puntaje": 50, "place_id": "pid",
            "fuera_de_rubro": False, "cerrado": False, "es_cliente": False,
            "es_cadena": False, "posible_competidor": False}
    base.update(kw)
    return base


# --- la numeracion de Costa Rica ---------------------------------------
# Plan Nacional de Numeracion (SUTEL): 2 y 4 fijos, 5/6/7/8 moviles.

@pytest.mark.parametrize("numero", [
    "8888 7777", "6361 8041", "7123 4567", "5012 3456",
    "+506 8888 7777", "506-8888-7777", "88887777",
])
def test_los_moviles_se_reconocen(numero):
    assert es_celular(numero)


@pytest.mark.parametrize("numero", [
    "2445 1234", "+506 2445 1234", "2445-1234", "4000 1234",
])
def test_los_fijos_no_son_celular(numero):
    assert not es_celular(numero)
    assert es_fijo(numero)


@pytest.mark.parametrize("numero", ["", None, "506", "123", "999 999 999 9"])
def test_un_numero_raro_no_es_ninguno_de_los_dos(numero):
    """Ante la duda no se promete un canal que no existe."""
    assert not es_celular(numero)
    assert not es_fijo(numero)


# --- quien entra a la lista --------------------------------------------

@pytest.mark.parametrize("bandera", ["fuera_de_rubro", "cerrado",
                                     "es_cliente"])
def test_no_se_visita_lo_que_prospecto_ya_descarto(bandera):
    assert zonas.visitables([negocio(**{bandera: True})]) == []


def test_sin_direccion_no_se_puede_visitar():
    """Por bueno que sea el puntaje: nadie sabe adonde ir."""
    assert zonas.visitables([negocio(direccion="", puntaje=99)]) == []
    assert zonas.visitables([negocio(direccion="   ")]) == []


def test_una_cadena_si_entra_a_la_lista():
    """Se avisa, no se esconde. Quien esta en la puerta decide."""
    assert len(zonas.visitables([negocio(es_cadena=True)])) == 1


def test_un_posible_competidor_tambien_entra():
    """La senal es una coincidencia de texto, no un veredicto.

    Estos negocios no pasaron por el calificador -- la pantalla no
    llama al modelo -- asi que esconderlos seria confiar en la
    heuristica mas de lo que aguanta.
    """
    assert len(zonas.visitables([negocio(posible_competidor=True)])) == 1


# --- la zona filtra, el puntaje ordena ---------------------------------

def test_la_provincia_filtra_antes_que_el_puntaje():
    """El mejor prospecto de otra provincia no aparece.

    Es el punto entero de esta pantalla: 95 puntos en Limon no le
    sirven al repartidor de Alajuela.
    """
    datos = [negocio(nombre="Limon", provincia="Limón", puntaje=95),
             negocio(nombre="Alajuela", puntaje=40)]

    r = zonas.ruta(datos, provincia="Alajuela")
    assert [d["nombre"] for d in r] == ["Alajuela"]


def test_alajuela_es_la_provincia_por_defecto():
    assert zonas.PROVINCIA_POR_DEFECTO == "Alajuela"


def test_dentro_de_la_zona_manda_el_puntaje():
    datos = [negocio(nombre="bajo", puntaje=20),
             negocio(nombre="alto", puntaje=80),
             negocio(nombre="medio", puntaje=50)]

    assert [d["nombre"] for d in zonas.ruta(datos)] == [
        "alto", "medio", "bajo"]


def test_se_pueden_pedir_varios_cantones():
    """Una ruta cruza mas de uno."""
    datos = [negocio(canton="Palmares"), negocio(canton="Naranjo"),
             negocio(canton="Atenas")]

    r = zonas.ruta(datos, cantones=["Palmares", "Naranjo"])
    assert {d["canton"] for d in r} == {"Palmares", "Naranjo"}


def test_sin_cantones_salen_todos_los_de_la_provincia():
    datos = [negocio(canton="Palmares"), negocio(canton="Atenas")]
    assert len(zonas.ruta(datos, cantones=[])) == 2


def test_el_tope_corta_los_de_menor_puntaje():
    datos = [negocio(nombre=str(i), puntaje=i) for i in range(10)]
    r = zonas.ruta(datos, tope=3)
    assert [d["nombre"] for d in r] == ["9", "8", "7"]


# --- lo que ve el repartidor -------------------------------------------

def test_el_fijo_se_informa_pero_no_se_advierte():
    """Cambio del 06/10: antes esto era un aviso en rojo.

    Un telefono fijo no es un problema -- es como se le llega a ese
    negocio. Lo que merece advertencia es lo que puede cambiar la
    decision de entrar: que sea cadena, o que parezca competidor.
    """
    n = negocio(telefono="2445 1234")
    assert zonas.avisos(n) == []
    assert "fijo" in zonas.canal(n)


def test_no_se_avisa_de_mas_cuando_todo_esta_bien():
    assert zonas.avisos(negocio()) == []


def test_se_avisa_de_cadena_y_de_competidor():
    a = zonas.avisos(negocio(es_cadena=True, posible_competidor=True))
    assert len(a) == 2


def test_el_enlace_de_maps_usa_el_place_id():
    """Mas preciso que buscar por nombre: hay muchos 'Super X'."""
    assert "query_place_id=pid" in zonas.enlace_maps(negocio())


def test_el_enlace_de_maps_sin_place_id_busca_por_texto():
    enlace = zonas.enlace_maps(negocio(place_id=None))
    assert "query=" in enlace and "Super" in enlace


# --- las cifras de la zona ---------------------------------------------

def test_el_resumen_cuenta_lo_que_hay():
    datos = [
        negocio(telefono="8888 7777"),
        negocio(telefono="2445 1234"),
        negocio(es_cadena=True),
        negocio(fuera_de_rubro=True),
        negocio(provincia="Limón"),
    ]
    r = zonas.resumen(datos)

    assert r["total"] == 4              # los de Alajuela, visitables o no
    assert r["visitables"] == 3         # sin el fuera_de_rubro
    assert r["con_celular"] == 2        # el fijo no cuenta
    assert r["cadenas"] == 1


def test_los_cantones_salen_ordenados_por_cantidad():
    datos = [negocio(canton="Palmares")] * 3 + [negocio(canton="Atenas")]
    assert zonas.cantones_con_conteo(datos) == [("Palmares", 3),
                                                ("Atenas", 1)]


def test_sin_archivo_no_rompe(tmp_path):
    assert zonas.cargar(tmp_path / "no_existe.json") == []


# --- lo que lee el vendedor en pantalla --------------------------------
# Origen (06/10/2026): el aviso decia "sin celular: no se le puede
# escribir, hay que ir", en rojo. Sonaba a regaño y a problema, cuando
# es un dato. Y la direccion traia el codigo de ubicacion de Google.

def test_el_plus_code_no_aparece():
    """"XJJC+WCJ" no se puede leer ni preguntar a un vecino."""
    d = zonas.direccion_corta(
        {"direccion": "XJJC+WCJ, 3, Provincia de Alajuela, Atenas"})
    assert "+" not in d
    assert "Atenas" in d


def test_la_provincia_repetida_se_quita():
    """Ya se eligio arriba en la pantalla."""
    assert "Provincia de" not in zonas.direccion_corta(
        {"direccion": "C. 3 Arroyo, Provincia de Alajuela, Alajuela"})


def test_una_direccion_buena_no_se_toca():
    d = "200 m norte de la iglesia, Palmares"
    assert zonas.direccion_corta({"direccion": d}) == d


def test_sin_direccion_devuelve_vacio():
    assert zonas.direccion_corta({}) == ""


@pytest.mark.parametrize("telefono,espera", [
    ("8888 7777", "WhatsApp"),
    ("2446 5141", "fijo"),
    (None, "visitar"),
])
def test_el_canal_dice_como_llegarle(telefono, espera):
    assert espera in zonas.canal({"telefono": telefono})


def test_el_canal_no_es_un_aviso():
    """Un fijo no es una advertencia: es informacion.

    Las advertencias son las que pueden cambiar la decision de entrar.
    """
    assert zonas.avisos({"telefono": "2446 5141"}) == []


def test_cadena_y_competidor_si_son_avisos():
    assert len(zonas.avisos({"es_cadena": True,
                             "posible_competidor": True})) == 2


# --- una sucursal por marca --------------------------------------------
# Origen (07/10/2026), en palabras de quien desarrolla: "me van a aparecer cinco
# palis en un mismo canton (...) voy a perder otros negocios donde
# quizas me es mas facil entrar".
#
# El puntaje suma por resenas y rating, asi que las sucursales de una
# cadena salen juntas y arriba. Eso no es un empate: es la misma
# decision de compra repetida cinco veces.

def test_cinco_palis_se_vuelven_uno():
    datos = [negocio(nombre=f"Pali {i}", puntaje=90 - i) for i in range(5)]
    assert len(zonas.una_por_marca(datos)) == 1


def test_sobrevive_la_sucursal_de_mejor_puntaje():
    """Depende de correr despues de por_puntaje."""
    datos = zonas.por_puntaje([negocio(nombre="Pali Atenas", puntaje=40),
                               negocio(nombre="Pali Grecia", puntaje=88)])
    assert zonas.una_por_marca(datos)[0]["nombre"] == "Pali Grecia"


def test_cada_cadena_deja_su_propia_sucursal():
    """No es 'una cadena en total': es una de cada marca."""
    datos = [negocio(nombre="Pali Grecia"), negocio(nombre="Pali Atenas"),
             negocio(nombre="Walmart Alajuela"),
             negocio(nombre="Auto Mercado Escazu")]
    nombres = [d["nombre"] for d in zonas.una_por_marca(datos)]
    assert nombres == ["Pali Grecia", "Walmart Alajuela",
                       "Auto Mercado Escazu"]


def test_maxi_pali_y_pali_son_la_misma_marca():
    """Formatos distintos de tienda, una sola decision de compra.

    Es un juicio de negocio escrito a mano en MARCAS, no algo que se
    deduzca del nombre.
    """
    datos = [negocio(nombre="Maxi Pali Naranjo"), negocio(nombre="Pali Zarcero")]
    assert len(zonas.una_por_marca(datos)) == 1


def test_los_independientes_nunca_se_agrupan():
    """Son el objetivo de la pantalla, no el ruido.

    Dos pulperias distintas no son la misma cosa, y agruparlas
    esconderia justo lo que se quiere encontrar.
    """
    datos = [negocio(nombre="Mini Super San Luis"),
             negocio(nombre="Pulperia La Esquina"),
             negocio(nombre="Abastecedor El Progreso")]
    assert len(zonas.una_por_marca(datos)) == 3


def test_se_pueden_pedir_dos_por_marca():
    datos = [negocio(nombre=f"Pali {i}") for i in range(5)]
    assert len(zonas.una_por_marca(datos, por=2)) == 2


def test_por_marca_none_muestra_todas():
    """La salida de emergencia: no se esconde nada en silencio."""
    datos = [negocio(nombre=f"Pali {i}") for i in range(5)]
    assert len(zonas.una_por_marca(datos, por=None)) == 5


def test_no_descarta_nada_del_archivo():
    """Filtra lo que se muestra, no lo que existe."""
    datos = [negocio(nombre=f"Pali {i}") for i in range(5)]
    antes = len(datos)
    zonas.una_por_marca(datos)
    assert len(datos) == antes


def test_ruta_aplica_una_por_marca_por_defecto():
    datos = [negocio(nombre=f"Pali {i}", puntaje=90) for i in range(4)]
    datos.append(negocio(nombre="Mini Super San Luis", puntaje=10))

    nombres = [d["nombre"] for d in zonas.ruta(datos)]
    assert nombres == ["Pali 0", "Mini Super San Luis"]


def test_el_tope_se_aplica_despues_de_filtrar():
    """Si no, un tope de 3 se gastaria en sucursales que se esconden.

    Aca hay 5 Palis de alto puntaje y 3 independientes. Con el tope
    antes del filtro saldria 1 negocio; con el tope al final salen 3.
    """
    datos = [negocio(nombre=f"Pali {i}", puntaje=90) for i in range(5)]
    datos += [negocio(nombre=f"Mini Super {i}", puntaje=50) for i in range(3)]

    assert len(zonas.ruta(datos, tope=3)) == 3


def test_marca_y_es_cadena_nunca_se_contradicen():
    """El candado real de este cambio.

    `es_cadena` lo pone prospecto.py con CADENAS; `marca()` usa MARCAS.
    Si alguien agrega un patron a una lista y no a la otra, un negocio
    seria cadena sin marca (y no se agruparia nunca) o tendria marca sin
    ser cadena. CADENAS se deriva de MARCAS justamente para que no pueda
    pasar, y esto lo verifica.
    """
    from reglas import CADENAS, contiene_palabra, marca, normalizar

    nombres = ["Pali Grecia", "Maxi Pali Naranjo", "Walmart Alajuela",
               "Auto Mercado Escazu", "Automercado Lindora",
               "Perimercado Heredia", "Peri - San Ramon",
               "Mega Super Poas", "Megasuper Palmares", "Vindi Santa Ana",
               "AMPM Centro", "PriceSmart Zapote", "Fresh Market Escazu",
               "Mas x Menos Cartago", "MasxMenos Tibas",
               "Mini Super San Luis", "Pulperia La Esquina",
               "Carniceria Don Beto"]

    for nombre in nombres:
        es_cadena = contiene_palabra(CADENAS, normalizar(nombre))
        tiene_marca = marca({"nombre": nombre}) is not None
        assert es_cadena == tiene_marca, nombre