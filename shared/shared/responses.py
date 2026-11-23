"""Response models."""

from pydantic import BaseModel, Field
from pydantic_ai.messages import ModelMessage


class Response(BaseModel):
    """Response model."""

    response: str
    score_id: int | None = Field(
        default=None, description="Id of the one library score the answer is about."
    )
    score_ids: list[int] | None = Field(
        default=None, description="Ids of the library scores the answer is about, if several."
    )


class FullResponse(BaseModel):
    """Full response model with history."""

    response: Response
    message_history: list[ModelMessage]


class ImslpResponse(BaseModel):
    """Response model for IMSLP agent."""

    response: str
    score_ids: list[int]


class ImslpFullResponse(BaseModel):
    """Full response model with history for IMSLP agent."""

    response: ImslpResponse
    message_history: list[ModelMessage]
