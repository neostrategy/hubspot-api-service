"""Carga de objetos no HubSpot (batch create/update/upsert, API v3).

O pipeline envia os registros na invocação e o Lambda cadastra.
Lotes são fatiados em blocos de 100 (limite dos endpoints batch).

Formatos de entrada (campo `records` do evento):
    create:  [{"properties": {...}}, ...]
    update:  [{"id": "123", "properties": {...}}, ...]
    upsert:  [{"id": "a@b.com", "properties": {...}}, ...]
             + id_property (ex.: "email" para contacts)

Nota de idempotência: create NÃO é idempotente — um retry após timeout
pode duplicar registros. Preferir upsert (contacts por email) ou update
sempre que houver chave. Ver comentário em core/hubspot_client.py.
"""
import logging
from core.hubspot_client import HubspotClient
from domain.schemas import BatchResult

log = logging.getLogger(__name__)

BATCH_SIZE = 100
WRITABLE_OBJECTS = {"contacts", "deals"}

class LoaderService:
    def __init__(self, client: HubspotClient):
        self.client = client

    def batch_write(
            self,
            action: str,
            object_type: str,
            records: list[dict],
            id_property: str | None = None,
    ) -> BatchResult:
        
        if object_type not in WRITABLE_OBJECTS:
            raise ValueError(f"Carga não suportada para {object_type!r}."               
                             f"Objetos graváveis: {sorted(WRITABLE_OBJECTS)}")
        if action not in ("create", "upsert", "update"):
            raise ValueError(f"action de carga inválida: {action!r}")
        if action == "upsert" and not id_property:
            raise ValueError("upsert exige id_property (ex.: 'email' para contacts)")
        if not records:
            raise ValueError("records vazio")

        self._validate_records(action, records)

        path = f"/crm/v3/objects/{object_type}/batch/{action}"

        result = BatchResult(
            object_type=object_type,
            action=action,
            total_sent=len(records),
            total_succeeded=0,
            total_failed=0,
        )

        for start in range(0, len(records), BATCH_SIZE):
            chunk = records[start:start + BATCH_SIZE]
            inputs = self._build_inputs(action, chunk, id_property)

            try:
                status, body = self.client.post_batch(path, {"inputs": inputs})
            except Exception as exc:
                log.error("[%s] Lote %d-%d falhou: %s", object_type, start, start + len(chunk), exc)
                result.total_failed += len(chunk)
                result.errors.append({
                    "range": [start, start + len(chunk)],
                    "error": str(exc),
                })
                continue
            batch_results = body.get("results", [])
            batch_errors = body.get("errors", [])

            # 207 Multi-Status: sucesso parcial dentro do lote
            succeeded = len(batch_results)
            failed = len(chunk) - succeeded
            result.total_succeeded += succeeded
            result.total_failed += max(failed, 0)
            result.results.extend(
                {"id": r.get("id")} for r in batch_results
            )
            if batch_errors:
                result.errors.extend(batch_errors)
            log.info("[%s] %s lote %d-%d: HTTP %d, %d ok, %d falhas", object_type, action, start, start + len(chunk), status, succeeded, max(failed, 0))
        log.info("[%s] %s concluído: %d enviados, %d ok, %d falhas", object_type, action, result.total_sent, result.total_succeeded, result.total_failed)
        
        return result
    
    @staticmethod
    def _validate_records(action: str, records: list[dict]) -> None:
        for i, rec in enumerate(records):
            if "properties" not in rec or not isinstance(rec["properties"], dict):
                raise ValueError(f"records[{i}]: campo 'properties' (dict) é obrigatório")
            if action in ("update", "upsert") and not rec.get("id"):
                raise ValueError(f"records[{i}]: campo 'id' é obrigatório para {action}")

    @staticmethod
    def _build_inputs(
        action: str,
        chunk: list[dict],
        id_property: str | None,
    ) -> list[dict]:
        if action == "create":
            return [{"properties": r["properties"]} for r in chunk]
        if action == "update":
            return [{"id": str(r["id"]), "properties": r["properties"]} for r in chunk]
        # upsert
        return [
            {
                "idProperty": id_property,
                "id": str(r["id"]),
                "properties": r["properties"],
            }
            for r in chunk
        ]