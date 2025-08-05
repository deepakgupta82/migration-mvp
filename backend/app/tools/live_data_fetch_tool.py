from crewai_tools import BaseTool
import requests

class LiveDataFetchTool(BaseTool):
    name: str = "Live Data Fetch Tool"
    description: str = "Fetches real-time data from cloud provider APIs or other live sources."

    def _run(self, source_url: str) -> str:
        """Fetches data from a given URL."""
        try:
            response = requests.get(source_url)
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.text
        except requests.exceptions.RequestException as e:
            return f"Error fetching data: {e}"
