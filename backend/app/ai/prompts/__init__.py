"""Modular prompt construction for the chat model.

Re-exports ``build_system_prompt`` so that existing imports like
``from app.ai.prompts import build_system_prompt`` continue to work.
"""

from app.ai.prompts.base import build_system_prompt

__all__ = ["build_system_prompt"]
