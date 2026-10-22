"""Tracing opcional: que se pueda apagar, y que no se pueda desenmascarar.

Punto 16 (21/10/2026). Dos propiedades que no se pueden verificar
mirando el codigo dentro de seis meses:

  - sin llaves en el .env, el pipeline corre igual y no intenta nada
  - con llaves, la mascara va puesta y no hay forma de pedir lo
    contrario

La segunda es la que importa. Una mascara opcional es una mascara que
alguien apaga "un momentito para depurar".

Correr con:  python -m pytest tests/test_trazas.py -v
"""

import inspect
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import trazas                                                   # noqa: E402


def cuerpo_de(archivo, funcion):
    """El codigo de una funcion, SIN comentarios.

    Sin quitarlos, una prueba que busca una palabra encuentra el
    comentario que explica por que esa palabra no deberia estar. Ya
    paso en verificar_estructura.py, que se acusaba a si mismo.
    """
    fuente = (RAIZ / archivo).read_text(encoding="utf-8")
    cuerpo = fuente.split(f"def {funcion}(")[1].split("\ndef ")[0]
    return "\n".join(linea.split("#")[0] for linea in cuerpo.splitlines())


def sin_llaves(monkeypatch):
    for llave in trazas.LLAVES:
        monkeypatch.delenv(llave, raising=False)


def con_llaves(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-prueba")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-prueba")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://ejemplo.invalido")


# ─────────────────────────────────────────────────────────────────
# Apagado
# ─────────────────────────────────────────────────────────────────

def test_sin_llaves_no_hay_trazas(monkeypatch):
    sin_llaves(monkeypatch)
    assert isinstance(trazas.preparar(avisar=False), trazas.SinTrazas)


def test_sin_trazas_el_config_va_vacio(monkeypatch):
    """Lo que se le pasa a invoke() tiene que ser inofensivo."""
    sin_llaves(monkeypatch)
    assert trazas.preparar(avisar=False).config() == {}


def test_sin_trazas_cerrar_no_revienta(monkeypatch):
    sin_llaves(monkeypatch)
    trazas.preparar(avisar=False).cerrar()


def test_con_una_sola_llave_tampoco_traza(monkeypatch):
    """Media configuracion es no configuracion."""
    sin_llaves(monkeypatch)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-prueba")
    assert isinstance(trazas.preparar(avisar=False), trazas.SinTrazas)


def test_un_fallo_al_conectar_no_mata_la_corrida(monkeypatch):
    """Una corrida de grafo.py cuesta dinero. Que el tracing no
    conecte no puede ser motivo para perderla."""
    con_llaves(monkeypatch)

    import trazas as modulo
    original = modulo.preparar

    def explotar(*a, **k):
        raise RuntimeError("sin red")

    monkeypatch.setattr("langfuse.Langfuse", explotar, raising=False)
    assert isinstance(original(avisar=False), trazas.SinTrazas)


# ─────────────────────────────────────────────────────────────────
# La mascara no es opcional
# ─────────────────────────────────────────────────────────────────

def test_el_cliente_se_construye_con_la_mascara():
    """Si alguien saca ese argumento, las trazas salen enteras y nada
    falla visiblemente. Por eso hay una prueba sobre el texto."""
    fuente = inspect.getsource(trazas.preparar)
    assert "mask_otel_spans=mascara.enmascarar" in fuente


def test_no_hay_manera_de_pedir_trazas_sin_mascara():
    """preparar() solo acepta 'avisar'. El dia que alguien agregue un
    parametro para saltarse la mascara, esto se pone rojo."""
    parametros = set(inspect.signature(trazas.preparar).parameters)
    assert parametros == {"avisar"}


def test_el_cliente_va_antes_que_el_handler():
    """El handler toma el cliente que ya exista. Si se crea primero,
    agarra uno sin hook y la mascara queda decorativa, sin un solo
    error en pantalla. Lo descubrio sonda_langfuse.py."""
    fuente = inspect.getsource(trazas.preparar)
    assert fuente.index("Langfuse(") < fuente.index("CallbackHandler(")


# ─────────────────────────────────────────────────────────────────
# Lo que el grafo sabe de Langfuse
# ─────────────────────────────────────────────────────────────────

def test_el_grafo_no_nombra_a_langfuse():
    """El grafo pide un config a trazas.py y no sabe que hay detras.
    Esa ignorancia es lo que deja cambiar de herramienta sin tocarlo."""
    cuerpo = cuerpo_de("grafo.py", "correr")
    assert "langfuse" not in cuerpo.lower()
    assert "trazador.config()" in cuerpo


def test_el_grafo_cierra_el_tracing():
    """Sin flush() el ultimo lote puede quedarse sin salir, y la
    corrida que mas interesa es justamente la ultima."""
    assert "trazador.cerrar()" in cuerpo_de("grafo.py", "correr")


def test_el_grafo_registra_antes_de_invocar():
    """Si recordar() corriera despues del invoke, la mascara llegaria
    tarde: el lote ya habria salido con los nombres adentro."""
    cuerpo = cuerpo_de("grafo.py", "correr")
    assert cuerpo.index("mascara.recordar(") < cuerpo.index("grafo.invoke(")
