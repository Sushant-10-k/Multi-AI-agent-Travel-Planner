import os
import certifi
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from typing import TypedDict, Annotated
import operator
import uuid

import psycopg
from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langchain_groq import ChatGroq
from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. Please add your Render PostgreSQL External Database URL to .env"
        )

    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"

    return database_url



GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing. Please add it to your .env file.")


# # =========================
# # LLM
# # =========================

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY
)


# # =========================
# # State
# # =========================

class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_results: str
    hotel_results: str
    itinerary: str
    llm_calls: int


# # =========================
# # Fisrt Agent: Flight Search
# # Flight Agent
# # =========================

def flight_agent(state: TravelState):
    query = state["user_query"]
    flight_data = search_flights(query)

    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(content="Real time flight results are retrieved.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }



# # =========================
# # Second Agent: Hotel Search
# # Hotel Agent
# # =========================

def hotel_agent(state: TravelState):
    query = f"Best hotels for {state['user_query']}"
    hotel_results = tavily_search(query)

    return {
        "hotel_results": hotel_results,
        "messages": [
            AIMessage(content="Real time hotel information are retrieved.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }




# # =========================
# # Third Agent: Itinerary Generation
# # Itinerary Agent
# # =========================

def itinerary_agent(state: TravelState):
    prompt = f"""
Create a complete travel itinerary.

User Query:
{state['user_query']}

Flight Results:
{state['flight_results']}

Hotel Results:
{state['hotel_results']}

Instructions:
- Use INR for every price value in the itinerary and recommendations.
- Show all departure and arrival times in 12-hour format with AM or PM.
- Keep the itinerary practical, budget-aware, and easy to follow.
"""

    response = llm.invoke([
        SystemMessage(content="You are a Multi-AI agent travel planner."),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }



# # =========================
# # Fourth Agent: Final Response Generation
# # Final Response Agent
# # =========================

def final_agent(state: TravelState):
    flight_section = state.get("flight_results", "") or "No flight data available."
    hotel_section = state.get("hotel_results", "") or "No hotel data available."
    itinerary_section = state.get("itinerary", "") or "No itinerary generated yet."

    final_prompt = f"""
You are producing the final travel response for the user.

User Request:
{state['user_query']}

Flight Search Results (use this as the primary source for flight information):
{flight_section}

Hotel Search Results:
{hotel_section}

Itinerary Draft:
{itinerary_section}

Instructions:
- Present the flight information clearly and directly.
- Include a dedicated "Flight Information" section, and insert the raw flight search output exactly as shown above.
- Use INR for every price value in the final answer. Do not display prices in USD unless you also show the rupee equivalent.
- Display all departure and arrival times in 12-hour format with AM or PM.
- If the flight search results contain airline, route, price, or timing details, include them verbatim or closely paraphrase them without inventing new data.
- Do not replace the flight information with generic placeholder text like 'several options' unless no flight data is available.
- Preserve any bullet-point structure from the flight results.
- Keep the response structured with these sections:
1. Trip Summary
2. Flight Information
3. Hotel Suggestions
4. Day-by-Day Itinerary
5. Estimated Budget
6. Final Recommendations
"""

    response = llm.invoke([
        SystemMessage(content="You are a professional Multi-AI agent travel planner and booking assistant."),
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# # =========================
# # By LangGraph, we can define a state graph to manage the flow of our travel planning agents. Each agent will handle a specific part of the travel planning process, and the state graph will ensure that they are executed in the correct order.
# # Build Graph
# # =========================

graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)


# # =========================
# # PostgreSQL Checkpointer
# # =========================
DATABASE_URL = get_database_url()

_conn = psycopg.connect(
    DATABASE_URL,
    autocommit=True,
    row_factory=dict_row
)

checkpointer = PostgresSaver(_conn)
checkpointer.setup()

travel_graph = graph.compile(checkpointer=checkpointer)



# # =========================
# # Function for FastAPI
# # =========================

def run_travel_agent(user_input: str, thread_id: str | None = None):
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = travel_graph.invoke(
        {
            "messages": [
                HumanMessage(content=user_input)
            ],
            "user_query": user_input,
            "flight_results": "",
            "hotel_results": "",
            "itinerary": "",
            "llm_calls": 0
        },
        config=config
    )

    final_answer = result["messages"][-1].content

    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "itinerary": result.get("itinerary", ""),
        "llm_calls": result.get("llm_calls", 0),
    }