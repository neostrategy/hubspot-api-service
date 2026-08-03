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

    BATCH_SIZE = 100  # limite do endpoint batch/read da API v4

    def read_batch(
            self,
            from_object: str,
            to_object: str,
            ids: list[str],
    ) -> list[dict]:
        """Resolve associações de vários registros de uma vez (API v4 batch).

        POST /crm/v4/associations/{from}/{to}/batch/read, em blocos de 100.
        Devolve uma linha achatada por par associado:
            {"from_id": "...", "to_id": "...", "type": "..."}

        Usado pelo pipeline analítico: a Search API (incremental) não
        devolve associações, então o flow chama esta action com os IDs
        que vieram alterados na janela.
        """
        if not ids:
            return []

        pares: list[dict] = []
        for start in range(0, len(ids), self.BATCH_SIZE):
            chunk = ids[start:start + self.BATCH_SIZE]
            body = {"inputs": [{"id": str(i)} for i in chunk]}
            try:
                _, data = self.client.post_batch(
                    f"/crm/v4/associations/{from_object}/{to_object}/batch/read",
                    body,
                )
            except Exception as exc:
                log.warning(
                    "Erro no batch de associações %s -> %s (%d ids): %s",
                    from_object, to_object, len(chunk), exc,
                )
                continue

            for resultado in data.get("results", []):
                from_id = str(resultado.get("from", {}).get("id", ""))
                for alvo in resultado.get("to", []):
                    tipos = alvo.get("associationTypes", [])
                    primeiro = tipos[0] if tipos else {}
                    pares.append({
                        "from_id": from_id,
                        "to_id": str(alvo.get("toObjectId", "")),
                        "type": primeiro.get("label"),
                        "type_id": primeiro.get("typeId"),
                        "category": primeiro.get("category"),
                    })

        log.info(
            "[assoc] %s -> %s: %d pares para %d ids",
            from_object, to_object, len(pares), len(ids),
        )
        return pares
