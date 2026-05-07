"""Helpers compartidos por los scripts de experimento."""
import json
import os
import sys


BASE_URL    = os.environ.get('BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
DEFAULT_BID = os.environ.get(
    'EXPERIMENT_BUSINESS_ID',
    '11111111-1111-1111-1111-111111111111',  # Universidad de los Andes (seed)
)


def url(path: str) -> str:
    return f'{BASE_URL}{path}'


def emit(name: str, payload: dict) -> None:
    """Imprime un evento del experimento como JSON line — fácil de parsear."""
    out = {'event': name, **payload}
    print(json.dumps(out, default=str), flush=True)


def fail(reason: str, **extra) -> 'NoReturn':
    emit('FAIL', {'reason': reason, **extra})
    sys.exit(1)


def ok(reason: str, **extra) -> 'NoReturn':
    emit('PASS', {'reason': reason, **extra})
    sys.exit(0)
