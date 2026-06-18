"""
Agent layer — LangGraph-based AI agents.

Each agent is a self-contained subgraph that can be:
- Run standalone for testing
- Composed as a node inside the outer orchestration graph

Available agents:
- ``app.agents.research`` — ResearchAgent: plan → RAG search → web search → findings
"""
