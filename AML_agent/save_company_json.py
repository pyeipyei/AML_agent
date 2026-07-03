import json
import os
import re


def _resolve_company_number(data: dict) -> str | None:
    """Return a stable company id from common agent output shapes."""
    company_number = data.get("company_number")
    if company_number not in (None, "", "null", "NIL"):
        return str(company_number)

    profile = data.get("company_profile")
    if isinstance(profile, dict):
        for key in ("registration_no", "company_number"):
            value = profile.get(key)
            if value not in (None, "", "null", "NIL"):
                return str(value)

    registration_no = data.get("registration_no")
    if registration_no not in (None, "", "null", "NIL"):
        return str(registration_no)

    return None


def _strip_code_fence(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrapper if the model returned one."""
    if not text:
        raise ValueError("Model output is empty; cannot parse JSON.")
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def _unique_key(item: dict) -> str | None:
    """Pick a stable identifier for list-of-dict merging (people, shareholders, etc.)."""
    for field in ("id_number", "registration_no_or_id_no", "name", "full_name"):
        value = item.get(field) if isinstance(item, dict) else None
        if value:
            return f"{field}:{value}"
    return None


def _merge_list(old_list: list, new_list: list) -> list:
    """Merge two lists. If items are dicts with a recognizable id, merge by id.
    Otherwise, append items from new_list that aren't already present."""
    if not old_list:
        return list(new_list)
    if not new_list:
        return old_list

    # If entries look like identifiable dicts (e.g. directors, shareholders), merge by key.
    if all(isinstance(i, dict) for i in old_list + new_list):
        indexed = {}
        order = []
        for item in old_list:
            key = _unique_key(item) or json.dumps(item, sort_keys=True)
            indexed[key] = item
            order.append(key)
        for item in new_list:
            key = _unique_key(item) or json.dumps(item, sort_keys=True)
            if key in indexed:
                indexed[key] = _merge_dict(indexed[key], item)
            else:
                indexed[key] = item
                order.append(key)
        return [indexed[k] for k in order]

    # Plain values (strings/numbers): append new distinct values.
    merged = list(old_list)
    for item in new_list:
        if item not in merged:
            merged.append(item)
    return merged


def _merge_dict(old: dict, new: dict) -> dict:
    """Recursively merge `new` into `old`.
    - dict + dict -> recurse
    - list + list -> merge via _merge_list
    - scalar -> new value overwrites old, unless new value is None/empty
    """
    merged = dict(old)
    for key, new_val in new.items():
        old_val = merged.get(key)

        if isinstance(old_val, dict) and isinstance(new_val, dict):
            merged[key] = _merge_dict(old_val, new_val)
        elif isinstance(old_val, list) and isinstance(new_val, list):
            merged[key] = _merge_list(old_val, new_val)
        else:
            # overwrite only if the new value actually carries information
            if new_val not in (None, "", "NIL", "null"):
                merged[key] = new_val
            elif key not in merged:
                merged[key] = new_val
    return merged


def save_company_json(model_output: str, json_path: str) -> None:
    """
    Save/merge a single extraction result into the local company JSON store.

    Rules:
    - If json_path doesn't exist -> create it with a single entry.
    - If it exists but the company_number isn't present -> append a new entry.
    - If the company_number is already present -> deep-merge the new data
      into the existing entry's "company_profile".
    """
    cleaned = _strip_code_fence(model_output)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Model output must be a JSON object.")

    company_number = _resolve_company_number(data)
    if not company_number:
        raise ValueError(
            "Model output is missing 'company_number' (and no registration number "
            "could be inferred). The PDF may not have been read correctly."
        )

    data = dict(data)
    data["company_number"] = company_number

    # Everything except company_number is treated as the "company_profile" payload.
    new_profile = {k: v for k, v in data.items() if k != "company_number"}

    os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)

    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            try:
                store = json.load(f)
            except json.JSONDecodeError:
                store = []
        if not isinstance(store, list):
            store = [store]
    else:
        store = []

    existing_entry = next(
        (entry for entry in store if entry.get("company_number") == company_number),
        None,
    )

    if existing_entry is None:
        store.append({
            "company_number": company_number,
            "company_profile": new_profile,
        })
    else:
        existing_entry["company_profile"] = _merge_dict(
            existing_entry.get("company_profile", {}), new_profile
        )

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)