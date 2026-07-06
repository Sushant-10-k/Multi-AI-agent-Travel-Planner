from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights
from backend import run_travel_agent

# res = tavily_search("Best rating holtels in India")
# print(res)

# res = search_flights("Plan a 10 days US trip from India with a budget of 2000 USD")
# print(res)

user_input = input("Enter your travel query: ")

response = run_travel_agent(
    user_input=user_input,
    thread_id="test_thread",
    )

print("\n\nFinal Itinerary:\n")
print(response["answer"])