"""Extração paginada de objetos do HubSpot CRM (API v3).

Devolve blocos de páginas com cursor (`next_after`) para o pipeline
iterar — a resposta síncrona de Lambda tem limite de 6 MB, então não
tentamos devolver o dataset inteiro numa invocação.

Logs registram apenas contagens e cursores — nunca payloads
(propriedades de contato contêm PII / LGPD).
"""

import logging
from datetime import datetime, timezone
from constants.properties import OBJECT_CONFIG
from core.hubspot_client import HubspotClient
from domain.schemas import ExtractionPage, HubspotRow
from utils.flatten import flatten_associations

log = logging.getLogger(__name__)

PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 10  # 1.000 registros/invocação; margem folgada sob os 6 MB

class ExtractorService:
    def __init__(self, client: HubspotClient):
        self.client = client

    def extract_pages(
            self,
            object_type: str,
            after: str | None = None,
            max_pages = DEFAULT_MAX_PAGES,
            properties: list[str] | None = None,
            associations: list[str] | None = None,
    ) -> ExtractionPage:
        if object_type not in OBJECT_CONFIG:
            raise ValueError(f"object_type inválido: {object_type!r}. "
                             f"Esperado em de {sorted(OBJECT_CONFIG)}")

        config = OBJECT_CONFIG[object_type]
        properties = properties or config["properties"]
        associations = associations if associations is not None else config["associations"]

        started_at = datetime.now(timezone.utc).isoformat()
        records: list[dict] = []
        pages = 0

        while pages < max_pages:
            params: dict = {
                "limit": PAGE_SIZE,
                "properties": ",".join(properties),
                "archived": "false",
            }
            if associations:
                params["associations"] = ",".join(associations)
            if after:
                params["after"] = after

            pages += 1
            log.info("[%s] Buscando página %d (after=%s)...", object_type, pages, after)
            data = self.client.get(f"/crm/v3/objects/{object_type}", params=params)

            for record in data.get("results", []):
                row = HubspotRow.from_api_record(
                    object_type,
                    record,
                    flatten_associations(record.get("associations", {})),
                )
                records.append(row.to_flat_dict())
            after = data.get("paging", {}).get("next", {}).get("after")
            if not after:
                break

            log.info("[%s] Bloco concluído: %d registros em %d páginas (next_after=%s)", object_type, len(records), after)

            return ExtractionPage(
                object_type=object_type,
                records=records,
                record_count=len(records),
                pages=pages,
                next_after=after,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
            )