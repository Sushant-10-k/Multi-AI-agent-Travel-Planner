import unittest
from unittest.mock import MagicMock, patch

from tools.flight_tool import search_flights


class FlightToolTests(unittest.TestCase):
    @patch("tools.flight_tool.requests.get")
    def test_search_flights_prefers_serpapi_when_key_exists(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "best_flights": [
                {
                    "price": {"amount": "120"},
                    "flights": [{"segments": [{"airline": "Air India"}]}],
                }
            ]
        }
        mock_get.return_value = mock_response

        with patch("tools.flight_tool.SERPAPI_API_KEY", "demo-serpapi-key"):
            result = search_flights("Flights from Delhi to Tokyo")

        self.assertIn("SerpAPI", result)
        self.assertIn("DEL", result)
        self.assertIn("NRT", result)
        mock_get.assert_called_once()
        self.assertIn("serpapi.com/search.json", mock_get.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
