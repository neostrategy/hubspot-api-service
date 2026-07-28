"""
Client HTTP para API do Hubspot.

Responsabilidades: autenticação, retry com backoff exponencial e tratamento de rate limit (429). Não conhece objetos de negócio
"""
import logging 
import time
import requests

BASE_URL = "https://api.hubapi.com"
log = logging.getLogger(__name__)

class HubspotRetriesExceededError(RuntimeError):
    """Levantada quando todas as tentativas de chamadas se esgotam."""

class HubspotClient:
    def __init__(self, token: str, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })

    def get(self, path: str, params: dict | None = None, retries: int = 5) -> dict:
        url = f"{BASE_URL}{path}"
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 10))
                    log.warning("Rate limit atingido em GET %s. Aguardando %ds...", path, wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.RequestException as exc:
                if attempt == retries:
                    log.error("GET %s falhou após %d tentativas: %s", path, retries, exc)
                    raise
                wait = 2 ** attempt
                log.warning("GET %s tentativas %d falhou (%s). Retry em %ds...", path, attempt, exc, wait)
                time.sleep(wait)
        raise HubspotRetriesExceededError(f"Retries esgotados para GET {path}")

    def post_batch(self, path: str, body: dict, retries: int = 5) -> tuple[int, dict]:
        """
        POST para endpoints de batch do Hubspot

        ATENÇÃO: O retry assume idempotência do endpoint (batch upsert por id).
        Não usar para criação não-idempotente sem chave de deduplicação.
        """
        url = f"{BASE_URL}{path}"
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.post(url, json=body, timeout=self.timeout * 2)
                if resp.status_code == 429:
                    wait = max(int(resp.headers.get("Retry-After", 10)), 5)
                    log.warning(
                        "429 em POST %s | daily-remaining=%s burst-remaining=%s | %s | aguardando %ds...",
                        path,
                        resp.headers.get("x-hubspot-ratelimit-daily-remaining"),
                        resp.headers.get("x-hubspot-ratelimit-remaining"),
                        resp.text[:200],
                        wait,
                    )
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.status_code, resp.json() if resp.content else {}
            except requests.exceptions.RequestException as exc:
                if attempt == retries:
                    log.error("POST %s falhou após %d tentativas: %s", path, retries, exc)
                    raise
                wait = 2 ** attempt
                log.warning("POST %s tentativa %d falhou (%s). Retry em %ds...", path, attempt, exc, wait)
                time.sleep(wait)
        raise HubspotRetriesExceededError(f"Retries esgotados para POST {path}")
    
    def delete(self, path: str) -> bool:
        url = f"{BASE_URL}{path}"
        try:
            resp = self.session.delete(url, timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            log.error("DELETE %s: exceção na chamada: %s", path, exc)
            return False
        if resp.status_code == 204:
            return True
        log.error("DELETE %s falhou: HTTP %d %s", path, resp.status_code, resp.text[:200])
        return False