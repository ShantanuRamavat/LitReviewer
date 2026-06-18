"""LLM provider implementations.

Each module in this package implements ``BaseLLMProvider`` for a specific
LLM vendor.  Add a new file here when integrating a new provider — no other
files need to change except ``app/llm/client.py``.

Current providers
-----------------
- ``groq``      — Groq (llama-3.3-70b-versatile) via ``langchain-groq`` — primary
- ``anthropic`` — Anthropic Claude via ``langchain-anthropic`` — alternative
"""
