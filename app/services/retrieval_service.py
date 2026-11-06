"""
Knowledge Retrieval Service Abstraction for EduGenie.
Provides a pluggable interface for external knowledge retrieval and search,
ensuring transparency about offline vs. online search capabilities.
"""

from typing import Optional, List, Dict, Any
from app.core.config import settings, logger

class KnowledgeRetrievalService:
    """
    Manages external knowledge retrieval and web search integration.
    Default status is disabled/offline unless an active search provider is configured.
    """

    def __init__(self):
        self.enabled: bool = getattr(settings, "ENABLE_WEB_SEARCH", False)

    def is_available(self) -> bool:
        """Returns True if external search or live retrieval is currently configured and active."""
        return self.enabled

    def retrieve_context(self, query: str, max_results: int = 3) -> Dict[str, Any]:
        """
        Retrieves grounded evidence for a query if a search provider is configured.
        Returns a structured dictionary with retrieved sources or an offline indicator.
        """
        if not self.is_available():
            return {
                "available": False,
                "sources": [],
                "disclaimer": "Live web search is not currently enabled. Responses are generated from verified curriculum knowledge and Google Gemini training."
            }

        # Pluggable extension point for future search APIs (e.g., Tavily, Google Search Tool, or local Vector Store)
        logger.info("Search requested for query: %s (Provider: Configured search engine)", query[:50])
        return {
            "available": True,
            "sources": [],
            "disclaimer": ""
        }

retrieval_service = KnowledgeRetrievalService()
