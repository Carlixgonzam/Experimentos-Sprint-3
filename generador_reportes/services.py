"""
Lógica de negocio del Generador de Reportes.
Orquesta la obtención de datos desde el RecolectorInventarios
y los concatena en un payload JSON estructurado para el frontend.
"""


class ReportGeneratorService:
    """
    Responsable de:
    - Solicitar datos a recolector_inventarios (Postgres y Mongo).
    - Normalizar y combinar ambas fuentes.
    - Retornar un dict serializable a JSON.
    """

    def generate_full_inventory_report(self) -> dict:
        """
        Combina datos de Postgres y Mongo en un único JSON de inventario.

        Estructura esperada del reporte:
        {
            "meta": {"generated_at": ..., "sources": ["postgres", "mongo"]},
            "postgres": [...],
            "mongo": [...],
            "combined": [...]    # lógica de merge a definir
        }
        """
        postgres_data = self._fetch_from_postgres()
        mongo_data = self._fetch_from_mongo()

        # TODO: implementar lógica de merge / join entre ambas fuentes
        return {
            "meta": {
                "generated_at": None,  # TODO: datetime.utcnow().isoformat()
                "sources": ["postgres", "mongo"],
            },
            "postgres": postgres_data,
            "mongo": mongo_data,
            "combined": [],
        }

    def _fetch_from_postgres(self) -> list:
        """Delega al RecolectorInventarios para obtener datos de Postgres."""
        # TODO: importar y llamar recolector_inventarios.services.PostgresCollector
        raise NotImplementedError

    def _fetch_from_mongo(self) -> list:
        """Delega al RecolectorInventarios para obtener datos de Mongo."""
        # TODO: importar y llamar recolector_inventarios.services.MongoCollector
        raise NotImplementedError
