import json
from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.graph.message import add_messages 
from enum import Enum

from tools import news_search, court_search, industry_outlook

class GoNoGo(str, Enum):
    GO = "go"
    NOGO = "nogo"
    NEEDSMORE = "needsmoreresearch"

class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class QueryCategory(str, Enum):
    ONLINE_RESOLVABLE = "online_resolvable"
    DOCUMENT_REQUEST = "document_request"
    INTERNAL_ACCOUNTING = "internal_accounting"

class Trend(BaseModel):
    observation: str
    supporting_data: str
    severity: Severity # "high" | "medium" | "low"

class Query(BaseModel):
    question: str
    category: QueryCategory
    answer: Optional[str] = None
    resolvable: bool = True
    source: Optional[str] = None
    resolved: bool = False

class AnalystOutput(BaseModel):
    trends: List[Trend]
    queries: List[Query]
    director_names: Optional[List[str]]
    related_companies: Optional[List[str]]


class State(TypedDict):
    messages: Annotated[List[Any], add_messages]
    excel_path: Optional[str]
    cran_data: Optional[Dict]
    trends: Optional[List[Trend]]
    queries: Optional[List[Query]]
    company_name: Optional[str]
    cin: Optional[str]
    director_names: Optional[List[str]]
    related_companies: Optional[List[str]]
    go_nogo: Optional[GoNoGo]


researcher_tools = [news_search, court_search, industry_outlook] 

class Analyst:

    def __init__(self):
        self.llm_1 = ChatAnthropic(model="claude-sonnet-4-6", verbose=True)
        self.llm_1_with_structured_output = self.llm_1.with_structured_output(AnalystOutput)

    def analyst(self, state):
        cran_data = state["cran_data"]
        
        # Build data section broken out by category
        data_sections = ""
        for sheet_name, sheet_info in cran_data.items():
            category = sheet_info["category"]
            data = sheet_info["data"]
            data_sections += f"\n\n### {category.upper()} (Sheet: {sheet_name})\n"
            data_sections += json.dumps(data, indent=2)

        # SYSTEM PROMPT REDACTED
        # Analyst system prompt instructs the LLM to perform financial anomaly detection
        # and bureau signal interpretation over CRAN data, and extract director names
        # and related companies for downstream research. Loaded from config in production.
        system_message = ""

        user_message = f"""Here is the CRAN data:\n{data_sections}"""

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_message)
        ]

        response = self.llm_1_with_structured_output.invoke(messages)

        return {
            "trends": response.trends,
            "queries": response.queries,
            "director_names": response.director_names,
            "related_companies": response.related_companies
        }


class Researcher:

    def __init__(self):
        self.llm_2 = ChatOpenAI(model="gpt-4o", verbose=True)
        self.llm_2_with_tools = self.llm_2.bind_tools(researcher_tools)

    def extract_go_nogo(self, response) -> GoNoGo:
        content = response.content.upper()
        if "RECOMMENDED STANCE: NOGO" in content:
            return GoNoGo.NOGO
        elif "RECOMMENDED STANCE: NEEDS FURTHER RESEARCH" in content:
            return GoNoGo.NEEDSMORE
        elif "RECOMMENDED STANCE: GO" in content:
            return GoNoGo.GO
        else:
            return GoNoGo.NEEDSMORE  # safe default if parsing fails

    def researcher(self, state):
        company_name = state["company_name"]
        cin = state["cin"]
        trends = state["trends"]
        queries = state["queries"]
        director_names = state["director_names"]
        related_companies = state["related_companies"]

        # Format trends for prompt
        trends_text = ""
        for i, trend in enumerate(trends, 1):
            trends_text += f"\n{i}. [{trend.severity.value.upper()}] {trend.observation}\n"
            trends_text += f"   Supporting data: {trend.supporting_data}\n"

        # Format queries for prompt
        queries_text = ""
        for i, query in enumerate(queries, 1):
            queries_text += f"\n{i}. [{query.category.value}] {query.question}\n"

        # Pre-generate the full search agenda as a checklist
        search_agenda = ""

        # Primary company
        search_agenda += f"\nPRIMARY COMPANY: {company_name} (CIN: {cin})\n"
        search_agenda += f"  [ ] News search: recent and historical news about {company_name}\n"
        search_agenda += f"  [ ] Court search: litigation, NCLT, DRT, enforcement actions for {company_name}\n"
        search_agenda += f"  [ ] Industry outlook: sector health and regulatory environment\n"

        # Each director individually
        if director_names:
            search_agenda += f"\nDIRECTORS — research each individually:\n"
            for director in director_names:
                search_agenda += f"\n  {director}:\n"
                search_agenda += f"  [ ] News search: recent and historical news about {director}\n"
                search_agenda += f"  [ ] Court search: litigation, NCLT, DRT, enforcement actions for {director}\n"

        # Each related company individually
        if related_companies:
            search_agenda += f"\nRELATED / GROUP COMPANIES — research each individually:\n"
            for company in related_companies:
                search_agenda += f"\n  {company}:\n"
                search_agenda += f"  [ ] News search: recent and historical news about {company}\n"
                search_agenda += f"  [ ] Court search: litigation, NCLT, DRT, enforcement actions for {company}\n"

        # SYSTEM PROMPT REDACTED
        # Researcher system prompt instructs the LLM to work through the search agenda
        # systematically, resolve online-resolvable queries, and produce a structured
        # intelligence brief ending with a parseable RECOMMENDED STANCE line.
        # Loaded from config in production.
        system_message = ""

        user_message = f"""SEARCH AGENDA — complete every item before synthesising:
        {search_agenda}

        FINANCIAL ANOMALIES FLAGGED BY ANALYST:
        {trends_text}

        QUERIES TO RESOLVE:
        {queries_text}

        Begin working through the search agenda now, starting with the primary company."""

        messages = state["messages"] + [
            SystemMessage(content=system_message),
            HumanMessage(content=user_message)
        ]

        response = self.llm_2_with_tools.invoke(messages)

        if not response.tool_calls:
            return {
                "messages": [response],
                "go_nogo": self.extract_go_nogo(response)
            }

        return {"messages": [response]}
