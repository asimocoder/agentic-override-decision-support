
import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from tavily import TavilyClient
from datetime import datetime, date

load_dotenv(override=True)
TODAY = datetime.now().strftime("%d-%m-%Y")

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

@tool
def news_search(query: str):
    """Search for recent and historical news about an MSME company 
    or its directors. Use this to find adverse media, business 
    developments, or reputational signals."""
    results = tavily.search(f"{query}. Note that today is {TODAY}.", max_results=5)

    return str(results)

@tool
def court_search(query: str):
    """Search for court cases, legal proceedings, insolvency filings,
    or enforcement actions involving an MSME company or its directors.
    Covers eCourts, NCLT, DRT, and SEBI enforcement orders, pertaining
    to an MSME company."""
    results = tavily.search(f"{query}. Note that today is {TODAY}.", max_results=5)

    return str(results)

@tool
def industry_outlook(query: str):
    """Search for sector-level information — industry health, regulatory 
    changes, commodity price movements, and peer company signals relevant 
    to an MSME borrower's business context."""
    results = tavily.search(f"{query}. Note that today is {TODAY}.", max_results=5)

    return str(results)


# @tool
# def mca21_lookup(cin: str) -> str:
#     """Look up live company details from MCA21 using the CIN.
#     Use this to verify and supplement company information already
#     present in the credit assessment — specifically to catch recent
#     director changes, newly filed charges, or associated entities
#     not captured at the time of data pull. Most useful when the
#     credit assessment data may be stale or incomplete.
#     Always call this before running any external searches."""
#     # Mock during development
#     return f"MCA21 data for CIN {cin} — mock response"
