"""Handler Lambda do hubspot-service.

Padrão request/response síncrono, igual ao cnpj-api-service: o flow
pipeline-leads-hubspot (exemplo) invoca o Lambda e recebe o JSON na resposta —
persistência é responsabilidade do pipeline.

CONTRATO (validar contra o doc "API Mapping — hubspot-service"):

Extração (o pipeline itera com o cursor até next_after == null):
    {
        "action": "extract",
        "object_type": "contacts",
        "after": "<cursor|omitido na 1a chamada>",
        "max_pages": 10,                # opcional
        "properties": [...],            # opcional
        "associations": [...]           # opcional
    }
    -> body: {object_type, records, record_count, pages, next_after, ...}

Extração incremental (mesmo contrato de resposta do extract):
    {
        "action": "search",
        "object_type": "deals",
        "since": "2026-07-27T00:00:00Z",   # ou epoch em ms (watermark)
        "after": "<cursor|omitido na 1a chamada>",
        "max_pages": 10,                    # opcional
        "properties": [...]                 # opcional
    }
    Observações: máx. 10.000 resultados por janela de since (fatiar no
    pipeline); Search API não devolve associations.

Carga (contacts e deals):
    {
        "action": "create" | "update" | "upsert",
        "object_type": "contacts",
        "records": [{"id": "...", "properties": {...}}, ...],
        "id_property": "email"          # obrigatório só no upsert
    }
    -> body: {total_sent, total_succeeded, total_failed, errors, results}

Variáveis de ambiente:
    HUBSPOT_TOKEN -> private app token, definido como env var do Lambda
                     via SAM (sem Secrets Manager para não gerar custo)
"""
import json
import logging 
import os
from core.hubspot_client import HubspotClient
from services.extractor import ExtractorService
from services.loader import LoaderService

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger(__name__)

WRITE_ACTIONS = ("create", "update", "upsert")

def handler(event: dict, context) -> dict:
    action = event.get("action", "extract")
    object_type = event.get("object_type")

    if not object_type:
        return _response(400, {"error": "object_type é obrigatório"})
    client = HubspotClient(token=os.environ["HUBSPOT_TOKEN"])

    try:
        if action == "extract":
            page = ExtractorService(client).extract_pages(
                object_type=object_type,
                after=event.get("after"),
                max_pages=int(event.get("max_pages", 10)),
                properties=event.get("properties"),
                associations=event.get("associations"),
            )
            return _response(200, page.to_dict())
        if action == "search":
            since = event.get("since")
            if not since:
                return _response(400, {"error": "since é obrigatório para search "
                                                "(epoch ms ou ISO 8601)"})
            page = ExtractorService(client).search_pages(
                object_type=object_type,
                since=since,
                after=event.get("after"),
                max_pages=int(event.get("max_pages", 10)),
                properties=event.get("properties"),
            )
            return _response(200, page.to_dict())
        if action in WRITE_ACTIONS:
            result = LoaderService(client).batch_write(
                action=action,
                object_type=object_type,
                records=event.get("records", []),
                id_property=event.get("id_property"),
            )
            status = 200 if result.total_failed == 0 else 207
            return _response(status, result.to_dict())
        
        return _response(400, {"error": f"action não suportada: {action!r}"})
    except ValueError as exc:
        return _response(400, {"error": str(exc)})

def _response(status_code: int, body: dict) -> dict:
    return {"statusCode": status_code, "body": json.dumps(body, ensure_ascii=False)}