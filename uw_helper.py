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
            # Graph resumes here after interrupt
            # company_name and cin have been injected into state 
            # by the Gradio interface before resuming
            
            return {}

    def make_thread_id(self) -> str:
        return str(uuid.uuid4())
  

    def format_trends_for_display(self, trends: List[Trend]) -> List[List]:
        """Convert trends from state to dataframe rows"""
        return [[t.observation, t.supporting_data, t.severity.value] for t in trends]

    def format_queries_for_display(self, queries: List[Query]) -> List[List]:
        """Convert queries from state to dataframe rows"""
        return [[q.question, q.category.value] for q in queries]

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
        """Step 1 — run ingestion and analyst"""

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
            "go_nogo": None
        }

        # Run graph — will pause at human_input interrupt
        await self.graph.ainvoke(state, config=config)

        # Pull Agent 1 output from checkpointed state
        checkpointed = self.graph.get_state(config)
        trends = checkpointed.values["trends"]
        queries = checkpointed.values["queries"]

        trends_display = self.format_trends_for_display(trends)
        queries_display = self.format_queries_for_display(queries)

        return trends_display, queries_display


    async def run_agent2_step(self, trends_data, queries_data, company_name, cin, thread_id):
        """Step 3 — resume graph with named entity inputs and edited tables"""

        config = {"configurable": {"thread_id": thread_id}}

        # Parse edited tables back to Pydantic objects
        trends = self.parse_trends_from_display(trends_data.values.tolist())
        queries = self.parse_queries_from_display(queries_data.values.tolist())

        # Inject all inputs into checkpointed state before resuming
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
