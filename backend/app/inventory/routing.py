"""Query parameters shared by the document list endpoints."""

from typing import Annotated

from fastapi import Query

from app.inventory.documents import DocumentStatus

StatusFilter = Annotated[
    list[DocumentStatus] | None,
    Query(description="Repeat to match several, e.g. ?status=DRAFT&status=WAITING&status=READY for pending"),
]
SearchFilter = Annotated[str | None, Query(max_length=100, description="Search reference and partner/reason")]
