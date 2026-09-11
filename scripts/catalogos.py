# -*- coding: utf-8 -*-
"""Los datos del mundo de la demo: ciudades reales, barrios reales, gustos plausibles.

Coordenadas de barrios REALES (brief §9): sin esto las distancias en km salen absurdas y la
columna de proximidad del score deja de significar nada. Un near-miss "por ciudad" tiene que
estar de verdad fuera del radio, no por casualidad.
"""

# barrio -> (lat, lon). Aproximadas al centro del barrio; el jitter determinista hace el resto.
CIUDADES = {
    "Berlin": {
        "Kreuzberg": (52.4986, 13.4033), "Mitte": (52.5200, 13.4050),
        "Prenzlauer Berg": (52.5400, 13.4200), "Neukolln": (52.4800, 13.4400),
        "Friedrichshain": (52.5150, 13.4540), "Charlottenburg": (52.5050, 13.3050),
        "Wedding": (52.5500, 13.3500), "Schoneberg": (52.4830, 13.3550),
        "Treptow": (52.4930, 13.4560), "Moabit": (52.5300, 13.3400),
    },
    "Dusseldorf": {
        "Flingern": (51.2300, 6.8000), "Altstadt": (51.2260, 6.7720),
        "Pempelfort": (51.2400, 6.7900), "Oberbilk": (51.2130, 6.7960),
        "Bilk": (51.2050, 6.7800), "Derendorf": (51.2480, 6.7860),
        "Unterbilk": (51.2140, 6.7700), "Gerresheim": (51.2280, 6.8720),
        "Oberkassel": (51.2320, 6.7530),
    },
    "Koln": {
        "Ehrenfeld": (50.9500, 6.9200), "Altstadt": (50.9380, 6.9600),
        "Sudstadt": (50.9200, 6.9500), "Nippes": (50.9660, 6.9500),
        "Deutz": (50.9370, 6.9750), "Sulz": (50.9160, 6.9250),
        "Kalk": (50.9410, 7.0040), "Lindenthal": (50.9280, 6.9020),
        "Ehrenfeld-Sued": (50.9440, 6.9160),
    },
    "Frankfurt": {
        "Bockenheim": (50.1230, 8.6400), "Sachsenhausen": (50.1000, 8.6800),
        "Nordend": (50.1290, 8.6870), "Bornheim": (50.1300, 8.7100),
        "Westend": (50.1200, 8.6600), "Ostend": (50.1150, 8.7050),
        "Gallus": (50.1050, 8.6350), "Riedberg": (50.1740, 8.6300),
    },
    "Munchen": {
        "Schwabing": (48.1650, 11.5860), "Maxvorstadt": (48.1500, 11.5670),
        "Haidhausen": (48.1300, 11.5950), "Glockenbach": (48.1290, 11.5700),
        "Sendling": (48.1180, 11.5400), "Neuhausen": (48.1550, 11.5350),
        "Giesing": (48.1120, 11.5830), "Bogenhausen": (48.1520, 11.6120),
        "Altstadt": (48.1370, 11.5750),
        # Donde esta el estadio: un plan de Bayern-Dortmund tiene que caer aqui, no en el centro.
        "Frottmaning": (48.2180, 11.6160),
    },
    # Vecinas: hacen que «Köln oder Umgebung» (frase 9) signifique algo medible.
    "Bonn":       {"Zentrum": (50.7340, 7.0980), "Beuel": (50.7420, 7.1250),
                   "Sudstadt": (50.7250, 7.0930)},
    "Leverkusen": {"Wiesdorf": (51.0300, 6.9800)},
    "Neuss":      {"Innenstadt": (51.2000, 6.6900)},
    # Destinos de viaje: dest_city != origin_city (frase 7).
    "Barcelona":  {"Gracia": (41.4020, 2.1560), "Eixample": (41.3900, 2.1620),
                   "El Born": (41.3840, 2.1820), "Barceloneta": (41.3790, 2.1900),
                   "Poble Sec": (41.3730, 2.1600), "Raval": (41.3800, 2.1690)},
    "Lissabon":   {"Alfama": (38.7120, -9.1300)},
    "Wien":       {"Neubau": (48.2020, 16.3500)},
    "Amsterdam":  {"Jordaan": (52.3760, 4.8830)},
    "Garmisch":   {"Partenkirchen": (47.4920, 11.0950)},
    "Rugen":      {"Binz": (54.4010, 13.6100)},
    "Madrid":     {"Malasana": (40.4260, -3.7030), "Lavapies": (40.4090, -3.7010)},
    # El lago de los muniqueses para una escapada de fin de semana (frase 10).
    "Tegernsee":  {"Rottach-Egern": (47.6900, 11.7700), "Gmund": (47.7480, 11.7350)},
}

CIUDADES_CLIENTE = ["Berlin", "Dusseldorf", "Koln", "Frankfurt", "Munchen"]

CATEGORIAS = ["concert", "football", "weekend_trip", "holiday", "restaurant", "activity"]

# Complementarias del §7: no se infieren, se declaran.
COMPLEMENTARIAS = [
    ("holiday", "weekend_trip"), ("holiday", "restaurant"),
    ("weekend_trip", "activity"), ("concert", "restaurant"), ("football", "restaurant"),
]

NOMBRES = [
    "Lena", "Jonas", "Mira", "Tobias", "Selin", "Kwame", "Anna", "Paul", "Yasmin", "Lukas",
    "Nora", "Emre", "Clara", "Finn", "Aisha", "David", "Marta", "Jakub", "Elif", "Ben",
    "Sofia", "Noah", "Amara", "Felix", "Hanna", "Deniz", "Julian", "Leyla", "Moritz", "Ines",
    "Tomasz", "Chiara", "Samir", "Greta", "Nils", "Zeynep", "Oskar", "Lucia", "Malik", "Rosa",
    "Henrik", "Nadia", "Bruno", "Alma", "Timo", "Farah", "Kilian", "Wanda", "Ravi", "Josefine",
    "Milan", "Thea", "Adem", "Frieda", "Levi", "Sara", "Anton", "Mina", "Piotr", "Johanna",
]

ARTISTAS = [
    "Burna Boy", "Coldplay", "Rosalia", "Wizkid", "Tems", "Peggy Gou", "Bad Bunny", "Adele",
    "Jorja Smith", "Fred again", "Amelie Lens", "Charlotte de Witte", "Arctic Monkeys",
    "AnnenMayKantereit", "Apache 207", "Nina Chuba", "Bonobo", "Little Simz", "Khruangbin",
    "Sampa the Great", "Kraftklub", "Sportfreunde Stiller", "Ayliva", "Cro",
]
GENEROS = ["afrobeats", "techno", "house", "indie", "hip_hop", "pop", "rock", "jazz",
           "electronic", "reggaeton", "soul", "classical"]

EQUIPOS = ["Bayern Munchen", "Borussia Dortmund", "1. FC Koln", "Fortuna Dusseldorf",
           "Eintracht Frankfurt", "Hertha BSC", "Union Berlin", "Bayer Leverkusen",
           "Borussia Monchengladbach", "VfB Stuttgart"]

COCINAS = ["italian", "japanese", "nigerian", "turkish", "vietnamese", "german", "levantine",
           "indian", "korean", "spanish", "greek", "ethiopian", "peruvian", "thai"]

INTERESES = [
    "live_music", "dancing", "football", "hiking", "cycling", "museums", "street_food",
    "wine", "craft_beer", "photography", "board_games", "running", "yoga", "climbing",
    "theatre", "cinema", "festivals", "cooking", "swimming", "art_galleries", "markets",
    "coffee", "vinyl", "stand_up_comedy", "kayaking", "birdwatching", "chess", "sailing",
]

PACE = ["relaxed", "moderate", "intense"]
BUDGET = ["low", "mid", "high"]
GRUPO = ["one_to_one", "small_group", "any"]

# Plantillas de bio. {i} intereses, {c} ciudad, {a} artista/equipo/cocina.
BIO_DE = [
    "Ich wohne seit ein paar Jahren in {c} und bin fast jedes Wochenende unterwegs. {i} sind mein Ding, und ich gehe lieber mit jemandem hin als allein. Spontan sein finde ich gut, solange man sich vorher kurz abspricht.",
    "Nach der Arbeit brauche ich Bewegung: {i}. In {c} kenne ich inzwischen die guten Ecken. Ich suche Leute, die etwas wirklich mogen und nicht nur mitkommen, weil gerade nichts anderes ansteht.",
    "{a} lauft bei mir rauf und runter. Sonst: {i}. Ich bin in {c} zu Hause und mag kleine Runden lieber als grosse Gruppen.",
    "Ich bin neu in {c} und will die Stadt uber Leute kennenlernen, nicht uber Listen. Am liebsten {i}. Ich frage viel und rede gern.",
    "Meine Freunde sagen, ich plane zu viel. Stimmt wahrscheinlich. {i} stehen fast immer im Kalender, und in {c} findet sich dafur immer was.",
]
BIO_EN = [
    "I moved to {c} a while ago and I still explore it like a visitor. Mostly {i}. I would rather go with one person than with a group of eight.",
    "Weekends are for {i}. I am not great at sitting still. If you actually like {a}, we will get along.",
    "I work a lot during the week, so {c} weekends matter. {i} above all. I prefer plans that are decided, not plans that dissolve in a group chat.",
    "Originally not from {c}, which means I say yes to things locals stopped doing years ago. {i} are my usual excuse to leave the flat.",
    "Quiet during the week, loud on Saturdays. {i}. I like meeting one person properly instead of a crowd briefly.",
]

TITULO_DE = {
    "concert": ["{a} live in {c}", "Konzertabend: {a}", "{a} - noch ein Platz frei"],
    "football": ["{a} im Stadion", "Spieltag in {c}", "{a} - Auswartsfahrt"],
    "weekend_trip": ["Wochenende in {d}", "Kurztrip nach {d}", "Zwei Tage {d}"],
    "holiday": ["Eine Woche {d}", "Urlaub in {d}", "Langer Aufenthalt in {d}"],
    "restaurant": ["Abendessen in {c}", "{a} essen gehen", "Tisch reserviert in {c}"],
    "activity": ["Wanderung bei {c}", "Radtour ab {c}", "Nachmittag im Museum, {c}"],
}
TITULO_EN = {
    "concert": ["{a} live in {c}", "Concert night: {a}", "{a} - one spare ticket"],
    "football": ["{a} at the stadium", "Matchday in {c}", "{a} - away trip"],
    "weekend_trip": ["Weekend in {d}", "Short trip to {d}", "Two days in {d}"],
    "holiday": ["A week in {d}", "Holiday in {d}", "Longer stay in {d}"],
    "restaurant": ["Dinner in {c}", "{a} food, {c}", "Table booked in {c}"],
    "activity": ["Hike near {c}", "Bike ride from {c}", "Afternoon at the museum, {c}"],
}
DESC_DE = [
    "Ich habe noch einen Platz frei und wurde ungern allein hingehen. Wer Lust hat, meldet sich einfach.",
    "Alles ist schon gebucht. Ich suche jemanden, der wirklich Lust darauf hat und nicht nur mitlauft.",
    "Kein grosses Programm, aber ein guter Abend. Ich freue mich uber Gesellschaft.",
    "Der Plan steht seit Wochen. Meine Begleitung ist ausgefallen, der Platz ist frei.",
]
DESC_EN = [
    "One spot is open and I would rather not go alone. Message me if this sounds like your evening.",
    "Everything is already booked. I am looking for someone who actually wants to be there.",
    "Nothing fancy, just a good plan with one seat left.",
    "Planned this weeks ago. The person coming with me cancelled, so the place is free.",
]


# ══════════════════════════════════════════════════════════════════════════════════════════
# COCHE COMPARTIDO (11-sep-2026) — lo que pide `pickando.docx`
# ══════════════════════════════════════════════════════════════════════════════════════════
#
# «This app is to be used privately by anyone on the way to work, shopping, etc.»
# El mundo de la demo necesita dos clases de trayecto, y las dos salen de aqui:
#
#   * el de diario   — Kreuzberg → Mitte a las 8:10, de lunes a viernes
#   * el del evento  — Berlin → el estadio de Munich el sabado
#
# El segundo es el que hace que las 10 frases de Helder sigan devolviendo resultados: el
# destino del trayecto ES el plan. Un conductor que va al Bayern-Dortmund y lleva dos plazas
# libres es, a la vez, el resultado de «busco a alguien que vaya al partido» y un viaje.

COCHES = [
    "VW Golf · gris", "Skoda Octavia · azul", "Opel Corsa · blanco", "Ford Focus · negro",
    "Toyota Yaris · rojo", "Renault Clio · gris", "Seat Leon · blanco", "BMW 1er · negro",
    "Audi A3 · plata", "Mazda 3 · azul", "Hyundai i30 · blanco", "Fiat 500 · verde",
    "Peugeot 208 · gris", "Kia Ceed · azul", "Nissan Leaf · blanco", "Tesla Model 3 · negro",
    "VW ID.3 · azul", "Dacia Sandero · gris", "Citroen C3 · rojo", "Mini Cooper · verde",
]

# Corredores reales de cada ciudad: (barrio de salida, [barrios por los que pasa], barrio destino).
# Los `via` son lo que convierte «dos puntos» en «una ruta»: el pasajero de en medio solo existe
# si la ruta pasa por su barrio. Es literalmente el requisito del docx — «tracking within 1-2 km
# of all drivers driving on the same route».
CORREDORES = {
    "Berlin": [
        ("Neukolln", ["Kreuzberg"], "Mitte"),
        ("Friedrichshain", ["Kreuzberg"], "Schoneberg"),
        ("Prenzlauer Berg", ["Mitte"], "Charlottenburg"),
        ("Wedding", ["Moabit"], "Mitte"),
        ("Treptow", ["Friedrichshain"], "Prenzlauer Berg"),
        ("Charlottenburg", ["Moabit"], "Mitte"),
    ],
    "Dusseldorf": [
        ("Bilk", ["Unterbilk"], "Altstadt"),
        ("Gerresheim", ["Flingern"], "Pempelfort"),
        ("Oberbilk", ["Flingern"], "Derendorf"),
        ("Oberkassel", ["Altstadt"], "Pempelfort"),
    ],
    "Koln": [
        ("Kalk", ["Deutz"], "Altstadt"),
        ("Ehrenfeld", ["Nippes"], "Altstadt"),
        ("Sulz", ["Sudstadt"], "Altstadt"),
        ("Lindenthal", ["Ehrenfeld"], "Nippes"),
    ],
    "Frankfurt": [
        ("Bornheim", ["Nordend"], "Westend"),
        ("Sachsenhausen", ["Ostend"], "Bornheim"),
        ("Riedberg", ["Bockenheim"], "Gallus"),
        ("Gallus", ["Bockenheim"], "Westend"),
    ],
    "Munchen": [
        ("Giesing", ["Haidhausen"], "Maxvorstadt"),
        ("Sendling", ["Glockenbach"], "Altstadt"),
        ("Bogenhausen", ["Haidhausen"], "Altstadt"),
        ("Neuhausen", ["Maxvorstadt"], "Altstadt"),
    ],
}

# El motivo del trayecto. `commute` y `errands` son los dos que nombra el docx por su nombre;
# el resto salen del mundo que ya existia.
MOTIVOS_TRAYECTO = ["commute", "commute", "commute", "errands", "nightlife", "gym"]

TITULO_TRAYECTO_DE = [
    "{o} → {d}, {h}",
    "Fahrt nach {d} um {h}",
    "{o} raus, {d} rein — {h}",
    "Jeden Morgen {o} → {d}",
]
TITULO_TRAYECTO_EN = [
    "{o} → {d}, {h}",
    "Driving to {d} at {h}",
    "{o} to {d} — {h}",
    "Same run every morning: {o} → {d}",
]
DESC_TRAYECTO_DE = [
    "Ich fahre die Strecke sowieso. Wer unterwegs mitkommen will, sagt kurz Bescheid.",
    "Feste Zeit, feste Strecke. Ich halte nur da, wo ich ohnehin an der Ampel stehe.",
    "Musik leise, Fenster auf. Zwei Plaetze sind frei, Sprit teilen wir uns.",
    "Ich nehme gern jemanden mit, der puenktlich ist. Umwege mache ich keine grossen.",
]
DESC_TRAYECTO_EN = [
    "I drive this route anyway. Say the word and I will stop where I already stop.",
    "Fixed time, fixed route. I do not do big detours, but I pass close to a lot of places.",
    "Two seats free, we split the fuel. Quiet in the morning, talkative on the way back.",
    "Same run most days. Happy to take someone who is on time.",
]

# Rese~nas de conductor. El docx pide «driver rating & review»; una nota sin frases es un numero
# sin prueba, y lo que convence a un pasajero es leer a otra persona.
RESENAS_DE = [
    "Puenktlich, ruhige Fahrweise, angenehmes Gespraech. Gerne wieder.",
    "Hat genau da gehalten, wo es abgesprochen war. Sehr entspannt.",
    "Faehrt sicher und haelt sich an die Zeit. Auto war sauber.",
    "Nette Fahrt, gute Musik, kein Stress im Berufsverkehr.",
    "Kurz verspaetet, aber vorher Bescheid gesagt. Alles gut.",
    "Sehr hilfsbereit, hat mir mit dem Gepaeck geholfen.",
    "Gute Kommunikation vorab. Man weiss genau, woran man ist.",
]
RESENAS_EN = [
    "On time, calm driver, easy conversation. Would ride again.",
    "Stopped exactly where we agreed. Very relaxed.",
    "Drives safely and keeps to the time. Clean car.",
    "Good music, no stress in rush hour traffic.",
    "Ran a few minutes late but messaged first. No problem at all.",
    "Helped me with my bag without being asked.",
    "Clear communication before the trip. You know exactly what to expect.",
]

# Tarifa: el docx pide «price should be calculated per km» con min y max configurables.
# Estos son los limites que la demo ense~na, y son los de una app de gastos compartidos
# alemana, no los de un taxi: no se gana dinero, se reparte el combustible.
PRECIO_KM_MIN = 0.05   # EUR/km
PRECIO_KM_MAX = 0.15
