"""Contratos de schema do hubspot-service.

Padrão do time: dataclasses como contrato entre o Lambda e o pipeline.
Todos os valores de propriedade chegam da API v3 como string (ou None);
tipagem forte acontece na camada dbt, não aqui.
"""

from __future__ import annotations
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Any
from constants.properties import OBJECT_CONFIG

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class HubspotRow:
    """Registro generico de um objeto do Hubspot"""
    id: str
    object_type: str
    properties: dict[str, str | None]
    associations: dict[str, list[str]] = field(default_factory=dict)
    load_ts: str = field(default_factory=_utc_now_iso)

    @classmethod
    def from_api_record(
        cls,
        object_type: str,
        record: dict[str, Any],
        flat_associations: dict[str, list[str]] | None = None,
    ) -> "HubspotRow":
        expected = set(OBJECT_CONFIG[object_type]["properties"])
        raw_props = record.get("properties", {}) or {}
        props = {k: raw_props.get(k) for k in expected}
        return cls(
            id=str(record["id"]),
            object_type=object_type,
            properties=props,
            associations=flat_associations or {},
        )
    def to_flat_dict(self) -> dict[str, Any]:
        """Formato serializado devolvido ao pipeline"""
        row: dict[str, Any] = {"id": self.id, "load_ts": self.load_ts}
        row.update(self.properties)
        for assoc_type, ids in self.associations.items():
            row[f"associated_{assoc_type}"] = ";".join(ids)
        return row

@dataclass
class ExtractionPage:
    """Bloco de extração devolvido por invocação — contrato de resposta.

    O pipeline itera reinvocando o Lambda com `after=next_after`
    até `next_after` vir null.
    """
    object_type: str
    records: list[dict[str, Any]]
    record_count: int
    pages: int
    next_after: str | None
    started_at: str
    finished_at: str

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass
class BatchResult:
    """Resultado de uma carga em lote (create/update/upsert) no HubSpot."""
    object_type: str
    action: str
    total_sent: int
    total_succeeded: int
    total_failed: int
    errors: list[dict[str, Any]] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

