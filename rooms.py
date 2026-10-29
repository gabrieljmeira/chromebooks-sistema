"""Salas autorizadas pela escola, em ordem numérica."""

ROOMS = (
    "101", "103", "105", "106", "107", "108", "109", "111", "113", "114", "115", "116",
    "201", "203", "205", "206", "207", "208", "209", "210", "211", "212", "213", "214", "215",
)


def room_name(value):
    return "214 — Sala de música" if str(value) == "214" else str(value)
