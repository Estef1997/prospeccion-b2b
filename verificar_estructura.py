"""
Verifica que el repo cumpla la estructura minima de un proyecto agentico.

    python verificar_estructura.py

No verifica que el contenido sea BUENO -- eso lo dice la prueba de
arranque en frio. Verifica que las piezas esten y que no falte nada
que despues cuesta caro.

Salida: lista de checks y codigo de salida 0 (todo bien) o 1 (falta algo).
"""

import ast
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).parent
fallos = []
avisos = []


def check(ok, etiqueta, detalle="", critico=True):
    """Imprime el resultado y acumula el fallo."""
    marca = "OK  " if ok else ("FALTA" if critico else "aviso")
    print(f"  [{marca}] {etiqueta}")
    if not ok:
        if detalle:
            print(f"          {detalle}")
        (fallos if critico else avisos).append(etiqueta)


def existe(nombre):
    return (RAIZ / nombre).exists()


def contiene(nombre, texto):
    ruta = RAIZ / nombre
    if not ruta.exists():
        return False
    return texto in ruta.read_text(encoding="utf-8")


print("\n=== 1. Se puede instalar y correr ===\n")

check(existe("requirements.txt"), "requirements.txt",
      "Sin esto nadie puede instalar las dependencias.")

check(existe(".env.example"), ".env.example",
      "Documenta que llaves hacen falta, sin revelarlas.")

check(existe(".gitignore"), ".gitignore")


print("\n=== 2. Secretos protegidos ===\n")

# Lo mas grave del proyecto: credenciales.json da acceso de ESCRITURA
# a las hojas de Google. Si se sube una vez, se sube para siempre --
# queda en el historial de git aunque despues se borre el archivo.
#
# .streamlit/secrets.toml se agrego el 08/10: tiene la clave del app y,
# en local, las credenciales de Google.
for secreto in (".env", "credenciales.json", "secrets.toml"):
    check(contiene(".gitignore", secreto),
          f"{secreto} ignorado por git",
          f"URGENTE: {secreto} se subiria al repositorio.")

# Los datos de negocios: cambio del 08/10/2026.
#
# Antes esto era un check critico -- los JSON tenian que estar
# ignorados. Al hospedar el app dejaron de poder estarlo: Streamlit
# Cloud despliega desde GitHub y sin los datos en el repo no hay app.
#
# La proteccion se movio de "no subirlos" a "repo privado + clave en el
# app". Esto ya no puede verificarlo un script: que el repo sea privado
# se ve en GitHub, no en el disco.
#
# Queda como aviso para que la decision se vuelva a mirar, no como
# fallo.
datos_ignorados = contiene(".gitignore", "\nprospectos_crudo.json")
check(not datos_ignorados,
      "datos de negocios suben al repo (hospedaje)",
      "prospectos_crudo.json esta ignorado: el app hospedado no va a "
      "tener datos. Si el repo es PUBLICO, al reves: debe estar "
      "ignorado y hay que revisar el hospedaje.",
      critico=False)

if not datos_ignorados:
    print("          recordatorio: el repo TIENE que ser privado,")
    print("          y el app TIENE que pedir clave (acceso.py)")

check(contiene(".gitignore", "__pycache__"),
      "__pycache__ ignorado", critico=False)


print("\n=== 3. Conocimiento escrito ===\n")

check(existe("AGENTS.md"), "AGENTS.md",
      "Las reglas del proyecto. Sin esto cada sesion las reinventa.")

check(existe("PROGRESO.md"), "PROGRESO.md",
      "Memoria entre sesiones. Sin esto el estado vive solo en tu cabeza.")

check(existe("README.md"), "README.md",
      "Para quien llega de afuera.")

# AGENTS.md sin el POR QUE de cada regla se vuelve una lista que
# alguien recorta dentro de seis meses.
check(contiene("AGENTS.md", "Origen:"),
      "AGENTS.md explica el origen de las reglas",
      "Cada regla necesita decir de que error salio.", critico=False)


print("\n=== 4. Reglas ejecutables ===\n")

hay_tests = (RAIZ / "tests").is_dir() and any((RAIZ / "tests").glob("test_*.py"))
check(hay_tests, "tests/ con al menos un test_*.py",
      "Una regla en markdown es una sugerencia; un test es una restriccion.")

if hay_tests:
    # python -m pytest, no "pytest" a secas: en Windows el ejecutable
    # queda en una carpeta que no esta en el PATH.
    print("\n  Corriendo pytest...\n")
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/"],
                       cwd=RAIZ, capture_output=True, text=True)
    print("   " + "\n   ".join(r.stdout.strip().splitlines()[-6:]))
    check(r.returncode == 0, "todos los tests pasan",
          "Hay tests en rojo. El repo no esta en estado limpio.")


print("\n=== 5. Procedimientos repetibles ===\n")

skills = RAIZ / ".claude" / "skills"
n_skills = len(list(skills.glob("*/SKILL.md"))) if skills.is_dir() else 0
check(n_skills > 0, f".claude/skills/ ({n_skills} skills)",
      "Los procedimientos que repetis deberian estar escritos.",
      critico=False)


print("\n=== 6. Los dos canales ===\n")

# Agregado el 07/10/2026. Antes este script solo conocia el pipeline de
# WhatsApp; el canal de visitas no existia cuando se escribio.

for pieza, para_que in [
    ("reglas.py", "Las reglas de negocio, en un solo lugar."),
    ("zonas.py", "La logica del canal de visitas."),
    ("registro.py", "Que paso con cada mensaje enviado."),
    ("estilo.py", "Las decisiones de diseno del app."),
    ("acceso.py", "La clave del app."),
    ("inicio.py", "El arranque comun: clave, estilo, donde se guarda."),
    ("app.py", "Punto de entrada: prepara el app y arma el menu."),
    ("bitacora.py", "Las cuentas de cada corrida, que no se borran."),
    ("mascara.py", "Lo que sale hacia el tracing, sin identidad."),
    ("trazas.py", "Si esta corrida traza o no. Una regla, un lugar."),
    ("reanudar.py", "Una corrida interrumpida no se vuelve a pagar."),
]:
    check(existe(pieza), pieza, para_que)

# Agregado el 20/10/2026 con el punto 15. La bitacora sirve para
# comparar una corrida con otra, y eso solo funciona si la cuenta es
# una sola. Si grafo.py volviera a contar por su cuenta, los dos
# numeros podrian discrepar y no habria forma de saber cual miente.
check(contiene("grafo.py", "from bitacora import"),
      "grafo.py anota en la bitacora",
      "Sin esto, 'reescritos: 3' se pierde al cerrar la terminal.")
check(contiene("validar.py", "anotar_calibracion"),
      "validar.py prueba anota su calibracion",
      "Es la unica medicion que deja historia con el pipeline en pausa.")

# CANDADO (21/10/2026). La sonda midio que los spans de nodo trazan el
# ESTADO, no el prompt: ahi viajan telefono y direccion, que
# CAMPOS_PROHIBIDOS mantiene fuera del modelo. Si el cliente de
# Langfuse se construyera sin la mascara, saldrian enteros y no habria
# ningun error en pantalla.
check(contiene("trazas.py", "mask_otel_spans=mascara.enmascarar"),
      "el tracing no se puede pedir sin mascara",
      "URGENTE: sin eso salen telefonos y direcciones de terceros.")
check(contiene("grafo.py", "mascara.recordar"),
      "grafo.py registra cada negocio antes de invocar",
      "Sin registro la mascara no sabe que tapar.")

# CANDADO DE SEGURIDAD (12/10/2026). El mas importante de este archivo.
#
# Streamlit convierte en pantalla TODO archivo de una carpeta llamada
# exactamente `pages/`, y esas pantallas corren como scripts sueltos:
# NO pasan por app.py y por lo tanto NO piden la clave.
#
# Se descubrio probando el app con un navegador antes de publicarlo:
#
#     GET /Rutas  ->  pide clave: NO / muestra datos: SI
#
# La documentacion dice que st.navigation hace que Streamlit ignore
# pages/, y es cierto -- si se llega a ejecutar. acceso.pedir() corta con
# st.stop() antes de esa linea, asi que Streamlit nunca se entera y
# vuelve al mecanismo viejo.
#
# Por eso la proteccion no es el orden de las lineas: es que la carpeta
# no exista. Una vulnerabilidad que depende del orden de ejecucion
# vuelve; una carpeta que no existe, no.
check(not (RAIZ / "pages").exists(),
      "NO existe una carpeta pages/",
      "URGENTE: Streamlit abre todo lo que haya ahi SIN pedir la clave. "
      "Las pantallas van en pantallas/ y se declaran en app.py.")

paginas = RAIZ / "pantallas"
check(paginas.is_dir(), "pantallas/ con las pantallas del app",
      "Ahi viven Rutas.py y Mensajes.py.")

if paginas.is_dir():
    # Candado reescrito el 12/10/2026, al pasar a st.navigation.
    #
    # ORIGEN (07/10): revisar.py se copio dentro de la carpeta de
    # pantallas y habria salido en el menu. El candado de entonces exigia
    # que el nombre empezara con un numero, que era la convencion del
    # mecanismo viejo de Streamlit.
    #
    # Ahora las pantallas se declaran a mano en app.py, asi que un
    # archivo suelto ya no se abre solo. Pero sigue siendo un problema
    # distinto: un archivo que NADIE declara es codigo muerto que alguien
    # va a creer que es una pantalla.
    #
    # Por eso el candado nuevo no mira el nombre: mira si app.py lo
    # nombra. Misma leccion del 07/10 con las reglas -- una prueba
    # escrita para el caso que paso no cubre la clase de error.
    declaradas = (RAIZ / "app.py").read_text(encoding="utf-8")
    sueltas = [p.name for p in paginas.glob("*.py")
               if f"pantallas/{p.name}" not in declaradas]
    check(not sueltas, "toda pantalla esta declarada en app.py",
          f"app.py no nombra: {', '.join(sueltas)}. O se agregan a "
          f"PANTALLAS, o no son pantallas y van a la raiz.")

    check(contiene("app.py", "st.navigation"),
          "app.py arma el menu con st.navigation",
          "Sin esto el menu depende del nombre de los archivos.")

    # El porton tiene que estar ANTES del menu, y una sola vez. Si una
    # pantalla volviera a llamar a preparar(), set_page_config correria
    # dos veces y Streamlit tira error.
    #
    # Se mira el ARBOL, no el texto. La primera version buscaba la
    # cadena "inicio.preparar" y se disparo con el comentario que explica
    # por que no hay que llamarlo -- un chequeo que no distingue codigo
    # de comentario acusa a su propia documentacion.
    def llama_a_preparar(ruta):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        return any(isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Attribute)
                   and n.func.attr == "preparar"
                   for n in ast.walk(arbol))

    for pagina in sorted(paginas.glob("*.py")):
        check(not llama_a_preparar(pagina),
              f"{pagina.name} no vuelve a preparar la pagina",
              "preparar() lo llama app.py una sola vez, antes del menu.")

check(existe(".streamlit/config.toml"), ".streamlit/config.toml",
      "El tema del app.", critico=False)

# El canal lo decide el dato, no una regla escrita en cada archivo.
check(contiene("reglas.py", "def es_celular"),
      "es_celular() vive en reglas.py",
      "Es quien parte el sistema en dos canales.")

check(contiene("reglas.py", "def marca"),
      "marca() vive en reglas.py",
      "Sin esto no se puede mostrar una sucursal por cadena.")

# Candado de 'una regla, un lugar' para las pantallas.
for pagina in sorted(paginas.glob("*.py")) if paginas.is_dir() else []:
    texto = pagina.read_text(encoding="utf-8")
    check("PREFIJOS_MOVIL" not in texto and "CADENAS = [" not in texto,
          f"{pagina.name} no redefine reglas",
          "Una pantalla pregunta, no define. Importar de reglas.py.")


print("\n" + "=" * 52)
if fallos:
    print(f"\nFALTAN {len(fallos)} cosas criticas:\n")
    for f in fallos:
        print(f"  - {f}")
if avisos:
    print(f"\nAvisos ({len(avisos)}):\n")
    for a in avisos:
        print(f"  - {a}")
if not fallos:
    print("\nEstructura completa.")
    print("\nSiguiente nivel: la prueba de arranque en frio.")
    print("Abri una sesion NUEVA, sin contexto, y pedile:")
    print('  "Lee el repo y decime que hace, como se corre y que falta."')
    print("Si no puede, falta algo que este script no detecta.")

print()
sys.exit(1 if fallos else 0)
