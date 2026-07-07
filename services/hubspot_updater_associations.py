from core.hubspot_client import HubspotClient
from datetime import datetime
from pathlib import Path
import logging

timestamp_run = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = Path(f"hubspot_associations_{timestamp_run}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding="utf-8",)
    ],
)
log = logging.getLogger("hubspot_associations")


def get_current_associations(
        client: HubspotClient,
        from_object: str,
        from_id: str,
        to_object: str
) -> list:
    try:
        data = client.get(f"/crm/v4/objects/{from_object}/{from_id}/associations/{to_object}")
        return [r["toObjectId"] for r in data.get("results", [])]
    except Exception as exc:
        log.warning(" Erro ao buscar associações de %s %s: %s", from_object, from_id, exc)
        return []