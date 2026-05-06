"""
Vistas del Recolector de Inventarios.

Endpoints:
  GET /api/recolector/businesses/{id}/USDConsumption   → Postgres
  GET /api/recolector/businesses/{id}/CloudGovernance  → Postgres
  GET /api/recolector/businesses/{id}/S3Usage          → MongoDB
  GET /api/recolector/businesses/{id}/EC2Usage         → MongoDB

Query params opcionales:
  /USDConsumption?month=2026-05   → filtra por mes
"""
import uuid

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .services import (
    USDConsumptionService,
    CloudGovernanceService,
    S3UsageService,
    EC2UsageService,
)


def _parse_business_id(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# PostgreSQL endpoints
# ---------------------------------------------------------------------------

class USDConsumptionView(APIView):
    """
    GET /api/recolector/businesses/{id}/USDConsumption
    Retorna el gasto mensual en USD para un negocio.

    Query params:
      ?month=2026-05   (opcional) filtra por mes
    """

    def get(self, request, business_id: str):
        bid = _parse_business_id(business_id)
        if bid is None:
            return Response({'error': 'business_id no es un UUID válido.'},
                            status=status.HTTP_400_BAD_REQUEST)

        month_year = request.query_params.get('month')  # e.g. '2026-05'

        try:
            data = USDConsumptionService().get(bid, month_year)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
        except LookupError as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'business_id': business_id,
            'consumption': data,
        })


class CloudGovernanceView(APIView):
    """
    GET /api/recolector/businesses/{id}/CloudGovernance
    Retorna tags obligatorios, responsable y límites de gasto por proyecto.
    """

    def get(self, request, business_id: str):
        bid = _parse_business_id(business_id)
        if bid is None:
            return Response({'error': 'business_id no es un UUID válido.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            data = CloudGovernanceService().get(bid)
        except (ValueError, LookupError) as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'business_id': business_id,
            'governance':  data,
        })


# ---------------------------------------------------------------------------
# MongoDB endpoints
# ---------------------------------------------------------------------------

class S3UsageView(APIView):
    """
    GET /api/recolector/businesses/{id}/S3Usage
    Retorna uso y métricas de desperdicio de buckets S3 desde MongoDB.
    """

    def get(self, request, business_id: str):
        bid = _parse_business_id(business_id)
        if bid is None:
            return Response({'error': 'business_id no es un UUID válido.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            data = S3UsageService().get(bid)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
        except LookupError as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        return Response(data)


class EC2UsageView(APIView):
    """
    GET /api/recolector/businesses/{id}/EC2Usage
    Retorna uso, logs de uptime y sugerencias de optimización de instancias EC2.
    """

    def get(self, request, business_id: str):
        bid = _parse_business_id(business_id)
        if bid is None:
            return Response({'error': 'business_id no es un UUID válido.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            data = EC2UsageService().get(bid)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
        except LookupError as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        return Response(data)