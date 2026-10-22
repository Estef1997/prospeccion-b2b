"""
Prospeccion nacional - version 2.

Cambios respecto a v1:
- Filtra por la categoria que devuelve Google, no por el termino de busqueda
- Normaliza acentos (v1 dejaba pasar "Mega Super")
- Cadenas se marcan, no se descartan
- Reseñas en escala logaritmica (v1 saturaba a las 300)
- Marca clientes actuales para no mandarles mensaje de presentacion
- Sin castigo por distancia: la distribucion es por terceros segun la zona,
  no reparto propio desde Palmares. La distancia vuelve al modelo cuando
  exista el mapa de cobertura real.
"""

import math
import json
import os
import re
import sys
import unicodedata
from buscar_negocios import buscar_negocios

ORIGEN = (10.0567, -84.4361)  # Palmares
TIPOS = ["carniceria", "minisuper", "supermercado"]

# Peso por categoria real de Google. Supermercado arriba de carniceria
# porque el supermercado revende y la carniceria suele ser competencia.
PESO_CATEGORIA = {
    "supermercado": 25,
    "hipermercado": 25,
    "supermercado de descuentos": 25,
    "supermercado asiatico": 20,
    "mayorista": 20,
    "mercado": 15,
    "tienda de alimentacion": 15,
    "grandes almacenes": 10,
    "comercio": 5,
    "proveedores": 5,
    "carniceria": 5,
    "panaderia": 5,
}

# Categorias que no compran embutidos. Salen del listado.
CATEGORIAS_FUERA = {
    "centro comercial",
    "tienda de ropa",
    "tienda de electronica",
    "tienda de artculos para el hogar",
    "tienda de articulos para el hogar",
    "tienda de materiales para la construccion",
    "restaurante",
    "bar restaurante",
    "asesor",
    "oficinas de empresa",
    "servicios",
    "lugar de interes de establecimiento",
    "fabrica",
    "deposito",
    "tienda de bebidas alcoholicas",
}

# Las listas de negocio NO se definen aqui. Vienen de reglas.py.
#
# ORIGEN (07/10/2026): este archivo tenia sus propias copias de CADENAS,
# CLIENTES_ACTUALES y SENALES_COMPETIDOR, escritas de memoria. Se
# desincronizaron sin que nadie se enterara:
#
#   - 7 patrones de cadena agregados el 07/10 -> nunca se aplicaron
#   - "procesadora", agregada el 06/10        -> nunca se aplico
#   - "feria ejemplo dos", un CLIENTE    -> quedo como prospecto
#
# Lo peor es como se veia: pytest daba 209 passed, porque las pruebas
# miraban reglas.py, que estaba perfecto. El que escribe las banderas
# usaba otra lista. `reetiquetar` decia "Cambiaron 0" y eso era lo unico
# que delataba el problema.
#
# Es el mismo bug que CONTEXTO_FABRICA en grafo.py y validar_claude.py.
# La prueba que se escribio entonces solo revisaba esos dos archivos.
from reglas import (CADENAS, CLIENTES_ACTUALES,  # noqa: E402
                    SENALES_COMPETIDOR, contiene_palabra, normalizar)

CANTONES = {
    "San José": [
        "San José", "Escazú", "Desamparados", "Puriscal", "Tarrazú",
        "Aserrí", "Mora", "Goicoechea", "Santa Ana", "Alajuelita",
        "Vázquez de Coronado", "Acosta", "Tibás", "Moravia",
        "Montes de Oca", "Turrubares", "Dota", "Curridabat",
        "Pérez Zeledón", "León Cortés",
    ],
    "Alajuela": [
        "Alajuela", "San Ramón", "Grecia", "San Mateo", "Atenas",
        "Naranjo", "Palmares", "Poás", "Orotina", "San Carlos",
        "Zarcero", "Sarchí", "Upala", "Los Chiles", "Guatuso",
        "Río Cuarto",
    ],
    "Cartago": [
        "Cartago", "Paraíso", "La Unión", "Jiménez", "Turrialba",
        "Alvarado", "Oreamuno", "El Guarco",
    ],
    "Heredia": [
        "Heredia", "Barva", "Santo Domingo", "Santa Bárbara",
        "San Rafael", "San Isidro", "Belén", "Flores", "San Pablo",
        "Sarapiquí",
    ],
    "Guanacaste": [
        "Liberia", "Nicoya", "Santa Cruz", "Bagaces", "Carrillo",
        "Cañas", "Abangares", "Tilarán", "Nandayure", "La Cruz",
        "Hojancha",
    ],
    "Puntarenas": [
        "Puntarenas", "Esparza", "Buenos Aires", "Montes de Oro",
        "Osa", "Quepos", "Golfito", "Coto Brus", "Parrita",
        "Corredores", "Garabito", "Monteverde", "Puerto Jiménez",
    ],
    "Limón": [
        "Limón", "Pococí", "Siquirres", "Talamanca", "Matina",
        "Guácimo",
    ],
}


# normalizar() y contiene_palabra() tambien vienen de reglas.py.
#
# Estaban copiadas aqui y, como se definian DESPUES del import, pisaban
# a las de reglas.py sin que nada lo avisara. Hoy eran identicas; manana
# alguien arregla un caso raro en una sola de las dos.


def distancia_km(lat, lng):
    """Se sigue calculando y guardando, pero ya no pesa en el puntaje."""
    if lat is None or lng is None:
        return None
    lat1, lng1 = ORIGEN
    dlat = math.radians(lat - lat1)
    dlng = math.radians(lng - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat))
         * math.sin(dlng / 2) ** 2)
    return round(2 * 6371 * math.asin(math.sqrt(a)), 1)


def etiquetar(negocio):
    """Devuelve dict con banderas. Ninguna descarta por si sola."""
    nombre = normalizar(negocio.get("nombre"))
    categoria = normalizar(negocio.get("categoria"))

    return {
        "es_cadena": contiene_palabra(CADENAS, nombre),
        "es_cliente": contiene_palabra(CLIENTES_ACTUALES, nombre),
        # Subcadena a proposito: las senales son palabras de producto y
        # tienen que atrapar el plural ("embutido" en "Embutidos Lucy").
        # Con limite de palabra no coincidirian.
        "posible_competidor": any(normalizar(s) in nombre
                                  for s in SENALES_COMPETIDOR),
        "fuera_de_rubro": categoria in CATEGORIAS_FUERA,
        "cerrado": negocio.get("estado") not in (None, "OPERATIONAL"),
    }


def puntuar(negocio):
    """Puntaje de potencial. Ordena la lista; no predice quien compra."""
    puntos = 0

    # Escala log: 100 resenas suma 16, 1000 suma 24, 20000 suma 34.
    # Con tope lineal (v1) todo lo que pasaba 300 quedaba empatado.
    resenas = negocio.get("num_resenas") or 0
    puntos += min(math.log10(resenas + 1) * 8, 30)

    rating = negocio.get("rating")
    if rating:
        puntos += (rating - 3) * 5

    # Contactabilidad. Sin canal de entrada el redactor no puede operar.
    if negocio.get("telefono"):
        puntos += 15
    if negocio.get("sitio_web"):
        puntos += 10

    categoria = normalizar(negocio.get("categoria"))
    puntos += PESO_CATEGORIA.get(categoria, 0)

    # Sin componente de distancia: ver docstring del modulo.

    return round(puntos, 1)


def prospectar(provincias=None, tipos=None):
    provincias = provincias or list(CANTONES.keys())
    tipos = tipos or TIPOS

    vistos = set()
    resultados = []
    llamadas = 0

    for provincia in provincias:
        for canton in CANTONES.get(provincia, []):
            zona = f"{canton}, {provincia}, Costa Rica"

            for tipo in tipos:
                try:
                    encontrados = buscar_negocios(zona, tipo)
                    llamadas += 1
                except Exception as e:
                    print(f"  ERROR en {zona} / {tipo}: {e}")
                    continue

                for n in encontrados:
                    if n["place_id"] in vistos:
                        continue
                    vistos.add(n["place_id"])

                    n["canton"] = canton
                    n["provincia"] = provincia
                    n["distancia_km"] = distancia_km(n["lat"], n["lng"])
                    n.update(etiquetar(n))
                    n["puntaje"] = puntuar(n)
                    resultados.append(n)

            print(f"{canton}, {provincia}: {len(vistos)} unicos")

    print(f"\nLlamadas a la API: {llamadas}")
    resultados.sort(key=lambda x: x["puntaje"], reverse=True)
    return resultados


def resumen(datos, n=25):
    fuera = [d for d in datos if d["fuera_de_rubro"]]
    clientes = [d for d in datos if d["es_cliente"]]
    competidores = [d for d in datos
                    if d["posible_competidor"] and not d["es_cliente"]]
    prospectos = [d for d in datos
                  if not d["fuera_de_rubro"]
                  and not d["es_cliente"]
                  and not d["posible_competidor"]
                  and not d["cerrado"]]

    print(f"\nTotal: {len(datos)}")
    print(f"  Fuera de rubro:      {len(fuera)}")
    print(f"  Cerrados:            {len([d for d in datos if d['cerrado']])}")
    print(f"  Ya son clientes:     {len(clientes)}")
    print(f"  Posibles competidores: {len(competidores)}")
    print(f"  Prospectos:          {len(prospectos)}")
    print(f"    de los cuales cadena: "
          f"{len([p for p in prospectos if p['es_cadena']])}")

    print(f"\nTop {n} prospectos:\n")
    for p in prospectos[:n]:
        marca = "[cadena] " if p["es_cadena"] else ""
        contacto = ("tel" if p.get("telefono") else "   ") + \
                   ("/web" if p.get("sitio_web") else "    ")
        print(f"{p['puntaje']:6.1f}  {marca}{(p['nombre'] or '')[:36]:38} "
              f"{(p['categoria'] or '')[:20]:22} "
              f"{p['canton'][:12]:14} {str(p['distancia_km']):6} km  {contacto}")

    # Control: los clientes actuales deberian quedar arriba en el ranking
    # general. Si quedan dispersos, los pesos estan mal calibrados.
    if clientes:
        print("\nDonde caen los clientes actuales (ranking general):\n")
        for i, d in enumerate(datos):
            if d["es_cliente"]:
                print(f"  #{i+1:<4} {d['puntaje']:6.1f}  "
                      f"{(d['nombre'] or '')[:40]}")

    return prospectos


def por_categoria(prospectos, n=15):
    """Ordena por tamano DENTRO de cada categoria.

    Comparar una pulperia con un hipermercado no dice nada;
    comparar supermercados entre si, si.
    """
    grupos = {}
    for p in prospectos:
        grupos.setdefault(p.get("categoria") or "Sin categoria", []).append(p)

    orden = ["Supermercado", "Hipermercado", "Supermercado de descuentos",
             "Mayorista", "Mercado", "Tienda de alimentación", "Carnicería"]

    for cat in orden:
        items = grupos.get(cat, [])
        if not items:
            continue
        items.sort(key=lambda x: x.get("num_resenas") or 0, reverse=True)
        print(f"\n=== {cat} ({len(items)}) ===\n")
        for p in items[:n]:
            marca = "[cadena] " if p["es_cadena"] else ""
            print(f"  {p['num_resenas'] or 0:6} res  {marca}"
                  f"{(p['nombre'] or '')[:36]:38} "
                  f"{p['canton'][:12]:14} {str(p['distancia_km']):6} km")


def reetiquetar(ruta="prospectos_crudo.json"):
    """Recalcula banderas y puntaje sobre el JSON ya guardado.

    Las banderas quedan horneadas en el archivo cuando corre prospectar().
    Cambiar CADENAS o CLIENTES_ACTUALES no sirve de nada hasta que se
    recalculan, y volver a llamar a Places gasta cuota sin necesidad:
    etiquetar() y puntuar() no consultan la API.
    """
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)

    banderas = ("es_cadena", "es_cliente", "posible_competidor",
                "fuera_de_rubro", "cerrado")
    cambios = []

    for n in datos:
        antes = {k: n.get(k) for k in banderas}
        n.update(etiquetar(n))
        n["puntaje"] = puntuar(n)
        despues = {k: n[k] for k in banderas}
        if antes != despues:
            distintas = [k for k in banderas if antes[k] != despues[k]]
            cambios.append((n["nombre"], distintas, despues))

    datos.sort(key=lambda x: x["puntaje"], reverse=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

    print(f"Reetiquetados {len(datos)} registros en {ruta}")
    print(f"Cambiaron {len(cambios)}:\n")
    for nombre, distintas, despues in cambios:
        detalle = ", ".join(f"{k}={despues[k]}" for k in distintas)
        print(f"  {(nombre or '')[:44]:46} {detalle}")
    return cambios


ARCHIVO = "prospectos_crudo.json"


def cargar_existente(ruta=ARCHIVO):
    if not os.path.exists(ruta):
        return []
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def fusionar(viejos, nuevos):
    """Agrega lo nuevo sin perder lo viejo.

    ORIGEN (05/10/2026): antes se escribia el archivo con "w" y los
    resultados de la corrida. Buscar en Puntarenas habria borrado los
    629 de Alajuela, que ya estaban pagados.

    Un negocio que aparece en las dos, gana el nuevo: trae rating y
    telefono mas frescos. El resto se conserva tal cual.
    """
    por_id = {n["place_id"]: n for n in viejos}
    agregados = sum(1 for n in nuevos if n["place_id"] not in por_id)

    por_id.update({n["place_id"]: n for n in nuevos})

    salida = sorted(por_id.values(), key=lambda x: x.get("puntaje") or 0,
                    reverse=True)
    return salida, agregados


def guardar(datos, ruta=ARCHIVO):
    """Temporal y renombrar: si el proceso muere, el viejo queda entero.

    Lo que hay adentro son llamadas a Places ya pagadas.
    """
    tmp = str(ruta) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)


def costo_estimado(provincias, tipos=None):
    """Llamadas que va a hacer. Places cobra por llamada."""
    tipos = tipos or TIPOS
    return sum(len(CANTONES.get(p, [])) for p in provincias) * len(tipos)


AYUDA = """\
Uso:

  python prospecto.py reetiquetar
      Recalcula banderas y puntaje sobre lo que ya hay.
      NO llama a la API. Es lo que hay que correr despues de
      cambiar algo en reglas.py.

  python prospecto.py buscar <Provincia> [Provincia...]
      Busca en esas provincias y FUSIONA con lo que ya existe.
      Cada canton son {n} llamadas a Google Places, una por tipo.

  python prospecto.py costo <Provincia> [Provincia...]
      Dice cuantas llamadas costaria, sin hacer ninguna.

Provincias: {provincias}

Correr sin argumentos no hace nada a proposito: antes rehacia la
busqueda completa, que son cientos de llamadas con costo real.
"""


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    pedidas = sys.argv[2:]

    if modo == "reetiquetar":
        reetiquetar()
        sys.exit(0)

    if modo not in ("buscar", "costo"):
        print(AYUDA.format(n=len(TIPOS),
                           provincias=", ".join(CANTONES)))
        sys.exit(0)

    provincias = pedidas or list(CANTONES)

    desconocidas = [p for p in provincias if p not in CANTONES]
    if desconocidas:
        sys.exit(f"No conozco: {', '.join(desconocidas)}.\n"
                 f"Las validas son: {', '.join(CANTONES)}")

    llamadas = costo_estimado(provincias)
    cantones = sum(len(CANTONES[p]) for p in provincias)
    print(f"{', '.join(provincias)}: {cantones} cantones, "
          f"{llamadas} llamadas a Places")

    if modo == "costo":
        sys.exit(0)

    existente = cargar_existente()
    print(f"Ya hay {len(existente)} negocios guardados.\n")

    datos = prospectar(provincias=provincias)
    salida, agregados = fusionar(existente, datos)

    prospectos = resumen(salida)
    por_categoria(prospectos)

    guardar(salida)
    print(f"\n{agregados} negocios nuevos. "
          f"{len(salida)} en total en {ARCHIVO}")
