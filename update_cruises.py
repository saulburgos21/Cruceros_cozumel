import json
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURACIÓN
# ============================================================

APIQROO_URL = "https://servicios.apiqroo.com.mx/programacion/?unit=m"

CRUISE_TIMETABLES_BASE = (
    "https://www.cruisetimetables.com/"
    "cozumelmexicoschedule-{mes}{anio}.html"
)

OUTPUT_FILE = "cruise-data.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0 Safari/537.36"
    )
}


# ============================================================
# NORMALIZAR NOMBRE DEL BARCO
# ============================================================

def normalizar_barco(nombre):
    if not nombre:
        return ""

    nombre = str(nombre).upper().strip()

    # Eliminar prefijos navales
    nombre = re.sub(
        r"^(M/S|M/V|S/S|SS)\s+",
        "",
        nombre
    )

    # Espacios múltiples
    nombre = re.sub(
        r"\s+",
        " ",
        nombre
    )

    return nombre.strip()


# ============================================================
# NORMALIZAR TERMINAL
# ============================================================

def normalizar_terminal(nombre):
    if not nombre:
        return ""

    nombre = str(nombre).upper().strip()

    nombre = re.sub(
        r"\s+",
        " ",
        nombre
    )

    return nombre


# ============================================================
# CONVERTIR FECHA APIQROO
# ============================================================

def convertir_fecha(fecha_texto):

    if not fecha_texto:
        return None

    fecha_texto = fecha_texto.strip()

    formatos = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d"
    ]

    for formato in formatos:
        try:
            return datetime.strptime(
                fecha_texto,
                formato
            ).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Buscar una fecha dentro del texto
    coincidencia = re.search(
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
        fecha_texto
    )

    if coincidencia:

        try:
            fecha = datetime.strptime(
                coincidencia.group(0),
                "%d/%m/%Y"
            )

            return fecha.strftime("%Y-%m-%d")

        except ValueError:
            pass

    return None


# ============================================================
# VALIDAR HORA
# ============================================================

def es_hora(valor):

    if not valor:
        return False

    return bool(
        re.fullmatch(
            r"\d{1,2}:\d{2}",
            valor.strip()
        )
    )


# ============================================================
# OBTENER DATOS DE APIQROO
# ============================================================

def obtener_apiqroo():

    print("Consultando APIQROO...")

    respuesta = requests.get(
        APIQROO_URL,
        headers=HEADERS,
        timeout=30
    )

    respuesta.raise_for_status()

    soup = BeautifulSoup(
        respuesta.text,
        "html.parser"
    )

    cruceros = {}

    filas_procesadas = 0
    filas_aceptadas = 0
    duplicados = 0

    # --------------------------------------------------------
    # Buscar solamente filas de tabla
    # --------------------------------------------------------

    for fila in soup.find_all("tr"):

        celdas = fila.find_all("td")

        # Una fila válida de APIQROO tiene las columnas:
        #
        # 0 = Puerto
        # 1 = Bandera
        # 2 = Crucero
        # 3 = Fecha arribo
        # 4 = ETA
        # 5 = Fecha zarpe
        # 6 = ETD
        # 7 = Status
        #
        if len(celdas) < 7:
            continue

        filas_procesadas += 1

        datos = [
            celda.get_text(
                " ",
                strip=True
            )
            for celda in celdas
        ]

        # ----------------------------------------------------
        # EXTRAER CADA COLUMNA INDIVIDUALMENTE
        # ----------------------------------------------------

        puerto = datos[0].strip()
        barco_original = datos[2].strip()
        fecha_arribo = datos[3].strip()
        eta = datos[4].strip()

        # ----------------------------------------------------
        # TERMINAL
        # ----------------------------------------------------

        terminal = normalizar_terminal(
            puerto
        )

        terminales_validas = {
            "TERMINAL SSA MEXICO",
            "TERMINAL PUERTA MAYA",
            "TERMINAL PUNTA LANGOSTA"
        }

        if terminal not in terminales_validas:
            continue

        # ----------------------------------------------------
        # BARCO
        # ----------------------------------------------------

        barco = normalizar_barco(
            barco_original
        )

        if not barco:
            continue

        # Evitar encabezados
        if barco in {
            "CRUCERO",
            "BUQUE",
            "SHIP"
        }:
            continue

        # ----------------------------------------------------
        # FECHA
        # ----------------------------------------------------

        fecha = convertir_fecha(
            fecha_arribo
        )

        if not fecha:
            continue

        # ----------------------------------------------------
        # HORARIOS
        # ----------------------------------------------------

        if not es_hora(eta):
            continue

        # ----------------------------------------------------
        # BUSCAR ETD
        # ----------------------------------------------------

        etd = ""

        if len(datos) > 6:
            posible_etd = datos[6].strip()

            if es_hora(posible_etd):
                etd = posible_etd

        if not etd:
            # Intento adicional por seguridad
            horas = []

            for dato in datos:
                if es_hora(dato):
                    horas.append(dato)

            if len(horas) >= 2:
                eta = horas[0]
                etd = horas[1]

        if not etd:
            continue

        # ----------------------------------------------------
        # CREAR DÍA
        # ----------------------------------------------------

        if fecha not in cruceros:
            cruceros[fecha] = []

        # ----------------------------------------------------
        # EVITAR DUPLICADOS
        #
        # REGLA:
        # Un mismo barco solamente puede aparecer una vez
        # en una misma fecha.
        # ----------------------------------------------------

        ya_existe = any(
            normalizar_barco(
                registro["ship"]
            ) == barco
            for registro in cruceros[fecha]
        )

        if ya_existe:

            duplicados += 1

            print(
                f"⚠️ Duplicado ignorado: "
                f"{fecha} - {barco}"
            )

            continue

        # ----------------------------------------------------
        # CREAR REGISTRO
        # ----------------------------------------------------

        registro = {
            "terminal": terminal,
            "ship": barco,
            "arrival": eta,
            "departure": etd,
            "passengers": 0
        }

        cruceros[fecha].append(
            registro
        )

        filas_aceptadas += 1

    # --------------------------------------------------------
    # ORDENAR CRUCEROS POR HORA DE ARRIBO
    # --------------------------------------------------------

    for fecha in cruceros:

        cruceros[fecha].sort(
            key=lambda x: x["arrival"]
        )

    print(
        f"Filas procesadas: {filas_procesadas}"
    )

    print(
        f"Cruceros aceptados: {filas_aceptadas}"
    )

    print(
        f"Duplicados ignorados: {duplicados}"
    )

    print(
        f"Días encontrados: {len(cruceros)}"
    )

    return cruceros


# ============================================================
# OBTENER PASAJEROS DE CRUISETIMETABLES
# ============================================================

def obtener_pasajeros():

    ahora = datetime.now()

    meses = {
        1: "jan",
        2: "feb",
        3: "mar",
        4: "apr",
        5: "may",
        6: "jun",
        7: "jul",
        8: "aug",
        9: "sep",
        10: "oct",
        11: "nov",
        12: "dec"
    }

    mes = meses[
        ahora.month
    ]

    anio = ahora.year

    url = CRUISE_TIMETABLES_BASE.format(
        mes=mes,
        anio=anio
    )

    print(
        f"Consultando pasajeros: {url}"
    )

    try:

        respuesta = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        respuesta.raise_for_status()

    except Exception as error:

        print(
            "⚠️ No se pudo consultar "
            f"CruiseTimetables: {error}"
        )

        return {}

    soup = BeautifulSoup(
        respuesta.text,
        "html.parser"
    )

    lineas = [
        linea.strip()
        for linea in soup.get_text(
            "\n",
            strip=True
        ).splitlines()
        if linea.strip()
    ]

    pasajeros = {}

    # --------------------------------------------------------
    # Palabras que identifican nombres de barcos
    # --------------------------------------------------------

    palabras_barcos = [
        "SEAS",
        "CARNIVAL",
        "MSC ",
        "CELEBRITY",
        "DISNEY",
        "NORWEGIAN",
        "MARGARITAVILLE",
        "PRINCESS",
        "MARDI GRAS",
        "EXPLORA",
        "ICON",
        "STAR OF THE SEAS"
    ]

    for i, linea in enumerate(lineas):

        posible_barco = linea.strip()

        texto_mayusculas = (
            posible_barco.upper()
        )

        es_barco = any(
            palabra in texto_mayusculas
            for palabra in palabras_barcos
        )

        if not es_barco:
            continue

        nombre = normalizar_barco(
            posible_barco
        )

        if not nombre:
            continue

        # ----------------------------------------------------
        # Buscar pasajeros cerca del nombre del barco
        # ----------------------------------------------------

        for siguiente in lineas[
            i + 1:i + 8
        ]:

            numero_limpio = (
                siguiente
                .replace(",", "")
                .replace(" ", "")
            )

            if not re.fullmatch(
                r"\d{3,5}",
                numero_limpio
            ):
                continue

            valor = int(
                numero_limpio
            )

            # Rango razonable para pasajeros
            if 500 <= valor <= 20000:

                # Si ya existe, conservar el primero
                if nombre not in pasajeros:

                    pasajeros[
                        nombre
                    ] = valor

                    print(
                        f"Pasajeros: "
                        f"{nombre} = {valor:,}"
                    )

                break

    print(
        f"Barcos con pasajeros encontrados: "
        f"{len(pasajeros)}"
    )

    return pasajeros


# ============================================================
# RELACIONAR PASAJEROS
# ============================================================

def relacionar_pasajeros(
    cruceros,
    pasajeros
):

    relacionados = 0
    sin_dato = 0

    for fecha, lista in cruceros.items():

        for crucero in lista:

            nombre = normalizar_barco(
                crucero["ship"]
            )

            if nombre in pasajeros:

                crucero["passengers"] = (
                    pasajeros[nombre]
                )

                relacionados += 1

            else:

                # No inventamos pasajeros
                crucero["passengers"] = 0

                sin_dato += 1

                print(
                    f"⚠️ Sin pasajeros: "
                    f"{fecha} - {nombre}"
                )

    return relacionados, sin_dato


# ============================================================
# ELIMINAR SEGURIDAD EXTRA DE DUPLICADOS
# ============================================================

def limpiar_duplicados(cruceros):

    resultado = {}

    eliminados = 0

    for fecha, lista in cruceros.items():

        resultado[fecha] = []

        barcos_vistos = set()

        for crucero in lista:

            barco = normalizar_barco(
                crucero["ship"]
            )

            if barco in barcos_vistos:

                eliminados += 1

                print(
                    f"⚠️ Duplicado eliminado: "
                    f"{fecha} - {barco}"
                )

                continue

            barcos_vistos.add(
                barco
            )

            resultado[fecha].append(
                crucero
            )

        resultado[fecha].sort(
            key=lambda x: x["arrival"]
        )

    if eliminados:
        print(
            f"Duplicados eliminados en "
            f"limpieza final: {eliminados}"
        )

    return resultado


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print(
        "======================================"
    )
    print(
        " ACTUALIZACIÓN DE CRUCEROS COZUMEL"
    )
    print(
        "======================================"
    )
    print("")

    # --------------------------------------------------------
    # 1. APIQROO
    # --------------------------------------------------------

    print(
        "1. Obteniendo programación de APIQROO..."
    )

    cruceros = obtener_apiqroo()

    if not cruceros:

        raise RuntimeError(
            "APIQROO no devolvió cruceros."
        )

    total_cruceros = sum(
        len(lista)
        for lista in cruceros.values()
    )

    print(
        f"Total de cruceros encontrados: "
        f"{total_cruceros}"
    )

    # --------------------------------------------------------
    # 2. LIMPIEZA EXTRA
    # --------------------------------------------------------

    print("")
    print(
        "2. Verificando duplicados..."
    )

    cruceros = limpiar_duplicados(
        cruceros
    )

    # --------------------------------------------------------
    # 3. PASAJEROS
    # --------------------------------------------------------

    print("")
    print(
        "3. Obteniendo pasajeros..."
    )

    pasajeros = obtener_pasajeros()

    # --------------------------------------------------------
    # 4. RELACIONAR
    # --------------------------------------------------------

    print("")
    print(
        "4. Relacionando pasajeros..."
    )

    relacionados, sin_dato = (
        relacionar_pasajeros(
            cruceros,
            pasajeros
        )
    )

    print(
        f"Pasajeros relacionados: "
        f"{relacionados}"
    )

    print(
        f"Cruceros sin dato de pasajeros: "
        f"{sin_dato}"
    )

    # --------------------------------------------------------
    # 5. RESULTADO FINAL
    # --------------------------------------------------------

    resultado = {

        "lastUpdated": datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        ),

        "source": (
            "APIQROO + CruiseTimetables"
        ),

        "cruises": cruceros
    }

    # --------------------------------------------------------
    # 6. GUARDAR JSON
    # --------------------------------------------------------

    print("")
    print(
        "5. Guardando cruise-data.json..."
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as archivo:

        json.dump(
            resultado,
            archivo,
            ensure_ascii=False,
            indent=2
        )

    # --------------------------------------------------------
    # 7. RESUMEN
    # --------------------------------------------------------

    total_final = sum(
        len(lista)
        for lista in cruceros.values()
    )

    print("")
    print(
        "======================================"
    )
    print(
        " ACTUALIZACIÓN COMPLETADA"
    )
    print(
        "======================================"
    )

    print(
        f"Días: {len(cruceros)}"
    )

    print(
        f"Cruceros: {total_final}"
    )

    print(
        f"Pasajeros relacionados: "
        f"{relacionados}"
    )

    print(
        f"Sin pasajeros: {sin_dato}"
    )

    print(
        f"Archivo: {OUTPUT_FILE}"
    )

    print(
        "======================================"
    )


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":
    main()