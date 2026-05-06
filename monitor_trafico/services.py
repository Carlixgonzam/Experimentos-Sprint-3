"""
Lógica de negocio del Monitor de Tráfico.
Desacoplado del middleware para facilitar testing.
"""


class TrafficMonitorService:
    """
    Encapsula la lógica de:
    - Registro de peticiones
    - Detección de umbrales (rate limiting)
    - Bloqueo y desbloqueo de IPs
    """

    # TODO: mover a settings.py o a un modelo de configuración
    REQUEST_THRESHOLD = 100       # peticiones máximas
    TIME_WINDOW_SECONDS = 60      # en este intervalo de tiempo

    def is_blocked(self, ip_address: str) -> bool:
        """Retorna True si la IP tiene un bloqueo activo."""
        # TODO: implementar consulta a BlockedIP
        raise NotImplementedError

    def log_request(self, ip_address: str, path: str, method: str,
                    status_code: int, user_agent: str) -> None:
        """Persiste un RequestLog en base de datos."""
        # TODO: guardar RequestLog; considerar escritura asíncrona (Celery / threading)
        raise NotImplementedError

    def evaluate_ip(self, ip_address: str) -> bool:
        """
        Evalúa si la IP supera el umbral en la ventana de tiempo.
        Retorna True si se procedió a bloquearla.
        """
        # TODO: contar RequestLog por IP en la ventana temporal
        # TODO: si supera el umbral, crear/activar BlockedIP
        raise NotImplementedError

    def unblock_ip(self, ip_address: str) -> None:
        """Desactiva el bloqueo de una IP manualmente."""
        # TODO: implementar
        raise NotImplementedError
