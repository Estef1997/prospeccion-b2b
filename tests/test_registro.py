"""El registro de respuestas: lo que hace que el punto 18 sirva.

Adentro de respuestas.json hay una tarde de trabajo que no se puede
rehacer: si se pierde o se corrompe, hay que volver a preguntarle a
veinte negocios que contestaron. Por eso estas pruebas miran sobre todo
la escritura, no la lectura.

No levantan Streamlit. La logica esta en registro.py justamente para
poder probarla sin pantalla.

Correr con:  python -m pytest tests/test_registro.py -v
"""

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import registro                                                 # noqa: E402


# --- el vocabulario se respeta -----------------------------------------

def test_un_estado_inventado_se_rechaza():
    """Sin esto el vocabulario cerrado seria decorativo.

    "contesto", "ni fu ni fa", "nada" entrarian igual y volveriamos al
    texto libre sin darnos cuenta.
    """
    with pytest.raises(ValueError, match="Estado desconocido"):
        registro.anotar({}, "abc", estado="mas o menos")


def test_un_tipo_de_mensaje_inventado_se_rechaza():
    with pytest.raises(ValueError, match="Mensaje desconocido"):
        registro.anotar({}, "abc", mensaje="lo cambie un poquito")


def test_vacio_es_valido():
    """Sin tocar es un estado legitimo, no un error."""
    assert registro.anotar({}, "abc")["abc"]["estado"] == ""


# --- no perder lo anotado ----------------------------------------------

def test_anotar_no_toca_el_registro_original():
    """Devuelve uno nuevo: un error a mitad no deja el registro partido."""
    antes = registro.anotar({}, "abc", estado="interesado")
    despues = registro.anotar(antes, "xyz", estado="no")

    assert "xyz" not in antes
    assert antes["abc"] == despues["abc"]


def test_anotar_dos_veces_el_mismo_negocio_actualiza():
    r = registro.anotar({}, "abc", estado="enviado")
    r = registro.anotar(r, "abc", estado="interesado",
                        notas="pidio precios")

    assert len(r) == 1
    assert r["abc"]["estado"] == "interesado"
    assert r["abc"]["notas"] == "pidio precios"


def test_guardar_y_cargar_da_lo_mismo(tmp_path):
    ruta = tmp_path / "respuestas.json"
    r = registro.anotar({}, "abc", estado="interesado",
                        enviado="2026-10-05", mensaje="tal cual",
                        notas="pregunto por chorizo")

    registro.guardar(r, ruta)
    assert registro.cargar(ruta) == r


def test_cargar_sin_archivo_no_rompe(tmp_path):
    """La primera vez que se abre el app no es un error."""
    assert registro.cargar(tmp_path / "no_existe.json") == {}


def test_guardar_no_deja_el_archivo_a_medias(tmp_path, monkeypatch):
    """Escribe a un temporal y renombra.

    Si el proceso muere a mitad, el archivo viejo queda entero. Se
    verifica que el contenido anterior sobreviva a un fallo.
    """
    ruta = tmp_path / "respuestas.json"
    bueno = registro.anotar({}, "abc", estado="interesado")
    registro.guardar(bueno, ruta)

    def explotar(*a, **k):
        raise OSError("disco lleno")

    monkeypatch.setattr(registro.os, "replace", explotar)
    with pytest.raises(OSError):
        registro.guardar(registro.anotar(bueno, "xyz", estado="no"), ruta)

    assert registro.cargar(ruta) == bueno       # intacto


# --- las cifras que se van a usar en el punto 19 -----------------------

def test_la_tasa_de_respuesta_excluye_los_no_enviados():
    """Si no, veinte filas en blanco harian ver la tasa en 5%."""
    r = {}
    r = registro.anotar(r, "a", estado="interesado")
    r = registro.anotar(r, "b", estado="no")
    r = registro.anotar(r, "c", estado="sin respuesta")
    r = registro.anotar(r, "d")                 # nunca se envio

    s = registro.resumen(r)
    assert s["enviados"] == 3
    assert s["contestaron"] == 2
    assert s["tasa_respuesta"] == pytest.approx(2 / 3)


def test_un_mal_numero_no_cuenta_como_enviado():
    """El negocio nunca recibio nada: no dice nada del mensaje."""
    r = registro.anotar({}, "a", estado="mal numero")
    assert registro.resumen(r)["enviados"] == 0


def test_la_tasa_tal_cual_mide_al_redactor():
    """La cifra que dice si el agente produjo algo usable.

    Dos respuestas de dos mensajes puede verse perfecto, y si los dos
    los reescribio una persona, el redactor no tuvo nada que ver.
    """
    r = {}
    r = registro.anotar(r, "a", estado="interesado", mensaje="editado")
    r = registro.anotar(r, "b", estado="interesado", mensaje="editado")

    s = registro.resumen(r)
    assert s["tasa_respuesta"] == 1.0           # se ve perfecto
    assert s["tasa_tal_cual"] == 0.0            # y no lo es


def test_resumen_vacio_no_divide_entre_cero():
    s = registro.resumen({})
    assert s["tasa_respuesta"] is None
    assert s["enviados"] == 0


# --- el puente a la hoja -----------------------------------------------

def test_para_la_hoja_devuelve_las_cuatro_columnas_en_orden():
    r = registro.anotar({}, "abc", estado="interesado",
                        enviado="2026-10-05", mensaje="tal cual",
                        notas="pidio lista")
    assert registro.para_la_hoja(r, "abc") == [
        "interesado", "2026-10-05", "tal cual", "pidio lista"]


def test_para_la_hoja_de_un_negocio_sin_anotar():
    assert registro.para_la_hoja({}, "abc") == ["", "", "", ""]


# --- donde se guardan las respuestas -----------------------------------
# Origen (08/10/2026): al hospedar el app en Streamlit Cloud se descubrio
# que el disco de alla es efimero -- lo que el app escribe se borra al
# reiniciar el servidor. respuestas.json es el UNICO archivo del proyecto
# que no se puede volver a generar.
#
# Se agrego un backend intercambiable. Estas pruebas usan uno falso, en
# memoria: no tocan Google ni necesitan credenciales.

class HojaFalsa:
    """Se comporta como almacen_sheets, sin red."""

    NOMBRE = "hoja de mentira"

    def __init__(self):
        self.datos = {}
        self.escrituras = 0

    def leer(self):
        return dict(self.datos)

    def escribir(self, registros):
        self.datos = dict(registros)
        self.escrituras += 1


@pytest.fixture
def hoja():
    """Pone el backend y lo quita al terminar.

    El quitarlo importa: registro.BACKEND es global, y si una prueba lo
    deja puesto, las que siguen escribirian en la hoja falsa sin saberlo.
    """
    falsa = HojaFalsa()
    registro.usar(falsa)
    yield falsa
    registro.usar(None)


def test_sin_backend_se_usa_el_archivo():
    """El modo de siempre, en la maquina de desarrollo."""
    assert registro.BACKEND is None
    assert registro.donde() == "respuestas.json"


def test_con_backend_se_escribe_alla_y_no_en_disco(hoja, tmp_path):
    ruta = tmp_path / "no_deberia_existir.json"
    registro.guardar({"abc": {"estado": "enviado"}}, ruta)

    assert hoja.escrituras == 1
    assert not ruta.exists(), "escribio en disco teniendo backend"


def test_lo_guardado_se_vuelve_a_leer_igual(hoja):
    datos = registro.anotar({}, "pid1", estado="interesado",
                            notas="pidió precios")
    registro.guardar(datos)

    assert registro.cargar() == datos


def test_el_app_puede_decir_donde_quedo(hoja):
    """Si el usuario no sabe donde se guardo, no puede confiar."""
    assert registro.donde() == "hoja de mentira"


def test_el_vocabulario_se_valida_igual_con_backend(hoja):
    """La validacion vive en anotar(), no en donde se guarda."""
    with pytest.raises(ValueError):
        registro.anotar({}, "pid1", estado="inventado")


# --- los permisos de Google --------------------------------------------
# Origen (08/10/2026): almacen_sheets tenia su propia lista de permisos,
# con uno solo -- el de Sheets. Al conectar, Google contesto:
#
#     APIError [403]: Request had insufficient authentication scopes
#
# gspread.open() busca la hoja POR NOMBRE, y eso es una consulta a
# Drive, no a Sheets. Hacen falta los dos.
#
# Tercer caso de la misma clase de error esta semana: CONTEXTO_FABRICA
# (02/10), CADENAS en prospecto.py (07/10), y esto.

def test_los_permisos_de_google_vienen_de_un_solo_lugar():
    """`is`, no `==`: una copia igual hoy se desincroniza manana."""
    import a_sheets
    import almacen_sheets

    assert almacen_sheets.ALCANCE is a_sheets.ALCANCES
    assert almacen_sheets.HOJA is a_sheets.HOJA


def test_hacen_falta_los_permisos_de_sheets_y_de_drive():
    """Buscar la hoja por nombre es una consulta a Drive."""
    import almacen_sheets

    permisos = " ".join(almacen_sheets.ALCANCE)
    assert "auth/spreadsheets" in permisos, "falta el permiso de Sheets"
    assert "auth/drive" in permisos, (
        "falta el permiso de Drive: gspread.open() busca por nombre y "
        "eso consulta Drive. Sin esto da 403 insufficient scopes."
    )


# --- la hoja se tiene que poder leer -----------------------------------
# Origen (09/10/2026): la primera fila que el app escribio en la hoja
# decia:
#
#     ChIJ_ejemplo_redactado | enviado | 2026-10-09
#
# Surgio la pregunta: que se supone que hace con eso. Tenia razon.
#
# El argumento para guardar en la hoja y no en una base de datos fue "el
# papa la puede abrir". Una hoja ilegible no cumple eso, y entonces la
# decision de usar la hoja pierde su razon de ser.
#
# Esto no es un bug del codigo: el codigo hacia lo que decia. Es un bug
# de para quien se escribio.

def test_se_guarda_el_nombre_del_negocio():
    r = registro.anotar({}, "pid1", estado="enviado",
                        nombre="Mini Super San Luis", canton="Palmares")
    assert r["pid1"]["nombre"] == "Mini Super San Luis"
    assert r["pid1"]["canton"] == "Palmares"


def test_volver_a_anotar_no_borra_el_nombre():
    """La segunda anotacion suele venir de otra pantalla, sin el nombre.

    Si lo borrara, la fila se volveria ilegible justo cuando pasa algo
    interesante -- que es cuando se vuelve a anotar.
    """
    r = registro.anotar({}, "pid1", estado="enviado",
                        nombre="Mini Super San Luis", canton="Palmares")
    r = registro.anotar(r, "pid1", estado="interesado")

    assert r["pid1"]["estado"] == "interesado"
    assert r["pid1"]["nombre"] == "Mini Super San Luis"


def test_la_hoja_pone_el_nombre_antes_que_el_codigo():
    """Quien abre la hoja lee de izquierda a derecha."""
    import almacen_sheets

    assert almacen_sheets.COLUMNAS[0] == "nombre"
    assert almacen_sheets.COLUMNAS[-1] == "place_id"


def test_la_hoja_escribe_todas_las_columnas_en_orden(hoja):
    r = registro.anotar({}, "pid1", estado="enviado", enviado="2026-10-09",
                        nombre="Mini Super San Luis", canton="Palmares")
    registro.guardar(r)

    assert hoja.datos["pid1"]["nombre"] == "Mini Super San Luis"


def test_el_place_id_sigue_siendo_la_llave():
    """El nombre es para leer; dos negocios pueden llamarse igual.

    Hay 630 'Mini Super' en el archivo. Si la llave fuera el nombre, se
    pisarian entre ellos.
    """
    r = registro.anotar({}, "pid1", estado="enviado",
                        nombre="Mini Super San Luis")
    r = registro.anotar(r, "pid2", estado="no",
                        nombre="Mini Super San Luis")

    assert len(r) == 2
    assert r["pid1"]["estado"] == "enviado"
    assert r["pid2"]["estado"] == "no"


# --- la hoja tiene que caber -------------------------------------------
# Origen (09/10/2026): la pestaña se creo con 5 columnas. Al agregar
# nombre y canton pasaron a 7, y Google recorto las dos ultimas sin
# avisar. Una de ellas era place_id, la llave.
#
# Resultado: escribir() "funcionaba" -- sin excepcion, con la hoja
# actualizada -- y leer() devolvia vacio.
#
# Es el peor tipo de error de este proyecto: silencioso, sobre el unico
# dato que no se puede regenerar.

class HojaAngosta:
    """Una hoja de Google con menos columnas de las que hacen falta."""

    def __init__(self, col_count):
        self.col_count = col_count
        self.agregadas = 0

    def add_cols(self, n):
        self.agregadas = n
        self.col_count += n


def test_se_agregan_columnas_si_la_hoja_quedo_angosta():
    import almacen_sheets

    h = HojaAngosta(5)
    almacen_sheets.ensanchar(h)

    assert h.col_count >= len(almacen_sheets.COLUMNAS)
    assert h.agregadas == len(almacen_sheets.COLUMNAS) - 5


def test_no_se_tocan_las_columnas_si_ya_caben():
    """Ensanchar de mas gasta una llamada a Google en cada guardado."""
    import almacen_sheets

    h = HojaAngosta(len(almacen_sheets.COLUMNAS))
    almacen_sheets.ensanchar(h)

    assert h.agregadas == 0


def test_la_hoja_mas_ancha_de_lo_necesario_se_deja_igual():
    import almacen_sheets

    h = HojaAngosta(26)
    almacen_sheets.ensanchar(h)

    assert h.col_count == 26
    assert h.agregadas == 0