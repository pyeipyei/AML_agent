import json
from datetime import date


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_kyc_input(
    company_id: str,
    company_json_path: str = "./jsons/company.json",
    results_json_path: str = "./jsons/screening_results.json",
    engagement_info: dict | None = None,
) -> dict:
    """
    Build the structured data dict for the KYC PDF generator, pulling ONLY from
    the JSON already produced by the extraction + screening pipeline. Nothing
    here is written by an LLM -- it's plain lookups, so no name/number can be
    altered in transit.

    `engagement_info` is for fields the pipeline has no source for (e.g. nature
    of service, office, engagement type, prepared-by names) -- pass these in
    explicitly per engagement; they default to "N/A" / blank if omitted.
    """
    companies = _load_json(company_json_path)
    if isinstance(companies, dict):
        companies = [companies]

    company = next((c for c in companies if c.get("company_number") == company_id), None)
    if company is None:
        raise ValueError(f"company_id {company_id} not found in {company_json_path}")

    profile = company.get("company_profile", {}) or {}
    company_profile_block = profile.get("company_profile", {}) or {}
    persons = profile.get("management_and_control_persons", []) or []
    shareholders = profile.get("shareholders_and_members", []) or []

    results_data = _load_json(results_json_path)
    all_results = results_data.get("screening_results", [])
    company_results = [r for r in all_results if r.get("company_id") == company_id]

    # --- PEP detection: individuals with pep_flag true -----------------------
    domestic_peps = []
    foreign_peps = []
    for r in company_results:
        summary = r.get("screening_summary", {}) or {}
        if r.get("entity_type_hint") == "INDIVIDUAL" and summary.get("pep_flag"):
            name = r.get("matched_name") or r.get("search_name") or "UNKNOWN"
            profile_nat = (r.get("matched_profile", {}) or {}).get("nationality")
            if profile_nat and profile_nat.upper() != "MALAYSIA":
                foreign_peps.append(name)
            else:
                domestic_peps.append(name)

    # --- Sanctions / adverse news hits ---------------------------------------
    sanctions_hits = [
        r.get("matched_name") or r.get("search_name")
        for r in company_results
        if (r.get("screening_summary", {}) or {}).get("sanctions_flag")
    ]
    adverse_news_hits = [
        r.get("matched_name") or r.get("search_name")
        for r in company_results
        if (r.get("screening_summary", {}) or {}).get("adverse_news_flag")
    ]

    # --- Overall risk rating (simple deterministic rule; adjust to your policy) ---
    any_flag = bool(domestic_peps or foreign_peps or sanctions_hits or adverse_news_hits)
    kyc_risk_rating = "HIGH" if any_flag else "LOW"

    engagement_info = engagement_info or {}

    return {
        "client_name": company_profile_block.get("company_name") or "N/A",
        "year_ending": engagement_info.get("year_ending", "N/A"),
        "nature_of_service": engagement_info.get("nature_of_service", "N/A"),
        "kyc_risk_rating": kyc_risk_rating,

        "pep_flag": bool(domestic_peps or foreign_peps),
        "pep_details": "Domestic PEP" if domestic_peps else ("Foreign PEP" if foreign_peps else "N/A"),
        "higher_risk_jurisdiction": False,  # not derivable from current schema; set manually if needed
        "alert_list_flag": bool(sanctions_hits),
        "investigation_flag": False,        # not derivable from current schema
        "adverse_info_flag": bool(adverse_news_hits),

        "engagement": {
            "type_of_client": engagement_info.get("type_of_client", "N/A"),
            "type_of_engagement": engagement_info.get("type_of_engagement", "N/A"),
            "nature_of_service": engagement_info.get("nature_of_service", "N/A"),
            "proposed_services": engagement_info.get("proposed_services", "N/A"),
            "office": engagement_info.get("office", "N/A"),
            "gazetted_activity": engagement_info.get("gazetted_activity", "N/A"),
        },

        "registration_no": company_profile_block.get("registration_no") or company_id,
        "principal_place_of_business": company_profile_block.get("registered_address") or "N/A",

        "management_and_control_persons": [
            {
                "full_name": p.get("full_name"),
                "role": p.get("role"),
                "id_number": p.get("id_number"),
                "nationality": p.get("nationality") or p.get("country_of_residence"),
            }
            for p in persons
        ],

        "shareholders_and_members": [
            {
                "name": s.get("name"),
                "member_type": s.get("member_type"),
                "registration_no_or_id_no": s.get("registration_no_or_id_no"),
                "shares_held": s.get("shares_held"),
            }
            for s in shareholders
        ],

        "domestic_peps": domestic_peps,
        "foreign_peps": foreign_peps,
        "sanctions_hits": sanctions_hits,
        "adverse_news_hits": adverse_news_hits,

        # Not derivable from current pipeline data -- SOE status isn't a field
        # Artemis returns. Populate this manually or extend the screening
        # schema if you need it auto-detected.
        "soe_entities": engagement_info.get("soe_entities", []),

        "approvals": engagement_info.get("approvals", {
            "prepared_by": {"name": "", "designation": "", "date": ""},
            "reviewed_by": {"name": "", "designation": "", "date": ""},
            "approved_by": {"name": "", "designation": "", "date": ""},
        }),

        "generated_date": date.today().isoformat(),
    }