from typing import Any

def flatten_associations(associations: dict[str, Any]) -> dict[str, list[str]]:
    """Achata o bloco `associations` da API v3 em {tipo: [ids]}.

    Entrada (API v3):
        {"companies": {"results": [{"id": "123", "type": "..."}, ...]}}
    Saída:
        {"companies": ["123", ...]}
    """
    flat: dict[str, list[str]] = {}
    for assoc_type, payload in (associations or {}).items():
        results = (payload or {}).get("results", [])
        ids = [str(r["id"]) for r in results if r.get("id") is not None]
        if ids:
            flat[assoc_type] = ids
    return flat