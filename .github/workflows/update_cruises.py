import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


APIQROO_URL = "https://servicios.apiqroo.com.mx/programacion/?unit=m"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Safari/605.1.15"
    )
}


MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def normalize_ship_name(name):
    name = name.upper()

    name = re.sub(r"^M/S\s+", "", name)
    name = re.sub(r"^M/V\s+", "", name)

    name = re.sub(r"\s+", " ", name)

    return name.strip()


def clean_terminal(terminal):
    terminal = terminal.upper()

    terminal = terminal.replace("TERMINAL ", "")

    replacements = {
        "SSA MEXICO": "SSA México",
        "PUERTA MAYA": "Puerta Maya",
        "PUNTA LANGOSTA": "Punta Langosta",
    }

    return replacements.get(
        terminal,
        terminal.title()
    )


def get_apiqroo_data():
    print("Consultando APIQROO...")

    response = requests.get(
        APIQROO_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    cruises = {}

    current_date = None

    for row in soup.find_all("tr"):

        cells = row.find_all(
            ["td", "th"]
        )

        texts = [
            cell.get_text(
                " ",
                strip=True
            )
            for cell in cells
        ]

        row_text = " ".join(texts)

        # Detectar fecha.
        match = re.search(
            r"(\d{1,2})/(\d{1,2})/(\d{4})",
            row_text
        )

        if match:

            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))

            try:
                current_date = (
                    datetime(
                        year,
                        month,
                        day
                    ).strftime("%Y-%m-%d")
                )

            except ValueError:
                current_date = None

        if not current_date:
            continue

        # APIQROO normalmente entrega 8 columnas.
        if len(texts) < 7:
            continue

        terminal = texts[0]

        # Buscar el nombre del barco.
        ship = None

        for text in texts:

            upper = text.upper()

            if any(
                keyword in upper
                for keyword in [
                    "OF THE SEAS",
                    "CARNIVAL",
                    "MSC ",
                    "DISNEY ",
                    "CELEBRITY ",
                    "REGAL PRINCESS",
                    "ICON OF THE SEAS",
                    "STAR OF THE SEAS",
                    "MARGARITAVILLE",
                    "NORWEGIAN",
                ]
            ):

                ship = text
                break

        if not ship:
            continue

        # Buscar horarios.
        times = re.findall(
            r"\b\d{1,2}:\d{2}\b",
            row_text
        )

        if len(times) < 2:
            continue

        arrival = times[0]
        departure = times[1]

        cruise = {
            "terminal": clean_terminal(
                terminal
            ),
            "ship": ship.strip(),
            "arrival": arrival,
            "departure": departure,
            "passengers": None,
        }

        cruises.setdefault(
            current_date,
            []
        ).append(cruise)

    return cruises


def get_cruisetimetables_data():
    print("Consultando CruiseTimetables...")

    now = datetime.now()

    month_name = now.strftime(
        "%b"
    ).lower()

    year = now.year

    url = (
        "https://www.cruisetimetables.com/"
        f"cozumelmexicoschedule-{month_name}{year}.html"
    )

    print(
        f"URL CruiseTimetables: {url}"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    passenger_data = {}

    current_date = None

    # Recorremos el texto visible.
    lines = [
        line.strip()
        for line in soup.stripped_strings
    ]

    for i, line in enumerate(lines):

        # Detectar encabezado del día.
        date_match = re.match(
            r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})$",
            line
        )

        if date_match:

            day = int(
                date_match.group(2)
            )

            try:

                current_date = (
                    datetime(
                        year,
                        now.month,
                        day
                    ).strftime(
                        "%Y-%m-%d"
                    )
                )

            except ValueError:

                current_date = None

            continue

        if not current_date:
            continue

        # Horario tipo:
        # a 0800 d 1600
        time_match = re.search(
            r"a\s*(\d{4})\s*d\s*(\d{4})",
            line,
            re.IGNORECASE
        )

        if not time_match:
            continue

        arrival_raw = time_match.group(1)
        departure_raw = time_match.group(2)

        # Buscar pasajero en las siguientes líneas.
        passengers = None

        for next_line in lines[
            i + 1:i + 8
        ]:

            passenger_match = re.fullmatch(
                r"\d{3,6}",
                next_line.replace(",", "")
            )

            if passenger_match:

                passengers = int(
                    next_line.replace(
                        ",",
                        ""
                    )
                )

                break

        if passengers is None:
            continue

        # El nombre del barco suele estar unas líneas antes.
        ship = None

        for previous_line in reversed(
            lines[
                max(0, i - 8):i
            ]
        ):

            candidate = previous_line.strip()

            if len(candidate) < 3:
                continue

            if re.search(
                r"(OF THE SEAS|CARNIVAL|MSC|DISNEY|CELEBRITY|PRINCESS|NORWEGIAN|MARGARITAVILLE|ICON OF THE SEAS|STAR OF THE SEAS)",
                candidate,
                re.IGNORECASE
            ):

                ship = candidate
                break

        if not ship:
            continue

        arrival = (
            arrival_raw[:2]
            + ":"
            + arrival_raw[2:]
        )

        departure = (
            departure_raw[:2]
            + ":"
            + departure_raw[2:]
        )

        passenger_data.setdefault(
            current_date,
            []
        ).append({
            "ship": normalize_ship_name(
                ship
            ),
            "arrival": arrival,
            "departure": departure,
            "passengers": passengers,
        })

    return passenger_data


def merge_data(apiqroo, cruise_times):
    print("Combinando información...")

    final_data = {}

    for date, ships in apiqroo.items():

        final_data[date] = []

        for ship in ships:

            api_name = normalize_ship_name(
                ship["ship"]
            )

            passenger_value = None

            # Buscar coincidencia exacta.
            for ct_ship in cruise_times.get(
                date,
                []
            ):

                ct_name = normalize_ship_name(
                    ct_ship["ship"]
                )

                if (
                    api_name == ct_name
                    or api_name in ct_name
                    or ct_name in api_name
                ):

                    passenger_value = (
                        ct_ship["passengers"]
                    )

                    break

            final_data[date].append({

                "terminal": ship["terminal"],

                "ship": ship["ship"],

                "arrival": ship["arrival"],

                "departure": ship["departure"],

                "passengers": passenger_value

            })

    return final_data


def save_data(data):
    output = {
        "lastUpdated": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "source": (
            "APIQROO + CruiseTimetables"
        ),
        "cruises": data
    }

    path = Path(
        "cruise-data.json"
    )

    path.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        f"Archivo actualizado: {path}"
    )


def main():

    apiqroo = get_apiqroo_data()

    if not apiqroo:
        raise RuntimeError(
            "APIQROO no devolvió cruceros."
        )

    cruise_times = (
        get_cruisetimetables_data()
    )

    final_data = merge_data(
        apiqroo,
        cruise_times
    )

    save_data(
        final_data
    )

    total = sum(
        len(items)
        for items in final_data.values()
    )

    print(
        f"Cruceros procesados: {total}"
    )


if __name__ == "__main__":
    main()
