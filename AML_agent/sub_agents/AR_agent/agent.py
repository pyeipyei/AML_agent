from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from tools import read_pdf

load_dotenv()

MODEL = LiteLlm("openai/gpt-4o-mini")

###########################################
try:
    from langfuse import get_client

    langfuse = get_client()

    if langfuse.auth_check():
        print("Langfuse client is authenticated and ready!")
    else:
        print("Langfuse auth failed — tracing disabled.")

    from openinference.instrumentation.google_adk import GoogleADKInstrumentor
    GoogleADKInstrumentor().instrument()
except Exception as e:
    print(f"Langfuse not configured, skipping instrumentation: {e}")
#############################################

AR_agent = Agent(
    name="AR_agent",
    model=MODEL,
    tools=[read_pdf],
    instruction="""
You are an Annual Return extraction agent.

You will receive a local PDF file path.

Workflow (MANDATORY):

1. Call the `read_pdf` tool exactly ONE time using the provided file path.
2. Wait for the tool to return the PDF text.
3. The returned PDF text is the ONLY source of truth.
4. Read the returned text carefully.
5. Extract only the information requested below.
6. Do NOT call `read_pdf` again.
7. Do NOT ask for additional information.
8. If a field is not present, return null.
9. Return ONLY a JSON object matching the output schema.

Never call `read_pdf` more than once.

This document is an Annual Return.

The Annual Return is the authoritative source for:
- directors
- shareholders
- members
- current company structure
- beneficial ownership indicators

Extract:

1. company_number

2. management_and_control_persons
For each person:
•	full_name 
•	role 
•	id_type 
•	id_number 
•	date_of_birth 
•	nationality 
•	country_of_residence 
•	gender 
•	occupation 
•	residential_address 
•	service_address 
•	email 
•	source_documents 

3. shareholders_and_members
For each:
•	name 
•	member_type (INDIVIDUAL / CORPORATE) 
•	role 
•	registration_no_or_id_no 
•	nationality_or_country 
•	address 
•	shares_held 
•	share_class 
•	ownership_percent_if_available 
•	source_documents 

4. beneficial_owners
•	Identify natural persons with ultimate control 
•	Preserve explicitly stated BOs 
•	If inferred → include inference_basis 
Fields:
•	full_name 
•	id_number 
•	nationality 
•	control_basis 
•	ownership_percent_if_known 
•	inference_basis 
•	source_documents 

Do not invent ownership relationships that are unsupported by the document.
""",
)