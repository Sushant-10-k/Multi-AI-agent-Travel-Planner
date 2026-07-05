from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights

# res = tavily_search("Best rating holtels in India")
# print(res)

res = search_flights("Plan a 10 days US trip from India with a budget of 2000 USD")
print(res)