"""Propriedades extraídas por objeto do HubSpot CRM.

Fonte da verdade do que o hubspot-service busca na API v3.
Alterações aqui devem ser refletidas em domain/schemas.py.
"""

ASSOCIATIONS = ["contacts", "deals", "companies", "tasks", "calls"]

CONTACT_PROPERTIES = [
    "email",
    "firstname",
    "lastname",
    "lifecyclestage",
    "hs_lead_status",
    "hs_latest_source",
    "hs_latest_source_timestamp",
    "phone",
    "mobilephone",
    "cadastrado_canal_azul",
    "associatedcompanyid",
    "cargo",
    "hs_state_code",
    "engagements_last_meeting_booked_medium",
    "first_conversion_date",
    "first_conversion_event_name",
    "hs_analytics_first_url",
    "hs_analytics_last_url",
    "hs_analytics_source",
    "hs_analytics_source_data_1",
    "hs_analytics_source_data_2",
    "hs_object_source_detail_1",
    "hs_object_source_detail_2",
    "hs_object_source_detail_3",
    "hs_object_source_label",
    "hs_clicked_linkedin_ad",
    "hs_google_click_id",
    "hs_facebook_click_id",
    "hs_marketable_status",
    "hs_marketable_reason_type",
    "hs_pipeline",
    "hs_country_region_code",
    "hs_createdate",
    "hs_email_last_send_date",
    "num_unique_conversion_events",
    "num_conversion_events",
    "produto_de_interesse",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
    "createdate",
    "lastmodifieddate",
    "hubspot_owner_id",
    "campanha",
    "tipo_de_campanha"
]

DEAL_PROPERTIES = [
    "dealname",
    "amount",
    "dealstage",
    "pipeline",
    "closedate",
    "createdate",
    "hs_lastmodifieddate",
    "hubspot_owner_id",
    "hs_deal_stage_probability",
    "hs_projected_amount",
    "hs_closed_amount",
    "dealtype",
    "description",
    "hs_forecast_category",
    "hs_next_step",
    "categoria_de_produto_de_interesse",
    "qualificado_para_qual_funil",
    "direcionado",
    "no_bo"
]

COMPANY_PROPERTIES = [
    "name",
    "domain",
    "phone",
    "city",
    "state",
    "country",
    "zip",
    "industry",
    "numberofemployees",
    "annualrevenue",
    "type",
    "description",
    "createdate",
    "hs_lastmodifieddate",
    "hubspot_owner_id",
    "lifecyclestage",
    "hs_lead_status",
    "website",
    "linkedin_company_page",
    "cnpj",
]

TASK_PROPERTIES = [
    "hs_task_subject",
    "hs_task_body",
    "hs_task_status",           # NOT_STARTED, IN_PROGRESS, COMPLETED, etc.
    "hs_task_priority",         # LOW, MEDIUM, HIGH
    "hs_task_type",             # CALL, EMAIL, TODO
    "hs_task_completion_date",
    "hubspot_owner_id",
    "hs_createdate",
    "hs_lastmodifieddate",
    "hs_timestamp",
]

CALL_PROPERTIES = [
    "hs_call_title",
    "hs_call_direction",        # INBOUND / OUTBOUND
    "hs_call_status",           # COMPLETED, MISSED, etc.
    "hs_call_duration",         # duração em ms
    "hs_call_body",             # transcrição / notas
    "hs_call_recording_url",
    "hs_call_disposition",
    "hubspot_owner_id",
    "hs_createdate",
    "hs_lastmodifieddate",
    "hs_timestamp",             # data/hora da chamada
]

MEETING_PROPERTIES = [
    "hs_meeting_title",
    "hs_meeting_outcome",          # SCHEDULED, COMPLETED, NO_SHOW, CANCELED...
    "hs_meeting_location",
    "hs_meeting_start_time",
    "hs_meeting_end_time",
    "hs_meeting_body",
    "hubspot_owner_id",
    "hs_createdate",
    "hs_lastmodifieddate",
    "hs_timestamp",                # data/hora de referência da reunião
]

# Propriedade de última modificação usada pela action `search`.
# Contacts é a exceção histórica da API: usa `lastmodifieddate`;
# todos os demais objetos usam `hs_lastmodifieddate`.
LASTMODIFIED_PROPERTY: dict[str, str] = {
    "contacts": "lastmodifieddate",
}
DEFAULT_LASTMODIFIED = "hs_lastmodifieddate"

# Mapa objeto -> (propriedades, associações padrão) usado pelo handler
OBJECT_CONFIG: dict[str, dict] = {
    "contacts": {
        "properties": CONTACT_PROPERTIES,
        "associations": ["companies", "deals"],
    },
    "deals": {
        "properties": DEAL_PROPERTIES,
        "associations": ["contacts", "companies"],
    },
    "companies": {
        "properties": COMPANY_PROPERTIES,
        "associations": [],
    },
    "tasks": {
        "properties": TASK_PROPERTIES,
        "associations": ["contacts", "deals", "companies"],
    },
    "calls": {
        "properties": CALL_PROPERTIES,
        "associations": ["contacts", "deals"],
    },
    "meetings": {
        "properties": MEETING_PROPERTIES,
        "associations": ["contacts", "deals"],
    },
}