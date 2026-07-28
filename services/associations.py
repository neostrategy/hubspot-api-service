"""Consulta e atualização de associações entre objetos (API v4)."""
import logging
from core.hubspot_client import HubspotClient

log = logging.getLogger(__name__)

class AssociationsServices:
    def __init__(self, client: HubspotClient):
        self.client = client

    def get_current_associations(
            self,
            from_object: str,
            from_id: str,
            to_object: str,
    ) -> list[str]:
        try:
            data = self.client.get(
                  f"/crm/v4/objects/{from_object}/{from_id}/associations/{to_object}"
            )
            return [str(r["toObjectId"]) for r in data.get("results", [])]
        except Exception as exc:
            log.warning(
                "Erro ao buscar associações de %s %s -> %s: %s",
                from_object, from_id, to_object, exc,
            )
            return []
