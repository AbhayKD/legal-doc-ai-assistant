from __future__ import annotations

import os
import uuid

import fitz  # PyMuPDF
import structlog
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from takehome.config import settings
from takehome.db.models import Document, DocumentPage

logger = structlog.get_logger()


async def upload_document(
    session: AsyncSession, conversation_id: str, file: UploadFile
) -> Document:
    """Upload and process a PDF document for a conversation.

    Validates the file is a PDF, saves it to disk, extracts text using PyMuPDF,
    and stores metadata + page-level chunks in the database.
    Multiple documents per conversation are supported.
    """
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        filename = file.filename or ""
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported.")

    content = await file.read()

    if len(content) > settings.max_upload_size:
        raise ValueError(
            f"File too large. Maximum size is {settings.max_upload_size // (1024 * 1024)}MB."
        )

    original_filename = file.filename or "document.pdf"
    unique_name = f"{uuid.uuid4().hex}_{original_filename}"
    file_path = os.path.join(settings.upload_dir, unique_name)

    os.makedirs(settings.upload_dir, exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info("Saved uploaded PDF", filename=original_filename, path=file_path, size=len(content))

    extracted_text = ""
    page_count = 0
    page_records: list[DocumentPage] = []

    try:
        doc = fitz.open(file_path)
        page_count = len(doc)
        pages_text: list[str] = []
        for page_num in range(page_count):
            page = doc[page_num]
            text = page.get_text()  # type: ignore[union-attr]
            if text.strip():
                pages_text.append(f"--- Page {page_num + 1} ---\n{text}")
                page_records.append(
                    DocumentPage(
                        page_number=page_num + 1,
                        content=text,
                        word_count=len(text.split()),
                    )
                )
        extracted_text = "\n\n".join(pages_text)
        doc.close()
    except Exception:
        logger.exception("Failed to extract text from PDF", filename=original_filename)
        extracted_text = ""

    logger.info(
        "Extracted text from PDF",
        filename=original_filename,
        page_count=page_count,
        text_length=len(extracted_text),
        pages_extracted=len(page_records),
    )

    document = Document(
        conversation_id=conversation_id,
        filename=original_filename,
        file_path=file_path,
        extracted_text=extracted_text if extracted_text else None,
        page_count=page_count,
    )
    session.add(document)
    await session.flush()

    for page_record in page_records:
        page_record.document_id = document.id
    session.add_all(page_records)

    await session.commit()
    await session.refresh(document)
    return document


async def get_document(session: AsyncSession, document_id: str) -> Document | None:
    """Get a document by its ID."""
    stmt = select(Document).where(Document.id == document_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_documents_for_conversation(
    session: AsyncSession, conversation_id: str
) -> list[Document]:
    """Get all documents for a conversation, ordered by upload time."""
    stmt = (
        select(Document)
        .where(Document.conversation_id == conversation_id)
        .order_by(Document.uploaded_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_document_pages_for_conversation(
    session: AsyncSession, conversation_id: str
) -> list[DocumentPage]:
    """Get all document pages for a conversation with their parent document loaded."""
    stmt = (
        select(DocumentPage)
        .join(Document)
        .where(Document.conversation_id == conversation_id)
        .options(selectinload(DocumentPage.document))
        .order_by(Document.uploaded_at.asc(), DocumentPage.page_number.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
