import logging
import time
import requests

BASE_URL = "https://api.hubapi.com"
log = logging.getLogger(__name__)

class HubspotClient:
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
    def get(self, path: str, params: dict = None, retries: int = 5) -> dict:
        url = f"{BASE_URL}{path}"

        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=30)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 10))
                    log.warning("Rater Limit atingido. Aguardando %ds...", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.RequestException as exc:
                if attempt == retries:
                    log.error("Falha após %d tentativas: %s", retries, exc)
                    raise
                wait = 2 ** attempt
                log.warning("Tentativa %d falhou (%s). Retry em %ds...", attempt, exc, wait)
                time.sleep(wait)
    def post_batch(self, path: str, body: dict, retries: int = 5):
        url = f"{BASE_URL}{path}"
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.post(url, json=body, timeout=60)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 10))
                    log.warning("Rate limit atingido. Aguardando %ds...", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.status_code, resp.json() if resp.content else {}
            except requests.exceptions.RequestException as exc:
                if attempt == retries:
                    raise
                wait = 2 ** attempt
                log.warning("Tentativa  $d falhou (%s). Retry em %ds...", attempt, exc, wait)
                time.sleep(wait)

    def delete(self, path: str) -> bool:
        url = f"{BASE_URL}{path}"
        try:
            resp = self.session.delete(url, timeout=30)
            if resp.status_code() == 204:
                return True
            log.error(" Erro:  HTTP %d %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            log.error(" Exceção ao executar: %s", exc)
            return False
        

