from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic_ai import Agent

import takehome.config  # noqa: F401 — triggers ANTHROPIC_API_KEY export
from takehome.services.prompts import QA_SYSTEM_PROMPT, REPORT_SYSTEM_PROMPT

title_agent = Agent(
    "anthropic:claude-haiku-4-5-20251001",
    system_prompt="Generate concise conversation titles.",
)

qa_agent = Agent(
    "anthropic:claude-haiku-4-5-20251001",
    system_prompt=QA_SYSTEM_PROMPT,
)

report_agent = Agent(
    "anthropic:claude-haiku-4-5-20251001",
    system_prompt=REPORT_SYSTEM_PROMPT,
)


async def generate_title(user_message: str) -> str:
    """Generate a 3-5 word conversation title from the first user message."""
    result = await title_agent.run(
        f"Generate a concise 3-5 word title for a conversation that starts with: '{user_message}'. "
        "Return only the title, nothing else."
    )
    title = str(result.output).strip().strip('"').strip("'")
    if len(title) > 100:
        title = title[:97] + "..."
    return title


async def generate_report(
    retrieved_context: str,
    document_names: list[str],
) -> AsyncIterator[str]:
    """Stream a structured property analysis report from the retrieved document context."""
    prompt_parts: list[str] = []

    if retrieved_context:
        prompt_parts.append(
            "The following are relevant pages from the document bundle:\n\n"
            f"{retrieved_context}\n\n"
            f"Documents in this conversation: {', '.join(document_names)}\n"
        )
    else:
        prompt_parts.append(
            "No documents have been uploaded yet. Cannot generate a report without documents.\n"
        )

    prompt_parts.append(
        "Generate a comprehensive structured property analysis report based on the documents above."
    )

    full_prompt = "\n".join(prompt_parts)

    async with report_agent.run_stream(full_prompt) as result:
        async for text in result.stream_text(delta=True):
            yield text


async def chat_with_documents(
    user_message: str,
    retrieved_context: str,
    document_names: list[str],
    conversation_history: list[dict[str, str]],
    confidence: str = "high",
) -> AsyncIterator[str]:
    """Stream a response to the user's message with citation-grounded answers."""
    prompt_parts: list[str] = []

    if confidence == "low":
        prompt_parts.append(
            "IMPORTANT: The retrieved context may not fully cover this query. "
            "If you cannot find a clear answer in the provided pages, explicitly state "
            "that the information is not available in the uploaded documents rather than speculating.\n"
        )

    if retrieved_context:
        prompt_parts.append(
            "The following are relevant pages from the document bundle:\n\n"
            f"{retrieved_context}\n\n"
            f"Documents in this conversation: {', '.join(document_names)}\n"
        )
    else:
        prompt_parts.append(
            "No documents have been uploaded yet. If the user asks about a document, "
            "let them know they need to upload one first.\n"
        )

    if conversation_history:
        prompt_parts.append("Previous conversation:\n")
        for msg in conversation_history:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                prompt_parts.append(f"User: {content}\n")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}\n")
        prompt_parts.append("\n")

    prompt_parts.append(f"User: {user_message}")

    full_prompt = "\n".join(prompt_parts)

    async with qa_agent.run_stream(full_prompt) as result:
        async for text in result.stream_text(delta=True):
            yield text
