import json
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup


APIQROO_URL = "https://servicios.apiqroo.com.mx/programacion/?unit=m"
CRUISE_URL = "https://www.cruisetimetables.com/cozumelmexicoschedule-sep2026.html"

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
    fecha_actual = None

    # APIQROO coloca la fecha en una fila y
    # los barcos en las filas siguientes.
    for fila in soup.find_all("tr"):

        texto = fila.get_text(" ", strip=True)

        # Detectar encabezado de fecha
        fecha = re.search(
            r"(\d{1,2})/(\d{1,2})/(\d{4})",
            texto
        )

        if fecha and not re.search(r"\d{1,2}:\d{2}", texto):

            dia = int(fecha.group(1))
            mes = int(fecha.group(2))
            año = int(fecha.group(3))

            fecha_actual = f"{año:04d}-{mes:02d}-{dia:02d}"

            if fecha_actual not in cruceros:
                cruceros[fecha_actual] = []

            continue

        if not fecha_actual:
            continue

        # Terminal
        terminal_match = re.search(
            r"(TERMINAL\s+[A-ZÁÉÍÓÚÑ ]+)",
            texto,
            re.I
        )

        # Barco
        barco_match = re.search(
            r"(M/S\s+[A-Z0-9 .'-]+|M/V\s+[A-Z0-9 .'-]+|"
            r"MARINER OF THE SEAS|RADIANCE OF THE SEAS|"
            r"ENCHANTMENT OF THE SEAS|CELEBRITY BEYOND|"
            r"ICON OF THE SEAS)",
            texto,
            re.I
        )

        # Horarios
        horarios = re.findall(
            r"\b\d{1,2}:\d{2}\b",
            texto
        )

        if not barco_match or len(horarios) < 2:
            continue

        barco = normalizar_barco(barco_match.group(1))

        terminal = (
            terminal_match.group(1).upper().strip()
            if terminal_match
            else "SIN TERMINAL"
        )

        registro = {
            "terminal": terminal,
            "ship": barco,
            "arrival": horarios[0],
            "departure": horarios[1],
            "passengers": 0
        }

        # Evitar duplicados
        existe = any(
            x["ship"] == registro["ship"]
            and x["terminal"] == registro["terminal"]
            and x["arrival"] == registro["arrival"]
            and x["departure"] == registro["departure"]
            for x in cruceros[fecha_actual]
        )

        if not existe:
            cruceros[fecha_actual].append(registro)

    return cruceros


def obtener_pasajeros():

    # Usamos el mes actual automáticamente
    ahora = datetime.now()

    mes = ahora.strftime("%b").lower()
    año = ahora.strftime("%Y")

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

    pasajeros = {}

    barcos_conocidos = [
        "Carnival Valor",
        "Carnival Paradise",
        "Carnival Breeze",
        "Carnival Jubilee",
        "Carnival Liberty",
        "Carnival Celebration",
        "Carnival Dream",
        "Disney Treasure",
        "Disney Destiny",
        "Harmony Of The Seas",
        "Mariner Of The Seas",
        "Icon Of The Seas",
        "MSC Seashore",
        "MSC Seascape",
        "MSC World America",
        "Radiance Of The Seas",
        "Symphony Of The Seas",
        "Enchantment Of The Seas",
        "Regal Princess",
        "Celebrity Beyond",
        "Celebrity Reflection",
        "Norwegian Prima",
        "Margaritaville At Sea Islander",
        "Mardi Gras",
        "Star Of The Seas"
    ]

    for enlace in soup.find_all("a"):

        nombre = enlace.get_text(" ", strip=True)

        barco = None

        for candidato in barcos_conocidos:
            if nombre.lower() == candidato.lower():
                barco = candidato
                break

        if not barco:
            continue

        # Subimos por el HTML hasta encontrar un bloque
        # que contenga horarios y pasajeros.
        contenedor = enlace

        for _ in range(5):

            if not contenedor.parent:
                break

            contenedor = contenedor.parent

            texto = contenedor.get_text(
                " ",
                strip=True
            )

            horarios = re.findall(
                r"\b[ad]\s*(\d{4})\b",
                texto,
                re.I
            )

            numeros = re.findall(
                r"\b\d{3,5}\b",
                texto
            )

            candidatos = []

            for numero in numeros:

                valor = int(numero)

                # Los pasajeros de cruceros normalmente
                # están dentro de este rango.
                if 500 <= valor <= 20000:
                    candidatos.append(valor)

            if len(horarios) >= 2 and candidatos:

                clave = normalizar_barco(barco)

                pasajeros[clave] = candidatos[-1]

                break

    return pasajeros


def main():

    print("1. Obteniendo datos de APIQROO...")

    cruceros = obtener_apiqroo()

    print(
        "Fechas encontradas:",
        len(cruceros)
    )

    print("2. Obteniendo pasajeros...")

    pasajeros = obtener_pasajeros()

    encontrados = 0

    for fecha, lista in cruceros.items():

        for crucero in lista:

            clave = normalizar_barco(
                crucero["ship"]
            )

            if clave in pasajeros:

                crucero["passengers"] = pasajeros[clave]

                encontrados += 1

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

    total = sum(
        len(lista)
        for lista in cruceros.values()
    )

    print(
        "Actualización terminada."
    )

    print(
        "Cruceros encontrados:",
        total
    )

    print(
        "Pasajeros relacionados:",
        encontrados
    )


if __name__ == "__main__":
    main()
