from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from tools import read_pdf

load_dotenv()

MODEL = LiteLlm("openai/gpt-4o-mini")

SSM_agent = Agent(
    name="SSM_agent",
    model=MODEL,
    tools=[read_pdf],
    instruction="""
You are an SSM corporate registry extraction agent.

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

This document is an SSM document.

The SSM document is the authoritative source for:
- legal entity details
- incorporation details
- registered address
- company status
- company type
- principal place of business
- nature of business
- MSIC codes
- validation of directors
- validation of shareholders

Extract:

1. company_number

2. company_profile
•	company_name 
•	registration_no 
•	incorporation_date 
•	company_type 
•	legal_form 
•	status 
•	country_of_incorporation 
•	registered_address 
•	business_address 
•	principal_place_of_business 
•	address_of_financial_records_if_any 
•	nature_of_business 
•	msic_codes 
•	source_documents 

3. management_and_control_persons
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

4. shareholders_and_members
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

Do not infer information that is not explicitly stated.
""",
)