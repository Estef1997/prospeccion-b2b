"""La puerta del app: expulsar al cambiar la clave, y limitar intentos.

Origen: revision externa del repo publico, 03/11/2026. Una sola clave
compartida, sin limite de intentos, y si se cambiaba la clave las
sesiones abiertas seguian adentro.

El tercero era el peor de los tres, porque rompia una promesa que el
propio acceso.py escribia: "si alguien se va hay que cambiarle la clave
a todos". Cambiarla no echaba a nadie -- solo impedia volver a entrar.

No levantan Streamlit. La logica de acceso.py esta separada de pedir()
justamente para poder probarla sin pantalla: una regla que no se puede
probar es una regla que nadie revisa.

Correr con:  python -m pytest tests/test_acceso.py -v
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import acceso                                                   # noqa: E402

CLAVE_VIEJA = "la-clave-de-setiembre"
CLAVE_NUEVA = "la-clave-de-noviembre"


# ═══════════════════════════════════════════════════════════════
# cambiar la clave expulsa a las sesiones abiertas
# ═══════════════════════════════════════════════════════════════

def test_la_sesion_sigue_valida_con_su_propia_clave():
    """El caso que DEBE pasar: nadie se cae sin motivo."""
    estado = {}
    acceso.abrir(estado, acceso.huella(CLAVE_VIEJA))

    assert acceso.sesion_vigente(estado, acceso.huella(CLAVE_VIEJA))


def test_cambiar_la_clave_invalida_la_sesion_abierta():
    """El hallazgo: antes esto seguia adentro.

    Es el caso de "se fue un rutero, cambiale la clave". Si la sesion
    que ya tenia abierta sigue sirviendo, cambiar la clave no hizo
    nada.
    """
    estado = {}
    acceso.abrir(estado, acceso.huella(CLAVE_VIEJA))

    assert not acceso.sesion_vigente(estado, acceso.huella(CLAVE_NUEVA))


def test_una_sesion_que_nunca_entro_no_es_vigente():
    assert not acceso.sesion_vigente({}, acceso.huella(CLAVE_VIEJA))


def test_estar_adentro_sin_huella_no_alcanza():
    """El estado que dejaria una version vieja del app en el navegador.

    Antes la sesion solo guardaba `adentro`. Si eso sobrevive a un
    despliegue, no puede valer como sesion valida.
    """
    assert not acceso.sesion_vigente({"adentro": True},
                                     acceso.huella(CLAVE_VIEJA))


def test_cerrar_saca_la_sesion():
    estado = {}
    acceso.abrir(estado, acceso.huella(CLAVE_VIEJA))
    acceso.cerrar(estado)

    assert not acceso.sesion_vigente(estado, acceso.huella(CLAVE_VIEJA))


def test_la_clave_no_queda_guardada_en_la_sesion():
    """Se guarda la huella, no el secreto.

    Para saber si la clave cambio no hace falta tenerla: alcanza con
    saber que es otra. Guardarla seria tener el secreto en un lugar
    mas, sin ganar nada.
    """
    estado = {}
    acceso.abrir(estado, acceso.huella(CLAVE_VIEJA))

    assert CLAVE_VIEJA not in str(estado)
    assert CLAVE_VIEJA not in str(estado.values())


def test_dos_claves_distintas_dan_huellas_distintas():
    assert acceso.huella(CLAVE_VIEJA) != acceso.huella(CLAVE_NUEVA)


def test_la_misma_clave_da_la_misma_huella():
    """Sin esto, cada recarga expulsaria a todos."""
    assert acceso.huella(CLAVE_VIEJA) == acceso.huella(CLAVE_VIEJA)


# ═══════════════════════════════════════════════════════════════
# limite de intentos
# ═══════════════════════════════════════════════════════════════

AHORA = 1_000_000.0


def test_los_primeros_intentos_no_bloquean():
    """Equivocarse una vez escribiendo en un teclado de telefono pasa."""
    estado = {}

    for _ in range(acceso.MAX_INTENTOS - 1):
        assert acceso.anotar_fallo(estado, AHORA) == 0

    assert acceso.segundos_de_bloqueo(estado, AHORA) == 0


def test_al_pasarse_del_tope_se_bloquea():
    estado = {}

    espera = 0
    for _ in range(acceso.MAX_INTENTOS):
        espera = acceso.anotar_fallo(estado, AHORA)

    assert espera == acceso.ESPERA_SEGUNDOS
    assert acceso.segundos_de_bloqueo(estado, AHORA) == \
        acceso.ESPERA_SEGUNDOS


def test_el_bloqueo_se_vence_solo():
    """No hace falta que nadie lo desbloquee a mano.

    Son tres o cuatro ruteros y el papa: un bloqueo que hay que ir a
    levantar a mano deja a alguien afuera en medio de la ruta.
    """
    estado = {}
    for _ in range(acceso.MAX_INTENTOS):
        acceso.anotar_fallo(estado, AHORA)

    assert acceso.segundos_de_bloqueo(
        estado, AHORA + acceso.ESPERA_SEGUNDOS + 1) == 0


def test_el_contador_se_reinicia_al_bloquear():
    """Si no, el intento siguiente bloquea de nuevo al primer error.

    La espera ya es el castigo.
    """
    estado = {}
    for _ in range(acceso.MAX_INTENTOS):
        acceso.anotar_fallo(estado, AHORA)

    assert acceso.intentos_restantes(estado) == acceso.MAX_INTENTOS


def test_entrar_bien_borra_los_intentos_fallidos():
    """Errarla cuatro veces y acertar no deja a la sesion a un paso."""
    estado = {}
    for _ in range(acceso.MAX_INTENTOS - 1):
        acceso.anotar_fallo(estado, AHORA)

    acceso.abrir(estado, acceso.huella(CLAVE_VIEJA))

    assert acceso.intentos_restantes(estado) == acceso.MAX_INTENTOS


def test_una_sesion_sin_intentos_no_esta_bloqueada():
    assert acceso.segundos_de_bloqueo({}, AHORA) == 0


def test_el_limite_es_por_sesion_y_eso_esta_escrito():
    """El limite frena el tanteo a mano, no un script.

    Un contador compartido por todo el servidor si frenaria el script,
    pero entonces cualquiera con el enlace puede dejar a los ruteros
    afuera errando la clave. A esta escala, quedarse sin app en medio
    de la ruta es un dano mas probable que el ataque que evitaria.

    Esta prueba no verifica codigo: verifica que la limitacion este
    dicha. Un limite que alguien cree mas fuerte de lo que es, es peor
    que no tenerlo.
    """
    doc = acceso.__doc__

    assert "por sesion" in doc
    assert "script" in doc, (
        "falta decir que un script abre una sesion nueva y el contador "
        "vuelve a cero")
