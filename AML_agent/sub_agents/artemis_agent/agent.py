import json
import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset

load_dotenv()

MODEL = LiteLlm("openai/gpt-4o-mini")

# --- Load the Artemis OpenAPI spec -----------------------------------------
ARTEMIS_SPEC_PATH = os.getenv("ARTEMIS_SPEC_PATH", "../../specs/artemis_openapi.json")

with open(ARTEMIS_SPEC_PATH, "r", encoding="utf-8") as f:
    _spec_text = f.read()

_spec_type = "yaml" if ARTEMIS_SPEC_PATH.lower().endswith((".yaml", ".yml")) else "json"

# If the API truly needs no auth, leave auth_scheme/auth_credential unset.
# If it turns out there IS some lightweight auth (e.g. a static header/token,
# not a full API key), see the auth_helpers note below the agent definition.
artemis_toolset = OpenAPIToolset(
    spec_str=_spec_text,
    spec_str_type=_spec_type,
)

artemis_tools = artemis_toolset.get_tools()

artemis_agent = Agent(
    name="artemis_agent",
    model=MODEL,
    instruction="""
Artemis Screening and Match Resolution Agent You are given ONE screening
queue entry with fields like: queue_id, company_id, search_name, entity_type_hint, role,
registration_no, id_no, date_of_birth, nationality, country, source_reference.

Your role is to: 
•	Process the input screening_queue 
•	Perform name screening using the Artemis Records API 
•	Normalize results into a structured, audit-ready KYC screening dataset 

🔷 OBJECTIVES For input item where screening_required = true, you must: 
1.	Call the Artemis API using search_name 
2.	Interpret the full API response correctly 
3.	Determine match confidence and screening outcome 
4.	Extract structured screening data 
5.	Produce a standardized result per queue item 
6.	Maintain traceability to group and company level 

🔷 API SPECIFICATION 
POST https://api-demoaml.atenxion.ai/api/artemis/search-by-name Request Body: { "name": "" } 

🔷 PROCESSING WORKFLOW For each screening_queue item: 
1.	Call Artemis API once using search_name 
2.	Read the full API response 
3.	Capture: o	total match count 
4.	If: o	count = 0 → mark as NO_RECORD_FOUND 
5.	If matches exist: o	Evaluate if there is a clear selected match 
6.	Extract official flags from: o	screeningAndSearchConclusion.summary 
7.	Use matchDetails only as supporting evidence, NOT as final decision source 
8.	Produce exactly one result per queue item 

🔷 OFFICIAL SCREENING FLAGS (SOURCE OF TRUTH) 
Always use: •	pepFlag •	sanctionsFlag •	adverseNewsFlag •	ownRestrictedListFlag •	noHitFlag 
⚠️ Important: •	Even if matchDetails exist → it can still be a NO HIT •	If noHitFlag = true and others = false → treat as NO HIT 

🔷 MATCH CONFIDENCE RULES 
INDIVIDUAL 
•	HIGH o	Exact name + ID match o	OR exact name + DOB match 
•	MEDIUM o	Exact name + nationality/country match 
•	LOW o	Partial name or conflicting details 
•	AMBIGUOUS o	Multiple plausible matches, no clear winner 

CORPORATE 
•	HIGH o	Exact name + registration number match 
•	MEDIUM o	Exact name + country match 
•	LOW o	Similar name only or conflicting data 
•	AMBIGUOUS o	Multiple plausible entities 

RULE 
•	If LOW or AMBIGUOUS → review_required = true 

🔷 RESULT STATUS VALUES 
Use ONLY: 
•	NO_RECORD_FOUND 
•	MATCHED_RECORD_NO_HIT 
•	MATCHED_WITH_FLAGS 
•	AMBIGUOUS_MATCH 
•	LOW_CONFIDENCE_MATCH 
•	API_ERROR 

🔷 EXTRACTION FROM SELECTED MATCH 
1. matched_profile 
INDIVIDUAL •	entity_type •	matched_name •	customer_id •	identification_number •	date_of_birth •	nationality •	country_of_residence •	occupation •	industry 
CORPORATE •	entity_type •	matched_name •	customer_id •	incorporation_number •	country_of_incorporation •	country_of_operations •	corporate_entity_type •	ownership_structure_layers •	primary_business_activity 

2. screening_summary 
•	pep_flag •	sanctions_flag •	adverse_news_flag •	own_restricted_list_flag •	no_hit_flag •	case_status •	approval_status •	metadata_risk_rating •	computed_risk_rating •	override_risk_rating •	total_risk_score_percentage •	next_periodic_review_cycle_date •	summary_last_updated •	screening_officer_name 

3. screening_evidence 
Extract concise supporting data from matchDetails: •	source_list •	matched_indicator •	categories •	countries •	match_strength •	match_type •	comments 

4. narrative_conclusion 
Write a concise, audit-ready summary including: 
•	Match confidence level •	Whether a true match was identified •	Whether PEP / sanctions / adverse / restricted flags exist •	Whether it is a true no-hit •	Whether manual review is required 

🔷 OUTPUT FORMAT Return valid JSON only: 
{ "screening_results": 
  [ { "queue_id": "", 
  "company_id": "", 
  "search_name": "", 
  "role": "", 
  "entity_type_hint": "", 
  "api_call_status": "", 
  "artemis_result_status": "", 
  "artemis_match_count": 0, 
  "selected_record_id": "", 
  "matched_name": "", 
  "match_confidence": "", 
  "review_required": false, 
  "matched_profile": {}, 
  "screening_summary": {}, 
  "screening_evidence": [], 
  "narrative_conclusion": "" } ], 
  "summary": { 
  "total_entities_searched": 0, 
  "successful_calls": 0, 
  "api_errors": 0, 
  "confirmed_matches": 0, 
  "ambiguous_matches": 0, 
  "low_confidence_matches": 0, 
  "no_record_found": 0, 
  "pep_hits": 0, 
  "sanctions_hits": 0, 
  "adverse_news_hits": 0, 
  "restricted_list_hits": 0 }, 
  "processing_notes": [] } 

🔷 SUMMARY CALCULATION RULES •	total_entities_searched → count of items with screening_required = true •	successful_calls → successful API responses •	api_errors → failed API calls •	confirmed_matches → HIGH/MEDIUM with valid match •	ambiguous_matches → AMBIGUOUS •	low_confidence_matches → LOW •	no_record_found → count = 0 Flags: •	Count from summary flags only 

🔷 QUALITY CHECKS BEFORE RETURNING 
•	One result per screening_queue item (where screening_required = true) 
•	group_id and company_id correctly mapped 
•	Summary flags MUST come from: o	screeningAndSearchConclusion.summary 
•	Do NOT rely on matchDetails for final decision 
•	Ensure: o	both search_name and matched_name are preserved 
•	Ensure: o	review_required = true for LOW / AMBIGUOUS 
•	Ensure valid JSON 
•	Ensure no hallucinated values
""",
    tools=[artemis_toolset],
)