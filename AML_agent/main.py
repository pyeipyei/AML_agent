import asyncio
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

from save_company_json import save_company_json
from build_screening_queue import build_screening_queue

from generate_pdf_from_json import extract_data, generate_kyc_pdf

from tools import (
    pre_filter_documents,
)

from token_tracker import TokenTracker

session_service = InMemorySessionService()

JSON_PATH = "./jsons/company.json"
QUEUE_PATH = "./jsons/screening_queue.json"
RESULTS_PATH = "./jsons/screening_results.json"
TOKEN_PATH = "./jsons/token_usage.json"

# ---- global token tracker ----
tracker = TokenTracker()

# Map file_type strings to the agent name stored in the JSON
AGENT_NAME_MAP = {
    "ssm": "SSM_agent",
    "annual return": "AR_agent",
    "ar": "AR_agent",
    "audited financial statements": "AF_agent",
    "afs": "AF_agent",
}

def log_event_tokens(event, label: str = ""):
    """Extract and print token counts from an event. Returns (input, output, total)."""
    usage = getattr(event, "usage_metadata", None)
    author = getattr(event, "author", "unknown")

    if usage is None:
        print(
            f"author={author} final={event.is_final_response()} "
            "(no usage_metadata)"
        )
        return 0, 0, 0

    input_tokens = getattr(usage, "prompt_token_count", 0) or 0
    output_tokens = getattr(usage, "candidates_token_count", 0) or 0
    total_tokens = getattr(usage, "total_token_count", 0) or 0

    print(
        f"[{label}] "
        f"author={author} "
        f"in={input_tokens} out={output_tokens} total={total_tokens}"
    )

    return input_tokens, output_tokens, total_tokens


APP_NAME = "document_extractor"
SCREENING_APP_NAME = "artemis_screening"
USER_ID = "system"


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
    filename = os.path.basename(file_path)
    agent_name = AGENT_NAME_MAP.get(file_type.lower(), "unknown_agent")

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
        if event.is_final_response() and event.content.parts:
            final_json = event.content.parts[0].text
        
        in_tok, out_tok, total_tok = log_event_tokens(event, label="process_pdf")

        # Record extraction tokens for this file
        tracker.record_extraction(
            filename=filename,
            agent_name=agent_name,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=total_tok,
        )
       
    return final_json

#-----------------Screening helpers--------------------------
def _strip_code_fence(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    return match.group(1).strip() if match else text

async def screen_entry(entry: dict, source_filename: str) -> dict:
    """Send ONE screening queue entry to the Artemis agent and return its parsed JSON."""
    session = await session_service.create_session(app_name=SCREENING_APP_NAME, user_id=USER_ID)

    message = types.Content(
        role="user",
        parts=[types.Part(text=json.dumps(entry))],
    )

    # Accumulate tokens for this single screening call
    screening_in = 0
    screening_out = 0
    screening_total = 0

    final_text = None
    async for event in artemis_runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=message,
    ):
        if event.is_final_response() and event.content.parts:
            final_text = event.content.parts[0].text

        in_tok, out_tok, total_tok = log_event_tokens(event, label="screen_entry")
        screening_in += in_tok
        screening_out += out_tok
        screening_total += total_tok
        
    if final_text is None:
        raise RuntimeError(f"No response from agent for queue_id={entry.get('queue_id')}")

    # Record screening tokens for one entity, tied back to its source file
    tracker.record_screening(
        filename=source_filename,
        agent_name="artemis_agent",
        input_tokens=screening_in,
        output_tokens=screening_out,
        total_tokens=screening_total,
        entities_screened=1,
    )

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
    queue_path: str = QUEUE_PATH,
    results_path: str = RESULTS_PATH,
    source_filename: str = "",
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
            result = await screen_entry(entry, source_filename=source_filename)
            results_data["screening_results"].extend(result.get("screening_results", []))
            results_data["processing_notes"].extend(result.get("processing_notes", []))
            results_data["summary"] = result.get("summary", results_data["summary"])
            save_screening_results(results_data, results_path)  # save after every entry
            already_done.add(queue_id)
            print(f"Screened {queue_id} ({entry.get('search_name')})")
        except Exception as e:
            print(f"Error screening {queue_id} ({entry.get('search_name')}): {e}")

#-----------------Pipeline--------------------------
async def run_pipeline(uploads_dir: str):
    for filename in os.listdir(uploads_dir):
        if not filename.endswith(".pdf"):
            continue

        pdf_path = os.path.join(uploads_dir, filename)
        file_type = pre_filter_documents(pdf_path)

        try:
            result = await process_pdf(pdf_path, file_type)

            #print(result)
            save_company_json(result, JSON_PATH)
            os.remove(pdf_path)
            build_screening_queue(JSON_PATH, QUEUE_PATH)
            await screen_new_queue_entries(QUEUE_PATH, RESULTS_PATH, source_filename=filename)

        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")

    # Save token usage before generating the final PDF
    tracker.save(TOKEN_PATH)

    data = extract_data(JSON_PATH, RESULTS_PATH)
    output_pdf = generate_kyc_pdf(data, "./output/result_KYC.pdf")
    print(f"KYC PDF generated: {output_pdf}")
    os.remove(JSON_PATH)
    os.remove(QUEUE_PATH)
    os.remove(RESULTS_PATH)

if __name__ == "__main__":
    asyncio.run(run_pipeline("./uploads"))