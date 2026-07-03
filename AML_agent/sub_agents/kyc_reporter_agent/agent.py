from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from tools import read_pdf

load_dotenv()

MODEL = LiteLlm("openai/gpt-4o-mini")