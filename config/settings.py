# config/settings.py
import os

DB_NAME = "bitacora_d5.db"

# ─────────────────────────────────────────────────────────────────────
# EDIFICIOS Y LABORATORIOS
# Para agregar un nuevo edificio o laboratorio, solo edita este
# diccionario — el resto de la app lo detecta automáticamente.
# ─────────────────────────────────────────────────────────────────────
EDIFICIOS = {
    "D5": ["104", "204", "211", "212"],
    "K5": ["101", "102", "106", "107", "108"],
}

# Lista plana de todos los laboratorios (usada en filtros y sidebar)
LABORATORIOS = [lab for labs in EDIFICIOS.values() for lab in labs]

# Lista de todos los edificios disponibles
EDIFICIOS_LISTA = list(EDIFICIOS.keys())

TURNOS = ["Matutino", "Vespertino"]
HORARIO_APERTURA = "07:00"
HORARIO_CIERRE   = "21:00"

ASIGNATURAS = [
    "Programación Orientada a Objetos",
    "Programación Web",
    "Bases de Datos",
    "Redes de Computadoras",
    "Sistemas Operativos",
    "Ingeniería de Software",
    "Inteligencia Artificial",
    "Seguridad Informática",
    "Arquitectura de Computadoras",
    "Desarrollo de Aplicaciones Móviles",
    "Cómputo en la Nube",
    "Taller de Programación",
    "Fundamentos de Programación",
    "Algoritmos y Estructuras de Datos",
    "Otra (especificar en Tema)",
]

KEYWORDS_FALLA = [
    "falla", "roto", "no sirve", "internet", "red", "lento", "virus",
    "pantalla", "cable", "no arranca", "quemado", "descompuesto",
    "mouse", "teclado", "no enciende", "no prende", "se apaga", "bloqueada",
    "computadora", "equipo", "monitor", "software", "licencia", "ruido",
    "error", "no funciona", "cuelga", "problema",
]
