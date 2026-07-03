from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import AgentTool

# from sub_agents.AR_agent import AR_agent
# from sub_agents.AF_agent import AF_agent
# from sub_agents.SSM_agent import SSM_agent

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

load_dotenv()

MODEL = LiteLlm("openai/gpt-4o-mini")

extraction_agent = Agent(
    name="doc_extraction_agent",
    model=MODEL,
    # tools = [
    #     AgentTool(agent = ssm_extractor),
    #     AgentTool(agent = annual_return_extractor),
    #     AgentTool(agent = afs_extractor),
    # ],
    instruction="""
You are responsible for routing extraction tasks.

You will receive:
- file_path
- document_type

If document_type is:
- "ssm": call the ssm_extractor tool.
- "annual return" or "ar": call the annual_return_extractor tool.
- "audited financial statements" or "afs": call the afs_extractor tool.

Call exactly one extraction tool based on the document type.
Return the tool's response without modification.
""",
)