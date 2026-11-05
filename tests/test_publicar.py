"""publicar.py no se publica a si mismo.

ORIGEN (05/11/2026), de la revision externa.

`publicar.py` construye la copia publica reemplazando los nombres
reales por genericos. Su tabla `REEMPLAZOS` es el **mapa inverso** de
todo lo que se oculto, en las dos direcciones:

    "Supermercado Ejemplo Uno" -> "Supermercado Ejemplo Uno"

Con ese archivo, deshacer la anonimizacion no es un ataque: es leer un
diccionario. El nombre de la fabrica, los cuatro clientes actuales, los
proveedores y los negocios de los casos de prueba quedan al descubierto
de una sola lectura.

Estuvo siempre fuera de `NUCLEO`, con un comentario que lo explicaba, y
lo encontro el propio script revisandose a si mismo. **Pero "no estar en
una lista" depende de que nadie lo agregue por error.** Esto es el
candado, y es el patron que este proyecto ya aplico cinco veces: lo que
puede ser una prueba, debe ser una prueba.

POR QUE SE SALTAN EN LA COPIA PUBLICA

Estas pruebas importan `publicar.py`, que por definicion no esta alla.
Se saltan con su motivo escrito -- igual que las dos de la mascara que
necesitan `prospectos_crudo.json`. Que se salten **es** el resultado
que se busca: si alguna corriera en la copia publica, seria porque el
archivo viajo.

Correr con:  python -m pytest tests/test_publicar.py -v
"""

import ast
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# No es skipif sobre el import: importar un modulo ausente revienta
# antes de llegar al marcador.
publicar = pytest.importorskip(
    "publicar",
    reason="publicar.py no esta en esta copia -- que es justo lo correcto")


# ─────────────────────────────────────────────────────────────────
# el archivo
# ─────────────────────────────────────────────────────────────────

def test_no_se_copia_a_si_mismo():
    """La verificacion que pidio la revision."""
    copiados = publicar.archivos_a_copiar()

    assert "publicar.py" not in copiados, (
        "publicar.py quedo en la lista de archivos a copiar. Su tabla "
        "REEMPLAZOS es el mapa inverso de la anonimizacion."
    )


def test_esta_en_la_lista_de_jamas():
    """No alcanza con que FALTE de NUCLEO: tiene que estar prohibido.

    Faltar de una lista depende de que nadie lo agregue. Estar en JAMAS
    hace que revisar() rechace la construccion entera.
    """
    assert "publicar.py" in publicar.JAMAS


def test_ningun_patron_lo_arrastra():
    """NUCLEO es explicito, pero PATRONES usa globs.

    Un glob mas amplio manana -- "*.py", por ejemplo -- lo arrastraria
    sin que nadie toque NUCLEO.
    """
    for patron in publicar.PATRONES:
        arrastrados = [p.name for p in publicar.RAIZ.glob(patron)]
        assert "publicar.py" not in arrastrados, (
            f"el patron {patron!r} arrastra publicar.py")


def test_el_revisor_lo_detectaria_si_apareciera(tmp_path):
    """Que el candado cierre, probado y no supuesto.

    Un candado que no se verifica es un candado que no se sabe si
    cierra: el mismo problema que el patron "ampm" que estuvo meses en
    la lista de cadenas sin coincidir nunca.
    """
    # El contenido da igual: revisar() lo rechaza por el NOMBRE, que
    # es lo que hace que el candado no dependa de leer el archivo.
    (tmp_path / "publicar.py").write_text(
        "# un publicar.py que se colo", encoding="utf-8")

    fugas = publicar.revisar(tmp_path)

    assert any("publicar.py" in str(f) for f in fugas), (
        "revisar() no detecto publicar.py en la carpeta construida")


# ─────────────────────────────────────────────────────────────────
# la tabla, que es el riesgo de verdad
# ─────────────────────────────────────────────────────────────────

def _nombres_asignados(ruta):
    """Los nombres que el modulo ASIGNA, no los que menciona.

    Se recorre el arbol y no el texto porque una busqueda de texto no
    distingue una definicion de una mencion. La primera version de esta
    prueba buscaba la cadena "PROHIBIDAS = " y se puso roja por dos
    falsos positivos: este mismo archivo, y tests/test_reglas.py, que
    tiene esa cadena dentro de su propia lista de candados.

    Ademas asi "PROHIBIDAS" y "PROHIBIDAS_SIEMPRE" son nombres
    distintos, que es lo correcto: el segundo son las palabras que el
    redactor no puede usar y no tiene nada que ver con la
    anonimizacion. La version de texto los confundia.
    """
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    return {objetivo.id
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.Assign)
            for objetivo in nodo.targets
            if isinstance(objetivo, ast.Name)}


def test_ningun_archivo_copiado_define_la_tabla_de_reemplazos():
    """El riesgo es la TABLA, no el nombre del archivo.

    Si manana REEMPLAZOS se mueve a reglas_publicas.py y ese si esta en
    NUCLEO, la prueba de arriba pasaria y la fuga seria la misma. Esta
    mira la clase de error.
    """
    for nombre in publicar.archivos_a_copiar():
        ruta = publicar.RAIZ / nombre
        if ruta.suffix != ".py":
            continue

        definidos = _nombres_asignados(ruta)
        for constante in ("REEMPLAZOS", "PROHIBIDAS",
                          "PATRONES_PROHIBIDOS"):
            assert constante not in definidos, (
                f"{nombre} define {constante}, que es parte del mapa de "
                f"la anonimizacion, y SI se copia."
            )
