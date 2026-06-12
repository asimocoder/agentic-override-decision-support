import uuid
from dotenv import load_dotenv
from typing import List
from IPython.display import display, Markdown, Image
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from datetime import datetime, date

from data_ingestor import DataIngestor
from agents import Analyst, Researcher, researcher_tools, State, Trend, Query, Severity, QueryCategory
from docx_generator import generate_docx
from pdf_generator import generate_pdf

load_dotenv(override=True)
TODAY = datetime.now().strftime("%d-%m-%Y")

class UWHelper:
    """Underwriter Helper"""

    def __init__(self):
        self.data_ingestor = DataIngestor()
        self.analyst = Analyst()
        self.researcher = Researcher()
        self.tools = ToolNode(tools=researcher_tools)
        self.graph = self.build_graph()
   

    def build_graph(self):
        gbuilder = StateGraph(State)

        gbuilder.add_node("excel_ingestor", self.data_ingestor.excel_ingestor)
        gbuilder.add_node("analyst", self.analyst.analyst)
        gbuilder.add_node("human_input", self.human_input)
        gbuilder.add_node("researcher", self.researcher.researcher)
        gbuilder.add_node("tools", self.tools)

        gbuilder.add_edge(START, "excel_ingestor")
        gbuilder.add_edge("excel_ingestor", "analyst")
        gbuilder.add_edge("analyst", "human_input")
        gbuilder.add_edge("human_input", "researcher")
        gbuilder.add_conditional_edges("researcher", tools_condition)
        gbuilder.add_edge("tools", "researcher")
        gbuilder.add_edge("researcher", END)

        memory = MemorySaver()

        graph = gbuilder.compile(
            checkpointer=memory,
            interrupt_before=["human_input"]
        )

        try:
            display(Image(graph.get_graph().draw_mermaid_png()))
        except Exception:
            pass

        return graph


    def human_input(self, state):
        """
        Graph resumes here after interrupt.
        company_name and cin have been injected into state by the Gradio
        interface before resuming via graph.update_state().

        Restoration of real entity names from placeholders happens here —
        director_names and related_companies are restored before the
        Researcher runs. entity_mapping is real_name -> placeholder
        (built by DataIngestor); reverse is placeholder -> real_name.
        """
        entity_mapping = state.get("entity_mapping") or {}
        if not entity_mapping:
            return {}

        reverse_mapping = {placeholder: real_name for real_name, placeholder in entity_mapping.items()}

        director_names = state.get("director_names") or []
        related_companies = state.get("related_companies") or []

        return {
            "director_names": [reverse_mapping.get(name, name) for name in director_names],
            "related_companies": [reverse_mapping.get(name, name) for name in related_companies]
        }

    def make_thread_id(self) -> str:
        return str(uuid.uuid4())
  

    def format_trends_for_display(self, trends: List[Trend], entity_mapping: dict = None) -> List[List]:
        """Convert trends from state to dataframe rows.
        Applies reverse entity mapping so the human sees real names at Step 2,
        not PERSON_N / ENTITY_N placeholders.
        """
        reverse = {v: k for k, v in (entity_mapping or {}).items()}

        def restore(text: str) -> str:
            if not reverse or not isinstance(text, str):
                return text
            for placeholder, real_name in reverse.items():
                text = text.replace(placeholder, real_name)
            return text

        return [
            [restore(t.observation), restore(t.supporting_data), t.severity.value]
            for t in trends
        ]

    def format_queries_for_display(self, queries: List[Query], entity_mapping: dict = None) -> List[List]:
        """Convert queries from state to dataframe rows.
        Applies reverse entity mapping so the human sees real names at Step 2.
        """
        reverse = {v: k for k, v in (entity_mapping or {}).items()}

        def restore(text: str) -> str:
            if not reverse or not isinstance(text, str):
                return text
            for placeholder, real_name in reverse.items():
                text = text.replace(placeholder, real_name)
            return text

        return [
            [restore(q.question), q.category.value]
            for q in queries
        ]

    def parse_trends_from_display(self, rows: List[List]) -> List[Trend]:
        """Convert edited dataframe rows back to Trend objects"""
        trends = []
        for row in rows:
            if row[0]:  # skip empty rows
                trends.append(Trend(
                    observation=row[0],
                    supporting_data=row[1],
                    severity=Severity(row[2])
                ))
        return trends

    def parse_queries_from_display(self, rows: List[List]) -> List[Query]:
        """Convert edited dataframe rows back to Query objects"""
        queries = []
        for row in rows:
            if row[0]:  # skip empty rows
                queries.append(Query(
                    question=row[0],
                    category=QueryCategory(row[1])
                ))
        return queries


    async def run_agent1_step(self, excel_file, trigger_type, thread_id):
        """Step 1 — run ingestion and analyst.
        PII detection happens at upload time (scan_pii in app.py) before this is called.
        """

        config = {"configurable": {"thread_id": thread_id}}

        state = {
            "messages": [],
            "excel_path": excel_file.name,
            "cran_data": None,
            "trends": None,
            "queries": None,
            "company_name": None,
            "cin": None,
            "director_names": None,
            "related_companies": None,
            "go_nogo": None,
            "entity_mapping": None,
            "pii_warnings": None
        }

        # Run graph — will pause at human_input interrupt
        await self.graph.ainvoke(state, config=config)

        # Pull Agent 1 output from checkpointed state
        checkpointed = self.graph.get_state(config)
        trends = checkpointed.values["trends"]
        queries = checkpointed.values["queries"]
        entity_mapping = checkpointed.values.get("entity_mapping") or {}

        trends_display = self.format_trends_for_display(trends, entity_mapping)
        queries_display = self.format_queries_for_display(queries, entity_mapping)

        return trends_display, queries_display


    async def run_agent2_step(self, trends_data, queries_data, company_name, cin, thread_id):
        """Step 3 — resume graph with named entity inputs and edited tables"""

        config = {"configurable": {"thread_id": thread_id}}

        # Parse edited tables back to Pydantic objects
        trends = self.parse_trends_from_display(trends_data.values.tolist())
        queries = self.parse_queries_from_display(queries_data.values.tolist())

        # Inject all inputs into checkpointed state before resuming.
        # human_input node handles placeholder restoration on resume —
        # director_names and related_companies will have real names
        # before researcher runs.
        self.graph.update_state(config, {
            "company_name": company_name,
            "cin": cin,
            "trends": trends,
            "queries": queries
        })

        # Resume graph from human_input
        result = await self.graph.ainvoke(None, config=config)

        # Extract final brief from last message
        brief = result["messages"][-1].content
        go_nogo = result["go_nogo"].value.upper()

        return brief, go_nogo


    def generate_brief_docx(
        self,
        brief: str,
        go_nogo: str,
        company_name: str,
        trigger_type: str,
    ) -> str:
        """
        Generate a DOCX intelligence brief and return the file path.
        Called by the Gradio download button handler in app.py.
        """
        return generate_docx(
            brief=brief,
            go_nogo=go_nogo,
            company_name=company_name,
            trigger_type=trigger_type,
        )


    def generate_brief_pdf(
        self,
        brief: str,
        go_nogo: str,
        company_name: str,
        trigger_type: str,
    ) -> str:
        """
        Generate a PDF intelligence brief and return the file path.
        Requires LibreOffice to be installed.
        Called by the Gradio download button handler in app.py.
        """
        return generate_pdf(
            brief=brief,
            go_nogo=go_nogo,
            company_name=company_name,
            trigger_type=trigger_type,
        )
