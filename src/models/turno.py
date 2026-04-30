TURNOS = [
    {'id': 'matutino', 'nome': 'Matutino'},
    {'id': 'vespertino', 'nome': 'Vespertino'},
    {'id': 'noturno', 'nome': 'Noturno'},
]

DEFAULT_TURNO = 'matutino'
TURNO_IDS = {turno['id'] for turno in TURNOS}


def normalizar_turno(turno):
    turno = (turno or '').strip().lower()
    return turno if turno in TURNO_IDS else DEFAULT_TURNO
