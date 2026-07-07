from app_hubspot.utils.utils import flatten_associations
import logging

log = logging.getLogger(__name__)

class ExtractorService:
    def __init__(self, client):

        self.client = client

    def extract_objects(
            self,
            object_type: str,
            properties: list[str],
            associations=None
    ):
        all_records = []
        after = None
        page = 1

        while True:
            params = {
                "limit": 100,
                "properties": ",".join(properties),
                "archived": "false"
            }
            log.info(params)
            if associations:

                params["associations"] = ",".join(associations)

            if after:
                params["after"] = after

            log.info(" [%s] Buscando página %d...", object_type, page)
            
            data = self.client.get(
                f"/crm/v3/objects/{object_type}",
                params=params
            )

            results = data.get("results", [])
            log.info(results)
            for record in results:
                row = {"id": record["id"]}
                row.update(record.get("properties", {}))
                row.update(flatten_associations(record.get("associations", {})))
                all_records.append(row)
            
            paging = data.get("paging", {})
            next_cursor = {} 
            # paging.get("next", {}).get("after")
            if not next_cursor:
                break
            after = next_cursor
            page += 1
        
        log.info(" [%s] Total extraído: %d registros", object_type, len(all_records))
        
        return all_records