# API Mapping — hubspot-service

**Repo:** `neostrategy/hubspot-api-service`
**Consumidor:** flow Prefect `pipeline-leads-hubspot`
**Padrão:** invocação Lambda síncrona request/response (mesmo modelo do `cnpj-api-service`). O Lambda não persiste nada — devolve JSON e o pipeline decide o destino.
**Última atualização:** 2026-07-08

---

## 1. Visão geral

| Item | Valor |
|---|---|
| Runtime | Python 3.12, AWS Lambda |
| Invocação | `lambda:InvokeFunction` síncrona (RequestResponse) |
| Handler | `handlers/lambda_handler.handler` |
| Autenticação HubSpot | Private app token via env var `HUBSPOT_TOKEN` (sem Secrets Manager — decisão de custo) |
| Limite de resposta | 6 MB (limite do Lambda síncrono) → extração paginada por cursor |
| Deploy | SAM + GitHub Actions OIDC (padrão `cnpj-api-service`); token como parâmetro `NoEcho` |

Formato de resposta em todas as actions:

```json
{ "statusCode": <int>, "body": "<JSON serializado>" }
```

---

## 2. Actions

### 2.1 `extract` — extração paginada

**Endpoint HubSpot usado:** `GET /crm/v3/objects/{object_type}` (API v3, cursor `after`)

**Request:**

| Campo | Tipo | Obrigatório | Default | Descrição |
|---|---|---|---|---|
| `action` | string | não | `"extract"` | |
| `object_type` | string | sim | — | `contacts` \| `deals` \| `companies` \| `tasks` \| `calls` |
| `after` | string | não | `null` | Cursor devolvido na invocação anterior. Omitir na 1ª chamada |
| `max_pages` | int | não | `10` | Páginas por invocação (100 registros/página) |
| `properties` | list[string] | não | `constants/properties.py` | Sobrescreve a lista padrão |
| `associations` | list[string] | não | por objeto (ver §4) | Sobrescreve as associações padrão |

**Response 200 (body):**

| Campo | Tipo | Descrição |
|---|---|---|
| `object_type` | string | Eco do objeto extraído |
| `records` | list[object] | Registros achatados (ver §3) |
| `record_count` | int | Registros neste bloco |
| `pages` | int | Páginas consumidas nesta invocação |
| `next_after` | string \| null | Cursor da próxima invocação. `null` = extração completa |
| `started_at` / `finished_at` | string | Timestamps ISO UTC |

**Loop de consumo no Prefect:**

```python
after = None
while True:
    body = invoke_hubspot_service({"action": "extract",
                                   "object_type": "contacts",
                                   "after": after})
    process(body["records"])
    after = body["next_after"]
    if not after:
        break
```

---

### 2.2 `create` — cadastro em lote

**Endpoint HubSpot usado:** `POST /crm/v3/objects/{object_type}/batch/create`
**Objetos graváveis:** `contacts`, `deals`

**Request:**

```json
{
  "action": "create",
  "object_type": "deals",
  "records": [
    { "properties": { "dealname": "...", "pipeline": "...", "dealstage": "..." } }
  ]
}
```

⚠️ **Não idempotente:** retry após timeout pode duplicar registros no HubSpot.
Usar apenas quando não existe chave — para contacts, preferir sempre `upsert`.

---

### 2.3 `update` — atualização em lote

**Endpoint HubSpot usado:** `POST /crm/v3/objects/{object_type}/batch/update`

**Request:**

```json
{
  "action": "update",
  "object_type": "deals",
  "records": [
    { "id": "123456789", "properties": { "dealstage": "..." } }
  ]
}
```

`id` = HubSpot object ID. Idempotente (seguro para retry).

---

### 2.4 `upsert` — cria ou atualiza por chave natural

**Endpoint HubSpot usado:** `POST /crm/v3/objects/{object_type}/batch/upsert`

**Request:**

```json
{
  "action": "upsert",
  "object_type": "contacts",
  "id_property": "email",
  "records": [
    { "id": "a@b.com", "properties": { "email": "a@b.com", "cargo": "..." } }
  ]
}
```

| Campo | Descrição |
|---|---|
| `id_property` | Propriedade única usada como chave (obrigatório). Para contacts: `email` |
| `records[].id` | **Valor** da `id_property` (não o HubSpot ID) |

Caminho recomendado para cadastro de contatos. Idempotente.

---

### 2.5 Response das cargas (`create`/`update`/`upsert`)

**Body (`BatchResult`):**

| Campo | Tipo | Descrição |
|---|---|---|
| `object_type` / `action` | string | Eco da requisição |
| `total_sent` | int | Registros recebidos |
| `total_succeeded` | int | Confirmados pelo HubSpot |
| `total_failed` | int | Falhas (lote inteiro ou parciais) |
| `errors` | list[object] | Erros por lote ou devolvidos pela API |
| `results` | list[object] | `{"id": ...}` dos registros gravados |

**Status codes:**

| Código | Significado |
|---|---|
| `200` | Tudo gravado (`total_failed == 0`) |
| `207` | Sucesso parcial — **o pipeline DEVE checar `total_failed` e `errors`** |
| `400` | Validação: `object_type` inválido/não gravável, `records` vazio, `id` ausente em update/upsert, `id_property` ausente em upsert, `action` desconhecida |

Lotes são fatiados internamente em blocos de **100** (limite dos endpoints batch do HubSpot).

---

## 3. Formato dos `records` na extração

Cada registro é achatado por `HubspotRow.to_flat_dict()`:

```json
{
  "id": "151",
  "load_ts": "2026-07-08T14:03:22.481+00:00",
  "email": "a@b.com",
  "...demais propriedades do objeto...": null,
  "associated_companies": "99;102",
  "associated_deals": "3001"
}
```

Regras:

- Toda propriedade da lista configurada aparece no registro, com `null` quando ausente — schema estável para o staging/DuckDB.
- Valores chegam como **string** (comportamento da API v3). Tipagem forte é responsabilidade da camada dbt.
- Associações viram colunas `associated_{tipo}` com IDs separados por `;`.
- `load_ts` é gerado como ISO UTC no momento da extração (padrão que evita o bug de `dayfirst` no parse downstream).

---

## 4. Propriedades e associações padrão por objeto

Fonte da verdade: `constants/properties.py` (`OBJECT_CONFIG`).

| Objeto | Propriedades (resumo) | Associações padrão |
|---|---|---|
| `contacts` | 39 props: email, phone, utm_*, hs_analytics_*, first_conversion_*, produto_de_interesse, cargo, owner, datas | `companies`, `deals` |
| `deals` | 15 props: dealname, amount, dealstage, pipeline, closedate, forecast, owner, datas | `contacts`, `companies` |
| `companies` | 20 props: name, domain, cnpj, industry, annualrevenue, lifecyclestage, owner, datas | — |
| `tasks` | 10 props: subject, body, status, priority, type, completion_date, owner, datas | `contacts`, `deals`, `companies` |
| `calls` | 11 props: title, direction, status, duration, body, recording_url, disposition, owner, datas | `contacts`, `deals` |

---

## 5. Comportamento do client HTTP

| Situação | Comportamento |
|---|---|
| HTTP 429 | Respeita `Retry-After` (default 10s) e tenta de novo |
| Erro de rede / 5xx | Backoff exponencial `2^tentativa`, até 5 tentativas |
| Retries esgotados | `HubspotRetriesExceededError` → erro de execução do Lambda (o Prefect vê a invocação falhar) |
| Logging | Apenas contagens, cursores e paths — **payloads nunca são logados (PII/LGPD)** |

---

## 6. Pendências / fora de escopo desta versão

- [ ] `template.yaml` (SAM) e workflow OIDC — copiar do `cnpj-api-service`, ajustando o role por repo
- [ ] Associações no cadastro: `create` de deals ainda não envia o bloco `associations` (deal→contact/company). Decidir se o vínculo é feito no cadastro ou em passo separado via API v4
- [ ] Estratégia de deduplicação de deals no pipeline (não há chave natural na API → extrair, casar e decidir create vs update no flow)
- [ ] Extração incremental (`hs_lastmodifieddate`) via endpoint `/search` — hoje a extração é sempre full