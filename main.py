"""Entrypoint para execução local do hubspot-service.

Uso:
    HUBSPOT_TOKEN=... python main.py extract contacts
    HUBSPOT_TOKEN=... python main.py extract deals --out deals.jsonl
    HUBSPOT_TOKEN=... python main.py upsert contacts --records records.json --id-property email
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from core.hubspot_client import HubspotClient
from services.extractor import ExtractorService
from services.loader import LoaderService


def configure_logging() -> None:
    timestamp_run = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / f"hubspot_service_{timestamp_run}.log",
                                encoding="utf-8"),
        ],
    )


def run_extract(extractor: ExtractorService, args, log) -> int:
    out = Path(args.out or f"{args.object_type}.jsonl")
    total = 0
    after = None
    with out.open("w", encoding="utf-8") as fh:
        while True:
            page = extractor.extract_pages(args.object_type, after=after)
            for record in page.records:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            total += page.record_count
            after = page.next_after
            if not after:
                break
    log.info("Extração concluída: %d registros em %s", total, out)
    return 0


def run_write(loader: LoaderService, args, log) -> int:
    records = json.loads(Path(args.records).read_text(encoding="utf-8"))
    result = loader.batch_write(
        action=args.command,
        object_type=args.object_type,
        records=records,
        id_property=args.id_property,
    )
    log.info("Carga concluída: %s", result.to_dict())
    return 0 if result.total_failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="hubspot-service local")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ext = sub.add_parser("extract")
    p_ext.add_argument("object_type")
    p_ext.add_argument("--out", default=None)

    for cmd in ("create", "update", "upsert"):
        p = sub.add_parser(cmd)
        p.add_argument("object_type")
        p.add_argument("--records", required=True, help="JSON com a lista de records")
        p.add_argument("--id-property", default=None)

    args = parser.parse_args()
    configure_logging()
    log = logging.getLogger("hubspot_service")

    token = os.environ.get("HUBSPOT_TOKEN")
    if not token:
        log.error("Defina a variável de ambiente HUBSPOT_TOKEN")
        return 1

    client = HubspotClient(token=token)
    if args.command == "extract":
        return run_extract(ExtractorService(client), args, log)
    return run_write(LoaderService(client), args, log)


if __name__ == "__main__":
    sys.exit(main())
