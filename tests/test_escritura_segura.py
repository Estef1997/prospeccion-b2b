"""Que una escritura fallida nunca deje la hoja vacia.

Origen: revision externa del repo publico, 03/11/2026. Dos hallazgos de
severidad alta que se multiplicaban entre si.

    1a. escribir() hacia hoja.clear() y despues hoja.update(). Son DOS
        llamadas a Google: si la segunda falla, la pestaña queda vacia.
    1b. Si Sheets no respondia, el app pasaba al disco local y esa
        decision quedaba cacheada. En Streamlit Cloud el disco se borra.

Las respuestas son el unico dato del proyecto que no se puede volver a
generar, asi que el fallo podia ser silencioso E irrecuperable.

REGLA DE ESTE ARCHIVO, QUE NO SE NEGOCIA

**Ninguna prueba toca la hoja de Google real.** credenciales.json da
permiso de ESCRITURA sobre la hoja del papa. Una prueba que se
equivoque de objetivo no falla: borra. Todo lo de Sheets va contra
PestanaFalsa, y conectar() esta siempre reemplazado.

No levantan Streamlit. La logica vive fuera de las pantallas justamente
para poder probarla sin pantalla.

Correr con:  python -m pytest tests/test_escritura_segura.py -v
"""

import ast
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import almacen_sheets                                           # noqa: E402
import registro                                                 # noqa: E402


# ─────────────────────────────────────────────────────────────────
# La pestaña de mentira
# ─────────────────────────────────────────────────────────────────

class PestanaFalsa:
    """Se comporta como una pestaña de gspread, sin red.

    Guarda las llamadas en orden: varias pruebas de abajo miran el
    ORDEN, porque el bug era de orden y no de contenido.
    """

    def __init__(self, filas=None, col_count=None, falla_update=False):
        self.filas = [list(f) for f in (filas or [])]
        self.col_count = (len(almacen_sheets.COLUMNAS)
                          if col_count is None else col_count)
        self.falla_update = falla_update
        self.llamadas = []

    def get_all_values(self):
        self.llamadas.append("get_all_values")
        return [list(f) for f in self.filas]

    def update(self, values=None, range_name=None):
        self.llamadas.append("update")
        if self.falla_update:
            raise RuntimeError("Google contesto 503")
        for i, fila in enumerate(values):
            if i < len(self.filas):
                self.filas[i] = list(fila)
            else:
                self.filas.append(list(fila))

    def clear(self):
        # Esta en la falsa a proposito: si alguien vuelve a usarla, la
        # prueba del orden lo ve.
        self.llamadas.append("clear")
        self.filas = []

    def batch_clear(self, rangos):
        self.llamadas.append("batch_clear")
        for rango in rangos:
            desde, hasta = rango.split(":")
            primera = int(re.sub(r"\D", "", desde))
            ultima = int(re.sub(r"\D", "", hasta))
            for i in range(primera - 1, min(ultima, len(self.filas))):
                self.filas[i] = [""] * self.col_count
        # En una hoja de verdad las filas vacias del final no son filas.
        while self.filas and not any(self.filas[-1]):
            self.filas.pop()

    def add_cols(self, n):
        self.llamadas.append("add_cols")
        self.col_count += n


ENCABEZADO = list(almacen_sheets.COLUMNAS)


def fila_de(pid, nombre="Super Uno", canton="Palmares", estado="enviado",
            notas=""):
    """Una fila con la forma exacta de COLUMNAS."""
    valores = {"nombre": nombre, "canton": canton, "estado": estado,
               "enviado": "2026-11-01", "mensaje": "tal cual",
               "notas": notas, "place_id": pid}
    return [valores[c] for c in almacen_sheets.COLUMNAS]


@pytest.fixture
def pestana(monkeypatch):
    """almacen_sheets apuntando a una pestaña falsa y un respaldo falso.

    Reemplaza conectar() y _pestana_respaldo(), que son los dos unicos
    lugares por donde este modulo llega a Google.
    """
    hoja = PestanaFalsa([ENCABEZADO, fila_de("pid1")])
    hoja.respaldo = PestanaFalsa()
    monkeypatch.setattr(almacen_sheets, "conectar", lambda: hoja)
    monkeypatch.setattr(almacen_sheets, "_pestana_respaldo",
                        lambda: hoja.respaldo)
    return hoja


# ─────────────────────────────────────────────────────────────────
# 1a. el orden de escritura
# ─────────────────────────────────────────────────────────────────

def test_no_se_vacia_la_hoja_antes_de_escribirla(pestana):
    """El bug exacto: clear() primero y update() despues."""
    almacen_sheets.escribir({"pid1": {"estado": "interesado"}})

    assert "clear" not in pestana.llamadas, (
        "se llamo clear(). Son dos llamadas a Google: si la segunda "
        "falla, la pestaña queda vacia."
    )


def test_se_escribe_antes_de_recortar(pestana):
    """El orden es lo que hace que el peor caso sea recuperable."""
    almacen_sheets.escribir({"pid1": {"estado": "no"}})

    assert "update" in pestana.llamadas
    if "batch_clear" in pestana.llamadas:
        assert (pestana.llamadas.index("update")
                < pestana.llamadas.index("batch_clear"))


def test_un_update_que_falla_no_pierde_lo_que_habia(monkeypatch):
    """La prueba que el hallazgo 1a pedia: update() falla."""
    previas = [ENCABEZADO, fila_de("pid1", nombre="Super Uno",
                                   estado="interesado")]
    hoja = PestanaFalsa(previas, falla_update=True)
    monkeypatch.setattr(almacen_sheets, "conectar", lambda: hoja)
    monkeypatch.setattr(almacen_sheets, "_pestana_respaldo",
                        lambda: PestanaFalsa())

    with pytest.raises(RuntimeError):
        almacen_sheets.escribir({"pid2": {"estado": "no"}})

    assert hoja.filas == previas, "la escritura fallida cambio la hoja"
    assert almacen_sheets.desde_filas(hoja.filas), "la hoja quedo vacia"


def _llamadas_a_clear(ruta):
    """Las lineas donde el modulo llama a algo .clear().

    Se usa ast y no una busqueda de texto para que un comentario o un
    docstring que mencione el bug no cuente como el bug.
    """
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    return [n.lineno for n in ast.walk(arbol)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "clear"]


def test_ningun_modulo_de_la_hoja_llama_a_clear():
    """Candado sobre la CLASE de error, no sobre el caso que paso.

    La leccion del 07/10 fue que una prueba escrita para el archivo
    donde paso el bug no cubre la clase. Esta recorre los dos modulos
    que escriben en Google, y fallaria igual si el patron apareciera en
    el otro.
    """
    for nombre in ("almacen_sheets.py", "a_sheets.py"):
        lineas = _llamadas_a_clear(RAIZ / nombre)
        assert not lineas, (
            f"{nombre} llama a .clear() en la linea {lineas}. "
            f"Usar escribir_seguro(): se escribe y despues se recorta."
        )


def test_el_orden_seguro_vive_en_un_solo_lugar():
    """Una funcion copiada se desincroniza. Van cuatro veces aca."""
    import a_sheets

    assert almacen_sheets.escribir_seguro is a_sheets.escribir_seguro


def test_el_sobrante_se_recorta_cuando_quedan_menos_filas(monkeypatch):
    """Sin recorte, una fila borrada volveria a aparecer al leer."""
    hoja = PestanaFalsa([ENCABEZADO, fila_de("pid1"), fila_de("pid2"),
                         fila_de("pid3")])
    monkeypatch.setattr(almacen_sheets, "conectar", lambda: hoja)
    monkeypatch.setattr(almacen_sheets, "_pestana_respaldo",
                        lambda: PestanaFalsa())

    # escribir_seguro() directo: escribir() fusiona a proposito, asi que
    # por ahi nunca se encogen las filas.
    almacen_sheets.escribir_seguro(hoja, [ENCABEZADO, fila_de("pid1")], 4)

    assert len(hoja.filas) == 2
    assert list(almacen_sheets.desde_filas(hoja.filas)) == ["pid1"]


# ─────────────────────────────────────────────────────────────────
# el respaldo
# ─────────────────────────────────────────────────────────────────

def test_lo_que_habia_se_respalda_antes_de_escribir_encima(pestana):
    almacen_sheets.escribir({"pid9": {"estado": "no"}})

    respaldadas = almacen_sheets.desde_filas(pestana.respaldo.filas)
    assert "pid1" in respaldadas, (
        "el respaldo no tiene lo que la hoja tenia antes")


def test_un_respaldo_que_falla_no_impide_guardar(pestana, monkeypatch):
    """La red de seguridad no es el arnes.

    escribir() ya no puede vaciar la pestaña, asi que negarse a guardar
    porque el respaldo fallo dejaria a la persona sin poder anotar sin
    ganar nada.
    """
    def explota():
        raise RuntimeError("sin permiso para crear pestañas")

    monkeypatch.setattr(almacen_sheets, "_pestana_respaldo", explota)

    almacen_sheets.escribir({"pid1": {"estado": "interesado"}})

    assert almacen_sheets.desde_filas(pestana.filas)["pid1"]["estado"] \
        == "interesado"


# ─────────────────────────────────────────────────────────────────
# dos guardados simultaneos
# ─────────────────────────────────────────────────────────────────

def test_dos_guardados_simultaneos_no_se_pisan(pestana):
    """El caso de los dos ruteros.

        9:00  A y B abren el app, los dos ven pid1
        9:05  A anota pid2 y guarda
        9:10  B anota pid3 y guarda, con la memoria de las 9:00

    Sin fusionar, el guardado de B borraba lo de A sin un solo error.
    """
    memoria_comun = almacen_sheets.desde_filas(pestana.filas)

    de_a = dict(memoria_comun)
    de_a["pid2"] = {"estado": "interesado", "nombre": "Super Dos"}
    almacen_sheets.escribir(de_a)

    de_b = dict(memoria_comun)          # B no sabe de pid2
    de_b["pid3"] = {"estado": "no", "nombre": "Super Tres"}
    almacen_sheets.escribir(de_b)

    quedaron = almacen_sheets.desde_filas(pestana.filas)
    assert set(quedaron) == {"pid1", "pid2", "pid3"}, (
        f"se perdio alguna anotacion: {sorted(quedaron)}")


def test_el_que_guarda_gana_sobre_su_propia_fila(pestana):
    """Fusionar no puede significar que un cambio no entre."""
    almacen_sheets.escribir({"pid1": {"estado": "interesado",
                                      "notas": "pidió precios"}})

    quedo = almacen_sheets.desde_filas(pestana.filas)["pid1"]
    assert quedo["estado"] == "interesado"
    assert quedo["notas"] == "pidió precios"


def test_fusionar_conserva_lo_que_el_que_guarda_no_conocia():
    en_la_hoja = {"pid1": {"estado": "enviado"}}
    nuevos = {"pid2": {"estado": "no"}}

    assert almacen_sheets.fusionar(en_la_hoja, nuevos) == {
        "pid1": {"estado": "enviado"},
        "pid2": {"estado": "no"},
    }


# ─────────────────────────────────────────────────────────────────
# 1b. Sheets caido
# ─────────────────────────────────────────────────────────────────

def _que_falle():
    raise RuntimeError("Google no responde")


@pytest.fixture
def sin_backend():
    """Deja registro.BACKEND como estaba.

    Es global: una prueba que lo deje puesto hace escribir a las que
    siguen en un almacen que no eligieron.
    """
    yield
    registro.usar(None)


def test_si_la_hoja_no_responde_queda_en_solo_lectura(monkeypatch,
                                                      sin_backend):
    """El hallazgo 1b: antes caia al disco local, que alla se borra."""
    import inicio

    monkeypatch.setattr(inicio, "_hoja_conectada", _que_falle)
    monkeypatch.setattr(inicio, "modo_desarrollo", lambda: False)
    monkeypatch.setattr(inicio, "_fuente_para_leer", lambda: None)

    assert inicio.elegir_almacen() == inicio.SOLO_LECTURA
    assert not registro.se_puede_guardar()


def test_en_solo_lectura_guardar_lanza_y_no_escribe_en_disco(
        monkeypatch, tmp_path, sin_backend):
    import inicio

    monkeypatch.setattr(inicio, "_hoja_conectada", _que_falle)
    monkeypatch.setattr(inicio, "modo_desarrollo", lambda: False)
    monkeypatch.setattr(inicio, "_fuente_para_leer", lambda: None)
    inicio.elegir_almacen()

    ruta = tmp_path / "no_deberia_existir.json"
    with pytest.raises(registro.SoloLectura):
        registro.guardar({"pid1": {"estado": "enviado"}}, ruta)

    assert not ruta.exists(), (
        "escribio en el disco del servidor. Alla se borra al reiniciar.")


def test_en_solo_lectura_todavia_se_puede_leer(monkeypatch, sin_backend):
    """Sin poder anotar, la lista sigue sirviendo para salir a la ruta."""
    import inicio

    class FuenteQueResponde:
        def leer(self):
            return {"pid1": {"estado": "enviado"}}

    monkeypatch.setattr(inicio, "_hoja_conectada", _que_falle)
    monkeypatch.setattr(inicio, "modo_desarrollo", lambda: False)
    monkeypatch.setattr(inicio, "_fuente_para_leer", FuenteQueResponde)
    inicio.elegir_almacen()

    assert registro.cargar() == {"pid1": {"estado": "enviado"}}


def test_una_lectura_que_falla_no_rompe_el_app(monkeypatch, sin_backend):
    import inicio

    class FuenteCaida:
        def leer(self):
            raise RuntimeError("Google no responde")

    monkeypatch.setattr(inicio, "_hoja_conectada", _que_falle)
    monkeypatch.setattr(inicio, "modo_desarrollo", lambda: False)
    monkeypatch.setattr(inicio, "_fuente_para_leer", FuenteCaida)
    inicio.elegir_almacen()

    assert registro.cargar() == {}


def test_el_disco_local_solo_en_modo_desarrollo(monkeypatch, sin_backend):
    """Hay que pedirlo escribiendolo. Antes era el camino por defecto."""
    import inicio

    monkeypatch.setattr(inicio, "_hoja_conectada", _que_falle)
    monkeypatch.setattr(inicio, "modo_desarrollo", lambda: True)

    assert inicio.elegir_almacen() == inicio.LOCAL_DESARROLLO
    assert registro.BACKEND is None
    assert registro.se_puede_guardar()


def test_la_variable_de_entorno_habilita_el_modo_desarrollo(monkeypatch):
    import inicio

    monkeypatch.setenv("EMBUTIDOS_MODO", "desarrollo")
    assert inicio.modo_desarrollo()

    monkeypatch.setenv("EMBUTIDOS_MODO", "produccion")
    assert not inicio.modo_desarrollo()

    monkeypatch.delenv("EMBUTIDOS_MODO", raising=False)
    assert not inicio.modo_desarrollo()


def test_un_fallo_de_conexion_no_queda_cacheado(monkeypatch, sin_backend):
    """La otra mitad del hallazgo 1b: se reintenta.

    Antes el False quedaba guardado con @st.cache_resource, asi que un
    corte de diez segundos al arrancar condenaba toda la vida del
    servidor a escribir en un disco efimero.
    """
    import inicio

    class HojaQueVuelve:
        NOMBRE = "hoja que volvio"
        intentos = 0

        def leer(self):
            return {}

        def escribir(self, registros):
            pass

    def primero_falla():
        HojaQueVuelve.intentos += 1
        if HojaQueVuelve.intentos == 1:
            raise RuntimeError("Google no responde")
        return HojaQueVuelve()

    monkeypatch.setattr(inicio, "_hoja_conectada", primero_falla)
    monkeypatch.setattr(inicio, "modo_desarrollo", lambda: False)
    monkeypatch.setattr(inicio, "_fuente_para_leer", lambda: None)

    assert inicio.elegir_almacen() == inicio.SOLO_LECTURA
    assert inicio.elegir_almacen() == inicio.EN_LA_HOJA_OK, (
        "no reintento: el fallo quedo cacheado")


# ─────────────────────────────────────────────────────────────────
# el aviso se tiene que ver
# ─────────────────────────────────────────────────────────────────

def test_el_solo_lectura_avisa_como_error_y_no_como_linea_gris():
    """Un aviso gris para "esto NO se guarda" es lo mismo que no avisar."""
    import inicio

    severidad, texto = inicio.texto_de_aviso(inicio.SOLO_LECTURA)
    assert severidad == "error"
    assert "no se puede guardar" in texto.lower()


def test_el_modo_desarrollo_avisa_que_el_disco_se_borra():
    import inicio

    severidad, texto = inicio.texto_de_aviso(inicio.LOCAL_DESARROLLO)
    assert severidad == "aviso"
    assert "pierden" in texto.lower()


def test_con_la_hoja_al_dia_no_se_avisa_nada():
    """Un aviso que sale siempre se deja de leer."""
    import inicio

    assert inicio.texto_de_aviso(inicio.EN_LA_HOJA_OK) is None

def test_el_candado_contra_google_cierra():
    """Que el candado de conftest.py sirva, probado y no supuesto.

    Un candado que no se verifica es un candado que no se sabe si
    cierra: el mismo problema que el patron "ampm" que estuvo años en
    la lista de cadenas sin coincidir nunca.

    Esto llama a conectar() de verdad. Si el candado estuviera mal
    puesto, en esta maquina se conectaria a la hoja del papa -- y esta
    prueba se pondria verde igual, que es justamente lo que no se
    quiere. Por eso se exige la excepcion.
    """
    with pytest.raises(AssertionError, match="hoja de Google de verdad"):
        almacen_sheets.conectar()
