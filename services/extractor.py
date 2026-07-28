"""Extração paginada de objetos do HubSpot CRM (API v3).

Devolve blocos de páginas com cursor (`next_after`) para o pipeline
iterar — a resposta síncrona de Lambda tem limite de 6 MB, então não
tentamos devolver o dataset inteiro numa invocação.

Logs registram apenas contagens e cursores — nunca payloads
(propriedades de contato contêm PII / LGPD).
"""

import logging
from datetime import datetime, timezone
from constants.properties import (
    OBJECT_CONFIG,
    LASTMODIFIED_PROPERTY,
    DEFAULT_LASTMODIFIED,
)
from core.hubspot_client import HubspotClient
from domain.schemas import ExtractionPage, HubspotRow
from utils.flatten import flatten_associations

log = logging.getLogger(__name__)

PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 10  # 1.000 registros/invocação; margem folgada sob os 6 MB
SEARCH_RESULT_CAP = 10_000  # limite da Search API por consulta (fatiar janelas acima disso)

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

        log.info(
            "[%s] Bloco concluído: %d registros em %d páginas (next_after=%s)",
            object_type, len(records), pages, after,
        )

        return ExtractionPage(
            object_type=object_type,
            records=records,
            record_count=len(records),
            pages=pages,
            next_after=after,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )

    def search_pages(
            self,
            object_type: str,
            since,
            after: str | None = None,
            max_pages: int = DEFAULT_MAX_PAGES,
            properties: list[str] | None = None,
    ) -> ExtractionPage:
        """Extração incremental via Search API (POST /search).

        Devolve apenas registros com última modificação >= `since`
        (ISO 8601 ou epoch em ms), ordenados por data de modificação
        ascendente — o pipeline avança o watermark com segurança a
        partir do último registro do bloco.

        Limitações da Search API (documentadas, não contornáveis aqui):
          * máx. 10.000 resultados por consulta — acima disso o pipeline
            deve fatiar a janela de `since` (um warning é logado);
          * não devolve `associations` — buscar via API v4 para os IDs
            alterados, se necessário.
        """
        if object_type not in OBJECT_CONFIG:
            raise ValueError(f"object_type inválido: {object_type!r}. "
                             f"Esperado em {sorted(OBJECT_CONFIG)}")

        properties = properties or OBJECT_CONFIG[object_type]["properties"]
        lastmod = LASTMODIFIED_PROPERTY.get(object_type, DEFAULT_LASTMODIFIED)
        since_ms = _to_epoch_ms(since)

        started_at = datetime.now(timezone.utc).isoformat()
        records: list[dict] = []
        pages = 0
        total_reported: int | None = None

        while pages < max_pages:
            body: dict = {
                "filterGroups": [{
                    "filters": [{
                        "propertyName": lastmod,
                        "operator": "GTE",
                        "value": str(since_ms),
                    }],
                }],
                "sorts": [{"propertyName": lastmod, "direction": "ASCENDING"}],
                "properties": properties,
                "limit": PAGE_SIZE,
            }
            if after:
                body["after"] = after

            pages += 1
            log.info("[%s] Search página %d (since=%s, after=%s)...",
                     object_type, pages, since_ms, after)
            _, data = self.client.post_batch(
                f"/crm/v3/objects/{object_type}/search", body,
            )

            if total_reported is None:
                total_reported = data.get("total")
                if total_reported and total_reported > SEARCH_RESULT_CAP:
                    log.warning(
                        "[%s] Search reporta %d resultados (> cap de %d). "
                        "Fatiar a janela de since no pipeline.",
                        object_type, total_reported, SEARCH_RESULT_CAP,
                    )

            for record in data.get("results", []):
                row = HubspotRow.from_api_record(object_type, record, {})
                records.append(row.to_flat_dict())

            after = data.get("paging", {}).get("next", {}).get("after")
            if not after:
                break

        log.info(
            "[%s] Search concluído: %d registros em %d páginas "
            "(total na janela=%s, next_after=%s)",
            object_type, len(records), pages, total_reported, after,
        )

        return ExtractionPage(
            object_type=object_type,
            records=records,
            record_count=len(records),
            pages=pages,
            next_after=after,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )


def _to_epoch_ms(since) -> int:
    """Aceita epoch em ms (int ou string numérica) ou ISO 8601."""
    if isinstance(since, int):
        return since
    if isinstance(since, str):
        raw = since.strip()
        if raw.isdigit():
            return int(raw)
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    raise ValueError(f"since inválido: {since!r} (esperado epoch ms ou ISO 8601)")