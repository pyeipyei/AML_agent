import json
import os


def _add_entry(queue, counter, **fields):
    entry = {
        "queue_id": f"SQ_{counter:03d}",
        **fields,
    }
    queue.append(entry)
    return counter + 1


def build_screening_queue(
    company_json_path: str,
    output_path: str,
    default_source_reference: str = None,
) -> list:
    with open(company_json_path, "r", encoding="utf-8") as f:
        companies = json.load(f)

    if isinstance(companies, dict):
        companies = [companies]

    queue = []
    counter = 1

    for company in companies:
        company_id = company.get("company_number")
        profile = company.get("company_profile", {}) or {}

        # --- 1. the company itself ---
        company_profile_block = profile.get("company_profile", {}) or {}
        counter = _add_entry(
            queue,
            counter,
            company_id=company_id,
            search_name=company_profile_block.get("company_name"),
            entity_type_hint="CORPORATE",
            role="CLIENT",
            registration_no=company_profile_block.get("registration_no") or company_id,
            id_no=None,
            date_of_birth=None,
            nationality=None,
            country=company_profile_block.get("country_of_incorporation"),
            source_reference=default_source_reference,
            screening_required=True,
        )

        # --- 2. directors / secretaries / other control persons ---
        for person in profile.get("management_and_control_persons", []) or []:
            counter = _add_entry(
                queue,
                counter,
                company_id=company_id,
                search_name=person.get("full_name"),
                entity_type_hint="INDIVIDUAL",
                role=person.get("role"),
                registration_no=None,
                id_no=person.get("id_number"),
                date_of_birth=person.get("date_of_birth"),
                nationality=person.get("nationality"),
                country=person.get("country_of_residence"),
                source_reference=default_source_reference,
                screening_required=True,
            )

        # --- 3. shareholders / members ---
        for holder in profile.get("shareholders_and_members", []) or []:
            member_type = (holder.get("member_type") or "").upper()
            is_corporate = member_type == "CORPORATE"

            counter = _add_entry(
                queue,
                counter,
                company_id=company_id,
                search_name=holder.get("name"),
                entity_type_hint=member_type or ("CORPORATE" if is_corporate else "INDIVIDUAL"),
                role=holder.get("role") or "SHAREHOLDER",
                registration_no=holder.get("registration_no_or_id_no") if is_corporate else None,
                id_no=None if is_corporate else holder.get("registration_no_or_id_no"),
                date_of_birth=None,
                nationality=None if is_corporate else holder.get("nationality_or_country"),
                country=holder.get("nationality_or_country") if is_corporate else None,
                source_reference=default_source_reference,
                screening_required=True,
            )

    result = {"screening_queue": queue}

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return queue


# if __name__ == "__main__":
#     build_screening_queue("./jsons/company.json", "./jsons/screening_queue.json")