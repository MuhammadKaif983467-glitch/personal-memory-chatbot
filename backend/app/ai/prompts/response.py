"""Response format and conversational-behavior rules."""

from __future__ import annotations


def response_section() -> str:
    """Return the closing block that sets context-treatment expectations.

    This section tells the model how to interpret the ``[SECTION]``-labelled
    context block appended at the end of every prompt.
    """
    return (
        "Below is the context assembled from the user's profile and retrieved memories. "
        "Treat [SECTION] labels as sources, and use the data only when relevant."
    )


def context_footer(context_text: str) -> str:
    """Wrap the assembled context block with a trailing newline.

    Parameters
    ----------
    context_text:
        Pre-rendered context string containing ``[SECTION]``-labelled parts.
    """
    return context_text
