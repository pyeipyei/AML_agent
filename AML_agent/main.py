import asyncio
import csv
import os
import json
import re

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from sub_agents.SSM_agent import SSM_agent
from sub_agents.AR_agent import AR_agent
from sub_agents.AF_agent import AF_agent
from sub_agents.artemis_agent import artemis_agent  # adjust path if your file lives elsewhere

from save_company_json import save_company_json, _resolve_company_number
from build_screening_queue import build_screening_queue

from generate_pdf_from_json import extract_data, generate_kyc_pdf

from tools import (
    pre_filter_documents,
)

session_service = InMemorySessionService()

TEST_RESULTS_BASE = "./test_results"

APP_NAME = "document_extractor"
SCREENING_APP_NAME = "artemis_screening"
USER_ID = "system"

token_usage = {
    "documents": {},
    "agents": {},
    "pipeline": {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    },
}

def _empty_token_counts() -> dict:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }

def _add_token_counts(target: dict, input_tokens: int, output_tokens: int, total_tokens: int) -> None:
    target["input_tokens"] += input_tokens
    target["output_tokens"] += output_tokens
    target["total_tokens"] += total_tokens

def _ensure_document(document: str) -> dict:
    if document not in token_usage["documents"]:
        token_usage["documents"][document] = {
            "company_number": None,
            "agents": {},
            "screening_queues": {},
            "totals": _empty_token_counts(),
        }
    return token_usage["documents"][document]

def _recalc_document_totals(document_entry: dict) -> None:
    totals = _empty_token_counts()
    for agent_counts in document_entry.get("agents", {}).values():
        _add_token_counts(
            totals,
            agent_counts["input_tokens"],
            agent_counts["output_tokens"],
            agent_counts["total_tokens"],
        )
    document_entry["totals"] = totals

def set_document_company_number(document: str, company_number: str | None) -> None:
    if not document or not company_number:
        return
    _ensure_document(document)["company_number"] = company_number

def log_event_tokens(event, label: str = "", file_path: str = ""):
    usage = getattr(event, "usage_metadata", None)
    author = getattr(event, "author", "unknown")

    if usage is None:
        print(
            f"[{label}] file={os.path.basename(file_path)} "
            f"author={author} final={event.is_final_response()} "
            "(no usage_metadata)"
        )
        return (
            file_path,
            author,
            0, 0, 0, 0, 0,
        )

    input_tokens = getattr(usage, "prompt_token_count", 0)
    output_tokens = getattr(usage, "candidates_token_count", 0)
    total_tokens = getattr(usage, "total_token_count", 0)
    cached_tokens = getattr(usage, "cached_content_token_count", 0)
    thoughts_tokens = getattr(usage, "thoughts_token_count", 0)

    print(
        f"[{label}] file={os.path.basename(file_path)} "
        f"author={author} "
        f"in={input_tokens} out={output_tokens} total={total_tokens}"
    )

    return (
        file_path,
        author,
        input_tokens,
        output_tokens,
        total_tokens,
        cached_tokens,
        thoughts_tokens,
    )

def update_token_usage(
    document: str,
    author: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    *,
    queue_id: str | None = None,
    search_name: str | None = None,
):
    document_key = os.path.basename(document) if document else "Unknown"
    document_entry = _ensure_document(document_key)

    if author not in document_entry["agents"]:
        document_entry["agents"][author] = _empty_token_counts()
    _add_token_counts(
        document_entry["agents"][author],
        input_tokens,
        output_tokens,
        total_tokens,
    )

    if queue_id:
        if queue_id not in document_entry["screening_queues"]:
            document_entry["screening_queues"][queue_id] = {
                "search_name": search_name,
                "agent": author,
                **_empty_token_counts(),
            }
        queue_entry = document_entry["screening_queues"][queue_id]
        if search_name and not queue_entry.get("search_name"):
            queue_entry["search_name"] = search_name
        _add_token_counts(queue_entry, input_tokens, output_tokens, total_tokens)

    _recalc_document_totals(document_entry)

    if author not in token_usage["agents"]:
        token_usage["agents"][author] = _empty_token_counts()
    _add_token_counts(
        token_usage["agents"][author],
        input_tokens,
        output_tokens,
        total_tokens,
    )

    _add_token_counts(
        token_usage["pipeline"],
        input_tokens,
        output_tokens,
        total_tokens,
    )

def allocate_test_run_dir(base_dir: str = TEST_RESULTS_BASE) -> tuple[int, str]:
    os.makedirs(base_dir, exist_ok=True)
    existing_ids = [
        int(name) for name in os.listdir(base_dir) if name.isdigit()
    ]
    run_id = max(existing_ids, default=0) + 1
    run_dir = os.path.join(base_dir, str(run_id))
    os.makedirs(run_dir, exist_ok=True)
    return run_id, run_dir

def run_paths(run_dir: str) -> dict[str, str]:
    return {
        "company_json": os.path.join(run_dir, "company.json"),
        "screening_queue": os.path.join(run_dir, "screening_queue.json"),
        "screening_results": os.path.join(run_dir, "screening_results.json"),
        "token_usage": os.path.join(run_dir, "token_usage.json"),
        "token_usage_csv": os.path.join(run_dir, "token_usage.csv"),
        "output_pdf": os.path.join(run_dir, "result_KYC.pdf"),
    }

def reset_token_usage(run_id: int, run_dir: str) -> None:
    global token_usage
    token_usage = {
        "run_id": run_id,
        "run_dir": run_dir,
        "documents": {},
        "agents": {},
        "pipeline": _empty_token_counts(),
    }

def save_token_usage_csv(path: str, usage: dict | None = None) -> None:
    usage = usage or token_usage
    fieldnames = [
        "run_id",
        "category",
        "document",
        "company_number",
        "agent",
        "queue_id",
        "search_name",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    ]
    run_id = usage.get("run_id", "")

    def _row(category: str, counts: dict, **fields) -> dict:
        return {
            "run_id": run_id,
            "category": category,
            "document": "",
            "company_number": "",
            "agent": "",
            "queue_id": "",
            "search_name": "",
            "input_tokens": counts.get("input_tokens", 0),
            "output_tokens": counts.get("output_tokens", 0),
            "total_tokens": counts.get("total_tokens", 0),
            **fields,
        }

    rows: list[dict] = []

    for document, doc_entry in usage.get("documents", {}).items():
        company_number = doc_entry.get("company_number") or ""

        for agent, counts in doc_entry.get("agents", {}).items():
            rows.append(
                _row(
                    "document_agent",
                    counts,
                    document=document,
                    company_number=company_number,
                    agent=agent,
                )
            )

        for queue_id, queue_entry in doc_entry.get("screening_queues", {}).items():
            rows.append(
                _row(
                    "screening_queue",
                    queue_entry,
                    document=document,
                    company_number=company_number,
                    agent=queue_entry.get("agent", ""),
                    queue_id=queue_id,
                    search_name=queue_entry.get("search_name", "") or "",
                )
            )

        rows.append(
            _row(
                "document_total",
                doc_entry.get("totals", _empty_token_counts()),
                document=document,
                company_number=company_number,
            )
        )

    for agent, counts in usage.get("agents", {}).items():
        rows.append(_row("agent_total", counts, agent=agent))

    rows.append(_row("pipeline_total", usage.get("pipeline", _empty_token_counts())))

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def save_token_usage(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(token_usage, f, indent=2)

    csv_path = os.path.splitext(path)[0] + ".csv"
    save_token_usage_csv(csv_path, token_usage)

#------------------Extraction agents-------------------------
ssm_runner = Runner(app_name=APP_NAME, agent=SSM_agent, session_service=session_service)
ar_runner = Runner(app_name=APP_NAME, agent=AR_agent, session_service=session_service)
afs_runner = Runner(app_name=APP_NAME, agent=AF_agent, session_service=session_service)
artemis_runner = Runner(app_name=SCREENING_APP_NAME, agent=artemis_agent, session_service=session_service)

def get_runner(file_type: str) -> Runner:
    file_type = file_type.lower()

    if file_type == "ssm":
        return ssm_runner

    if file_type in ("annual return", "ar"):
        return ar_runner

    if file_type in ("audited financial statements", "afs"):
        return afs_runner

    raise ValueError(f"Unsupported document type: {file_type}")

async def process_pdf(file_path: str, file_type: str):
    runner = get_runner(file_type)

    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )

    message = types.Content(
        role="user",
        parts=[
            types.Part(
                text=f"""
                File path: {file_path}
                """
            )
        ],
    )

    final_json = None

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_json = event.content.parts[0].text

        _, author, in_tok, out_tok, total_tok, _, _ = log_event_tokens(
            event,
            label="process_pdf",
            file_path=file_path,
        )

        update_token_usage(
            document=file_path,
            author=author,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=total_tok,
        )

    if final_json is None:
        raise RuntimeError(f"No response from agent for file={os.path.basename(file_path)}")

    return final_json

#-----------------Screening helpers--------------------------
def _strip_code_fence(text: str) -> str:
    if not text:
        raise ValueError("Model output is empty; cannot parse JSON.")
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    return match.group(1).strip() if match else text

async def screen_entry(entry: dict, source_document: str | None = None) -> dict:
    """Send ONE screening queue entry to the Artemis agent and return its parsed JSON."""
    session = await session_service.create_session(app_name=SCREENING_APP_NAME, user_id=USER_ID)

    message = types.Content(
        role="user",
        parts=[types.Part(text=json.dumps(entry))],
    )

    final_text = None
    queue_id = entry.get("queue_id")
    search_name = entry.get("search_name")
    document_key = os.path.basename(source_document) if source_document else "screening"

    async for event in artemis_runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text

        _, author, in_tok, out_tok, total_tok, _, _ = log_event_tokens(
            event,
            label="screen_entry",
            file_path=document_key,
        )

        update_token_usage(
            document=document_key,
            author=author,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=total_tok,
            queue_id=queue_id,
            search_name=search_name,
        )

    if final_text is None:
        raise RuntimeError(f"No response from agent for queue_id={entry.get('queue_id')}")

    return json.loads(_strip_code_fence(final_text))

def load_screening_results(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}
    data.setdefault("screening_results", [])
    data.setdefault("summary", {})
    data.setdefault("processing_notes", [])
    return data

def save_screening_results(data: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def screen_new_queue_entries(
    queue_path: str,
    results_path: str,
    source_document: str | None = None,
):
    """Screen only queue entries that aren't already in screening_results.json."""
    with open(queue_path, "r", encoding="utf-8") as f:
        queue_data = json.load(f)

    results_data = load_screening_results(results_path)
    already_done = {r.get("queue_id") for r in results_data["screening_results"]}

    for entry in queue_data.get("screening_queue", []):
        queue_id = entry.get("queue_id")

        if not entry.get("screening_required", True):
            continue
        if queue_id in already_done:
            continue

        try:
            result = await screen_entry(entry, source_document=source_document)
            results_data["screening_results"].extend(result.get("screening_results", []))
            results_data["processing_notes"].extend(result.get("processing_notes", []))
            results_data["summary"] = result.get("summary", results_data["summary"])
            save_screening_results(results_data, results_path)  # save after every entry
            already_done.add(queue_id)
            print(f"Screened {queue_id} ({entry.get('search_name')})")
        except Exception as e:
            print(f"Error screening {queue_id} ({entry.get('search_name')}): {e}")

#-----------------Pipeline--------------------------
async def run_pipeline(
    uploads_dir: str,
    filenames: list[str] | None = None,
) -> dict:
    run_id, run_dir = allocate_test_run_dir()
    paths = run_paths(run_dir)
    reset_token_usage(run_id, run_dir)

    print(f"Writing outputs to {run_dir}")

    processed_any = False

    if filenames is None:
        pdf_filenames = [
            name for name in os.listdir(uploads_dir) if name.lower().endswith(".pdf")
        ]
    else:
        pdf_filenames = [name for name in filenames if name.lower().endswith(".pdf")]

    for filename in pdf_filenames:
        pdf_path = os.path.join(uploads_dir, filename)
        if not os.path.isfile(pdf_path):
            print(f"Skipping missing file: {pdf_path}")
            continue
        file_type = pre_filter_documents(pdf_path)

        try:
            result = await process_pdf(pdf_path, file_type)

            company_number = None
            try:
                parsed = json.loads(_strip_code_fence(result))
                company_number = _resolve_company_number(parsed)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
            set_document_company_number(filename, company_number)

            save_company_json(result, paths["company_json"])
            build_screening_queue(
                paths["company_json"],
                paths["screening_queue"],
                default_source_reference=filename,
            )
            await screen_new_queue_entries(
                paths["screening_queue"],
                paths["screening_results"],
                source_document=filename,
            )
            processed_any = True

        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")

        save_token_usage(paths["token_usage"])

    if processed_any and os.path.exists(paths["company_json"]):
        data = extract_data(paths["company_json"], paths["screening_results"])
        output_pdf = generate_kyc_pdf(data, paths["output_pdf"])
        print(f"KYC PDF generated: {output_pdf}")
    else:
        output_pdf = None
        print("No documents processed; skipped KYC PDF generation.")

    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "output_pdf": output_pdf,
        **paths,
    }

if __name__ == "__main__":
    asyncio.run(run_pipeline("./uploads"))