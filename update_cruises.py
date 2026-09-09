import json
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup


APIQROO_URL = "https://servicios.apiqroo.com.mx/programacion/?unit=m"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def normalizar_barco(nombre):
    nombre = nombre.upper().strip()
    nombre = re.sub(r"^(M/S|M/V)\s+", "", nombre)
    nombre = re.sub(r"\s+", " ", nombre)
    return nombre


def obtener_apiqroo():

    r = requests.get(
        APIQROO_URL,
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    cruceros = {}

    # Buscar todas las filas de la tabla
    for fila in soup.find_all("tr"):

        celdas = fila.find_all(["td", "th"])

        if len(celdas) < 7:
            continue

        datos = [
            celda.get_text(" ", strip=True)
            for celda in celdas
        ]

        texto = " | ".join(datos)

        # Necesitamos una fecha
        fecha_match = re.search(
            r"(\d{1,2})/(\d{1,2})/(\d{4})",
            texto
        )

        if not fecha_match:
            continue

        # Identificar terminal
        terminal = None

        for nombre_terminal in [
            "TERMINAL SSA MEXICO",
            "TERMINAL PUERTA MAYA",
            "TERMINAL PUNTA LANGOSTA"
        ]:
            if nombre_terminal in texto.upper():
                terminal = nombre_terminal
                break

        if not terminal:
            continue

        # El nombre del barco normalmente está en la tercera celda
        barco = None

        for dato in datos:

            limpio = dato.strip()

            if re.search(
                r"\b(M/S|M/V)\b",
                limpio,
                re.I
            ):
                barco = re.sub(
                    r"^(M/S|M/V)\s+",
                    "",
                    limpio,
                    flags=re.I
                ).strip()
                break

        # Barcos que pueden aparecer sin M/S o M/V
        if not barco:

            conocidos = [
                "MARINER OF THE SEAS",
                "RADIANCE OF THE SEAS",
                "ENCHANTMENT OF THE SEAS",
                "CELEBRITY BEYOND",
                "ICON OF THE SEAS",
                "STAR OF THE SEAS"
            ]

            for dato in datos:

                if dato.upper().strip() in conocidos:
                    barco = dato.strip()
                    break

        if not barco:
            continue

        # Buscar horarios
        horarios = re.findall(
            r"\b\d{1,2}:\d{2}\b",
            texto
        )

        if len(horarios) < 2:
            continue

        # Convertir fecha
        dia = datetime.strptime(
            fecha_match.group(0),
            "%d/%m/%Y"
        ).strftime("%Y-%m-%d")

        registro = {
            "terminal": terminal,
            "ship": normalizar_barco(barco),
            "arrival": horarios[0],
            "departure": horarios[1],
            "passengers": 0
        }

        if dia not in cruceros:
            cruceros[dia] = []
# Evitar duplicados del mismo barco en la misma terminal
existe = any(
    x["terminal"] == registro["terminal"]
    and x["ship"] == registro["ship"]
    for x in cruceros[dia]
)

        if not existe:
            cruceros[dia].append(registro)

    return cruceros


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

    mes = meses[ahora.month]
    año = ahora.year

    url = (
        "https://www.cruisetimetables.com/"
        f"cozumelmexicoschedule-{mes}{año}.html"
    )

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    lineas = [
        x.strip()
        for x in soup.get_text("\n", strip=True).splitlines()
        if x.strip()
    ]

    pasajeros = {}

    for i, linea in enumerate(lineas):

        # Buscar un número de pasajeros inmediatamente después
        # de los datos del barco

        barco = None

        # El nombre del barco puede ser el texto de un enlace
        if linea:

            posible = linea.strip()

            if (
                "SEAS" in posible.upper()
                or "CARNIVAL" in posible.upper()
                or "MSC " in posible.upper()
                or "CELEBRITY" in posible.upper()
                or "DISNEY" in posible.upper()
                or "NORWEGIAN" in posible.upper()
                or "MARGARITAVILLE" in posible.upper()
                or "PRINCESS" in posible.upper()
                or "MARDI GRAS" in posible.upper()
            ):
                barco = posible

        if not barco:
            continue

        nombre = normalizar_barco(barco)

        # Buscar en las siguientes líneas
        for siguiente in lineas[i + 1:i + 7]:

            numero = re.fullmatch(
                r"\d{3,5}",
                siguiente.replace(",", "")
            )

            if numero:

                valor = int(numero.group())

                if 500 <= valor <= 20000:

                    pasajeros[nombre] = valor
                    break

    return pasajeros


def main():

    print("Obteniendo datos de APIQROO...")

    cruceros = obtener_apiqroo()

    print(
        "Fechas encontradas:",
        len(cruceros)
    )

    total = sum(
        len(x)
        for x in cruceros.values()
    )

    print(
        "Cruceros encontrados:",
        total
    )

    print("Obteniendo pasajeros...")

    pasajeros = obtener_pasajeros()

    relacionados = 0

    for dia in cruceros:

        for crucero in cruceros[dia]:

            clave = normalizar_barco(
                crucero["ship"]
            )

            if clave in pasajeros:

                crucero["passengers"] = pasajeros[clave]
                relacionados += 1

    resultado = {
        "lastUpdated": datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        ),
        "source": "APIQROO + CruiseTimetables",
        "cruises": cruceros
    }

    with open(
        "cruise-data.json",
        "w",
        encoding="utf-8"
    ) as archivo:

        json.dump(
            resultado,
            archivo,
            ensure_ascii=False,
            indent=2
        )

    print(
        "Pasajeros relacionados:",
        relacionados
    )

    print("Actualización terminada.")


if __name__ == "__main__":
    main()
