from __future__ import annotations

import json
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from takehome.db.models import Citation, Document, Message
from takehome.db.session import get_session
from takehome.schemas.messages import CitationOut, MessageCreate, MessageOut
from takehome.services.citations import normalize_name, parse_citations, validate_citations
from takehome.services.conversation import get_conversation, update_conversation
from takehome.services.document import (
    get_document_pages_for_conversation,
    get_documents_for_conversation,
)
from takehome.services.llm import chat_with_documents, generate_report, generate_title
from takehome.services.retrieval import retrieve_context

logger = structlog.get_logger()

router = APIRouter(tags=["messages"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _build_doc_maps(documents: list[Document]) -> tuple[dict[str, Document], dict[str, str]]:
    """Build normalized name→Document map and id→display name map."""
    normalized_map: dict[str, Document] = {}
    id_to_name: dict[str, str] = {}
    for d in documents:
        name = d.filename.replace(".pdf", "").replace(".PDF", "")
        normalized_map[normalize_name(name)] = d
        id_to_name[d.id] = name
    return normalized_map, id_to_name


async def _save_message_and_citations(
    full_response: str,
    conversation_id: str,
    message_type: str,
    documents: list[Document],
    all_pages: list,
    doc_normalized_map: dict[str, Document],
    doc_id_to_name: dict[str, str],
) -> tuple[Message, list[dict]]:
    """Parse citations, save message + citation records, return message and citations for SSE."""
    from takehome.db.session import async_session as session_factory

    parsed = parse_citations(full_response)
    validated = validate_citations(parsed, documents, all_pages)
    sources_count = sum(1 for c in validated if c.status != "dropped")

    async with session_factory() as save_session:
        assistant_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=full_response,
            sources_cited=sources_count,
            message_type=message_type,
        )
        save_session.add(assistant_message)
        await save_session.flush()

        citation_records: list[Citation] = []
        for pc in validated:
            if pc.status == "dropped":
                continue
            matched_doc: Document | None = None
            pc_normalized = normalize_name(pc.document_name)
            for key, doc in doc_normalized_map.items():
                if pc_normalized in key or key in pc_normalized:
                    matched_doc = doc
                    break
            if matched_doc:
                citation_records.append(
                    Citation(
                        message_id=assistant_message.id,
                        document_id=matched_doc.id,
                        page_number=pc.page_number,
                        clause=pc.clause,
                        status=pc.status,
                    )
                )

        if citation_records:
            save_session.add_all(citation_records)

        await save_session.commit()
        await save_session.refresh(assistant_message)

    citations_out = [
        {
            "id": c.id,
            "document_id": c.document_id,
            "document_name": doc_id_to_name.get(c.document_id, "Unknown"),
            "page_number": c.page_number,
            "clause": c.clause,
        }
        for c in citation_records
        if c.status == "verified"
    ]

    return assistant_message, citations_out


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@router.get(
    "/api/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
)
async def list_messages(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[MessageOut]:
    """List all messages in a conversation, ordered by creation time."""
    conversation = await get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    result = await session.execute(stmt)
    messages = list(result.scalars().all())

    # Load documents for citation name resolution
    documents = await get_documents_for_conversation(session, conversation_id)
    _, doc_id_to_name = _build_doc_maps(documents)

    # Load citations for all messages in one query
    message_ids = [m.id for m in messages]
    citations_by_message: dict[str, list[CitationOut]] = {mid: [] for mid in message_ids}
    if message_ids:
        cite_stmt = select(Citation).where(Citation.message_id.in_(message_ids))
        cite_result = await session.execute(cite_stmt)
        for c in cite_result.scalars().all():
            if c.status == "verified":
                citations_by_message[c.message_id].append(
                    CitationOut(
                        id=c.id,
                        document_id=c.document_id,
                        document_name=doc_id_to_name.get(c.document_id, "Unknown"),
                        page_number=c.page_number,
                        clause=c.clause,
                    )
                )

    return [
        MessageOut(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            sources_cited=m.sources_cited,
            message_type=m.message_type,
            citations=citations_by_message.get(m.id, []),
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.post("/api/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: MessageCreate,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Send a user message and stream back the AI response via SSE."""
    conversation = await get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Save the user message
    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=body.content,
    )
    session.add(user_message)
    await session.commit()
    await session.refresh(user_message)

    logger.info("User message saved", conversation_id=conversation_id, message_id=user_message.id)

    # Load all documents for the conversation
    documents = await get_documents_for_conversation(session, conversation_id)
    document_names = [d.filename.replace(".pdf", "").replace(".PDF", "") for d in documents]
    doc_normalized_map, doc_id_to_name = _build_doc_maps(documents)

    # Run retrieval pipeline
    retrieved_context, _pages_used, confidence = await retrieve_context(
        session, conversation_id, body.content
    )

    # Load conversation history
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .where(Message.id != user_message.id)
        .order_by(Message.created_at.asc())
    )
    result = await session.execute(stmt)
    history_messages = list(result.scalars().all())

    conversation_history: list[dict[str, str]] = [
        {"role": m.role, "content": m.content} for m in history_messages
    ]

    user_msg_count = sum(1 for m in history_messages if m.role == "user")
    is_first_message = user_msg_count == 0

    # Pre-load pages for citation validation
    all_pages = await get_document_pages_for_conversation(session, conversation_id)

    async def event_stream() -> AsyncIterator[str]:
        """Generate SSE events with the streamed LLM response."""
        full_response = ""

        try:
            async for chunk in chat_with_documents(
                user_message=body.content,
                retrieved_context=retrieved_context,
                document_names=document_names,
                conversation_history=conversation_history,
                confidence=confidence,
            ):
                full_response += chunk
                event_data = json.dumps({"type": "content", "content": chunk})
                yield f"data: {event_data}\n\n"

        except Exception:
            logger.exception(
                "Error during LLM streaming",
                conversation_id=conversation_id,
            )
            error_msg = "I'm sorry, an error occurred while generating a response. Please try again."
            full_response = error_msg
            event_data = json.dumps({"type": "content", "content": error_msg})
            yield f"data: {event_data}\n\n"

        # Save message and citations
        assistant_message, citations_out = await _save_message_and_citations(
            full_response=full_response,
            conversation_id=conversation_id,
            message_type="chat",
            documents=documents,
            all_pages=all_pages,
            doc_normalized_map=doc_normalized_map,
            doc_id_to_name=doc_id_to_name,
        )

        # Auto-generate title from first user message
        if is_first_message:
            try:
                from takehome.db.session import async_session as session_factory

                async with session_factory() as title_session:
                    title = await generate_title(body.content)
                    await update_conversation(title_session, conversation_id, title)
            except Exception:
                logger.exception("Failed to generate title", conversation_id=conversation_id)

        message_data = json.dumps(
            {
                "type": "message",
                "message": {
                    "id": assistant_message.id,
                    "conversation_id": assistant_message.conversation_id,
                    "role": assistant_message.role,
                    "content": assistant_message.content,
                    "sources_cited": assistant_message.sources_cited,
                    "message_type": assistant_message.message_type,
                    "citations": citations_out,
                    "created_at": assistant_message.created_at.isoformat(),
                },
            }
        )
        yield f"data: {message_data}\n\n"

        done_data = json.dumps(
            {
                "type": "done",
                "sources_cited": assistant_message.sources_cited,
                "message_id": assistant_message.id,
                "confidence": confidence,
            }
        )
        yield f"data: {done_data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/conversations/{conversation_id}/report")
async def generate_report_endpoint(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Generate a structured property analysis report and stream it via SSE."""
    conversation = await get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Load all documents for the conversation
    documents = await get_documents_for_conversation(session, conversation_id)
    if not documents:
        raise HTTPException(status_code=400, detail="No documents uploaded for this conversation")

    document_names = [d.filename.replace(".pdf", "").replace(".PDF", "") for d in documents]
    doc_normalized_map, doc_id_to_name = _build_doc_maps(documents)

    # Run retrieval with a broad query to get comprehensive context
    retrieved_context, _pages_used, _confidence = await retrieve_context(
        session, conversation_id, "key property terms obligations risks dates financial rent lease"
    )

    # Pre-load pages for citation validation
    all_pages = await get_document_pages_for_conversation(session, conversation_id)

    async def event_stream() -> AsyncIterator[str]:
        """Generate SSE events with the streamed report response."""
        full_response = ""

        try:
            async for chunk in generate_report(
                retrieved_context=retrieved_context,
                document_names=document_names,
            ):
                full_response += chunk
                event_data = json.dumps({"type": "content", "content": chunk})
                yield f"data: {event_data}\n\n"

        except Exception:
            logger.exception(
                "Error during report generation",
                conversation_id=conversation_id,
            )
            error_msg = "I'm sorry, an error occurred while generating the report. Please try again."
            full_response = error_msg
            event_data = json.dumps({"type": "content", "content": error_msg})
            yield f"data: {event_data}\n\n"

        # Save message and citations
        assistant_message, citations_out = await _save_message_and_citations(
            full_response=full_response,
            conversation_id=conversation_id,
            message_type="report",
            documents=documents,
            all_pages=all_pages,
            doc_normalized_map=doc_normalized_map,
            doc_id_to_name=doc_id_to_name,
        )

        message_data = json.dumps(
            {
                "type": "message",
                "message": {
                    "id": assistant_message.id,
                    "conversation_id": assistant_message.conversation_id,
                    "role": assistant_message.role,
                    "content": assistant_message.content,
                    "sources_cited": assistant_message.sources_cited,
                    "message_type": assistant_message.message_type,
                    "citations": citations_out,
                    "created_at": assistant_message.created_at.isoformat(),
                },
            }
        )
        yield f"data: {message_data}\n\n"

        done_data = json.dumps(
            {
                "type": "done",
                "sources_cited": assistant_message.sources_cited,
                "message_id": assistant_message.id,
            }
        )
        yield f"data: {done_data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
