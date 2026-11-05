"""Los dos lugares que fallaban ABIERTO.

Origen: revision externa del repo publico, 03/11/2026.

Este proyecto falla cerrado en todo lo demas. acceso.py sin clave no
abre. mascara.py sin registro borra los atributos en vez de dejarlos
pasar. es_celular() ante la duda no promete un canal que no existe.
`buscar` escribe a temporal y renombra. El validador nunca aprueba por
defecto.

Estos dos eran la excepcion:

    2a. pantallas/Mensajes.py aceptaba cualquier valor de validacion
        menos "revisar", asi que un campo ausente o editado a mano
        pasaba el unico filtro que decide si un mensaje sale.
    2b. pantallas/Rutas.py metia el texto de Google Places en HTML con
        unsafe_allow_html=True, sin escapar. La frontera de este
        proyecto dice que el texto de terceros no puede dar ordenes;
        esto era la MISMA vulnerabilidad en otro canal -- texto de
        terceros llegando a un motor de renderizado en vez de a un
        modelo.

Correr con:  python -m pytest tests/test_falla_cerrado.py -v
"""

import ast
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from reglas import (VALIDACION_OK, VALIDACION_REVISAR,  # noqa: E402
                    como_html, se_puede_mandar)


# ═══════════════════════════════════════════════════════════════
# 2a. se_puede_mandar() exige "ok"
# ═══════════════════════════════════════════════════════════════

CELULAR = "88887777"
FIJO = "24501234"


def negocio(**cambios):
    base = {"mensaje": "Buenas. Le escribo de la fábrica...",
            "validacion": VALIDACION_OK,
            "telefono": CELULAR}
    base.update(cambios)
    return base


def test_un_mensaje_validado_con_celular_se_puede_mandar():
    """El caso que DEBE pasar.

    Va primero a proposito: un banco de pruebas que solo tiene casos
    que deben fallar premia al filtro que rechaza todo. La leccion del
    22/10, aplicada aca.
    """
    assert se_puede_mandar(negocio())


def test_sin_el_campo_validacion_no_se_manda():
    """El hallazgo exacto: `!= "revisar"` dejaba pasar el campo ausente.

    Es el caso de un JSON viejo, de uno editado a mano, o de un
    registro a medio escribir.
    """
    sin_campo = negocio()
    del sin_campo["validacion"]

    assert not se_puede_mandar(sin_campo)


def test_un_valor_de_validacion_desconocido_no_se_manda():
    """Lo que escribiria una version futura del validador.

    Si manana alguien agrega "revisar_a_mano" o "pendiente", el filtro
    viejo lo habria tratado como aprobado.
    """
    for valor in ("pendiente", "revisar_a_mano", "OK", "ok ", "si",
                  "aprobado", "1", "true"):
        assert not se_puede_mandar(negocio(validacion=valor)), (
            f"paso con validacion={valor!r}")


def test_un_validacion_en_none_no_se_manda():
    """El pipeline escribe None cuando no hubo mensaje que validar."""
    assert not se_puede_mandar(negocio(validacion=None))


def test_lo_marcado_para_revisar_no_se_manda():
    assert not se_puede_mandar(negocio(validacion=VALIDACION_REVISAR))


def test_sin_mensaje_no_se_manda():
    assert not se_puede_mandar(negocio(mensaje=""))
    assert not se_puede_mandar(negocio(mensaje=None))


def test_a_un_fijo_no_se_le_manda_whatsapp():
    assert not se_puede_mandar(negocio(telefono=FIJO))


def test_sin_telefono_no_se_manda():
    assert not se_puede_mandar(negocio(telefono=None))


def test_un_negocio_vacio_no_se_manda():
    """El registro vacio que menciona la revision."""
    assert not se_puede_mandar({})


# ═══════════════════════════════════════════════════════════════
# 2b. como_html() cierra el canal del renderizado
# ═══════════════════════════════════════════════════════════════

def test_un_nombre_con_html_se_muestra_y_no_se_ejecuta():
    """El caso que pidio la revision: un negocio con HTML en el nombre.

    Google Places devuelve el nombre tal como lo registro un tercero.
    """
    salida = como_html("Mini Súper <script>alert(1)</script>")

    assert "<script>" not in salida
    assert "&lt;script&gt;" in salida
    # No censura: el texto se sigue viendo, escrito tal cual.
    assert "script" in salida
    assert "Mini Súper" in salida


def test_se_escapan_las_comillas_de_los_atributos():
    """Sin esto se puede salir de un atributo sin abrir una etiqueta."""
    salida = como_html('X" onmouseover="alert(1)')

    assert '"' not in salida
    assert "&quot;" in salida


def test_un_apostrofo_normal_no_rompe_el_nombre():
    """D'Feria Ejemplo Dos es un cliente real."""
    salida = como_html("D'Feria Ejemplo Dos")

    assert "'" not in salida
    assert "&#x27;" in salida


def test_se_aplastan_los_caracteres_de_control():
    """Mismo criterio que como_dato(), incluido U+202E.

    U+202E invierte visualmente el texto: haria que la tarjeta no diga
    lo que parece decir, y el rutero decide mirando la tarjeta.
    """
    assert como_html("Super ‮X") == "Super X"
    assert "\n" not in como_html("Super\nFalso")
    assert "\t" not in como_html("Super\tFalso")


def test_un_nombre_normal_pasa_sin_cambios():
    """Si escapar deformara los nombres de verdad, nadie lo dejaria."""
    assert como_html("Supermercado Tres SR") == \
        "Supermercado Tres SR"
    assert como_html("Mega Súper · Poás") == "Mega Súper · Poás"


def test_none_y_vacio_no_rompen():
    assert como_html(None) == ""
    assert como_html("") == ""
    assert como_html(0) == "0"


def test_escapar_dos_veces_no_es_lo_mismo_que_escapar_una():
    """Deja dicho que como_html() NO es idempotente.

    No es un defecto: es la razon por la que se aplica una sola vez, en
    el borde, y no en el camino. Si alguien lo agrega dos veces, la
    tarjeta va a mostrar &amp;lt; y se va a ver.
    """
    assert como_html(como_html("<b>")) != como_html("<b>")


# ─────────────────────────────────────────────────────────────────
# el candado: nada entra a HTML sin pasar por como_html()
# ─────────────────────────────────────────────────────────────────

def _interpolaciones_sin_escapar(ruta):
    """Interpolaciones que entran a unsafe_allow_html sin como_html().

    Se recorre el arbol y no el texto para que valga sobre cualquier
    forma de escribir la llamada, no sobre las lineas que hay hoy.

    Se acepta una interpolacion si:

      - en algun lugar de su subarbol llama a como_html(); o
      - no toca datos, o sea que no tiene ningun Subscript (`n["x"]`)
        ni ningun Attribute (`zonas.canal(n)`). Asi `{i}`,
        `{len(lista)}` y `{len(lista) - tope}` pasan, que es lo que
        son: numeros nuestros.
    """
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    malas = []

    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        inseguro = any(k.arg == "unsafe_allow_html"
                       and getattr(k.value, "value", False) is True
                       for k in nodo.keywords)
        if not inseguro:
            continue

        for arg in nodo.args:
            for trozo in ast.walk(arg):
                if not isinstance(trozo, ast.FormattedValue):
                    continue
                sub = list(ast.walk(trozo.value))
                escapado = any(
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "como_html" for n in sub)
                toca_datos = any(
                    isinstance(n, (ast.Subscript, ast.Attribute))
                    for n in sub)
                if not escapado and toca_datos:
                    malas.append((trozo.lineno,
                                  ast.unparse(trozo.value)))
    return malas


@pytest.mark.parametrize("archivo", ["pantallas/Rutas.py",
                                     "pantallas/Mensajes.py",
                                     "inicio.py", "app.py"])
def test_nada_entra_a_html_sin_escapar(archivo):
    """Candado sobre la clase de error, no sobre el caso que paso.

    Recorre los cuatro archivos que usan unsafe_allow_html, no solo
    Rutas.py, donde se encontro. La leccion del 07/10: una prueba
    escrita para el archivo del bug no cubre la clase.
    """
    ruta = RAIZ / archivo
    if not ruta.exists():
        pytest.skip(f"{archivo} no esta en esta carpeta")

    malas = _interpolaciones_sin_escapar(ruta)

    assert not malas, (
        f"{archivo} mete datos en HTML sin como_html(): {malas}")


def test_el_candado_detecta_el_bug_original():
    """Que el candado sirva, probado contra el codigo que tenia el bug.

    Un candado que no se verifica es un candado que no se sabe si
    cierra -- el mismo problema que el patron "ampm" muerto en la
    lista de cadenas.
    """
    import tempfile

    con_bug = (
        "import streamlit as st\n"
        "def tarjeta(i, n):\n"
        "    st.markdown(f'<p>{n[\"nombre\"]}</p>',"
        " unsafe_allow_html=True)\n"
    )
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "con_bug.py"
        ruta.write_text(con_bug, encoding="utf-8")

        assert _interpolaciones_sin_escapar(ruta), (
            "el candado no detecta la interpolacion sin escapar")
