"""Ninguna prueba toca la hoja de Google real. Lo hace cumplir el codigo.

ORIGEN (03/11/2026), de la regla de seguridad de la revision externa:

> credenciales.json da permiso de escritura. Todo lo de Sheets se
> prueba con un falso.

Y en esta maquina `credenciales.json` **existe**. O sea que una prueba
mal escrita no falla: se conecta a la hoja del papa y escribe. Si la
prueba es de `escribir()`, lo que escribe es la pestaña entera.

**Por que un candado y no la disciplina.** Hoy todas las pruebas usan
falsos. La que se escriba el mes que viene puede olvidarse de un
monkeypatch, y el sintoma seria "la prueba pasa" -- que es exactamente
el patron de error que este proyecto ya repitio cinco veces: el codigo
corrio, no lanzo excepcion, y el dato quedo mal. Salvo que aca el dato
es el unico que no se puede regenerar.

Falla cerrada, como el resto del proyecto: no hay parametro para pedir
una conexion de verdad. Si alguna vez hace falta probar contra Google,
se hace a mano y fuera de pytest.
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


class ConexionDeVerdad(AssertionError):
    """Una prueba intento conectarse a Google."""


@pytest.fixture(autouse=True)
def nada_de_google(monkeypatch):
    """Revienta si una prueba llega a autenticarse contra Google.

    Se parchan los dos puntos por donde el proyecto entra: gspread, que
    es quien se conecta, y la carga de credenciales de cada modulo.
    """
    def explota(*a, **k):
        raise ConexionDeVerdad(
            "Esta prueba intento conectarse a la hoja de Google de "
            "verdad. credenciales.json da permiso de ESCRITURA: usa un "
            "falso (ver PestanaFalsa en tests/test_escritura_segura.py)."
        )

    try:
        import gspread

        monkeypatch.setattr(gspread, "authorize", explota)
        monkeypatch.setattr(gspread, "service_account", explota,
                            raising=False)
    except ImportError:
        # Sin gspread instalado no hay nada que bloquear.
        pass

    import almacen_sheets

    monkeypatch.setattr(almacen_sheets, "_credenciales", explota)
    # El modulo cachea la pestaña en _hoja. Si una prueba anterior la
    # dejo puesta, conectar() la devolveria sin pasar por gspread.
    monkeypatch.setattr(almacen_sheets, "_hoja", None)
    monkeypatch.setattr(almacen_sheets, "_libro", None)

    import a_sheets

    if hasattr(a_sheets, "conectar"):
        monkeypatch.setattr(a_sheets, "conectar", explota)
