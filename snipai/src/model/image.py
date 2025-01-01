import datetime
from typing import List, Optional
from uuid import uuid4

from sqlmodel import Field, Relationship, SQLModel


class ImageTag(SQLModel, table=True):
    image_id: str = Field(foreign_key="image.id", primary_key=True)
    tag_id: str = Field(foreign_key="tag.id", primary_key=True)


class Tag(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str
    is_generated: bool
    images: List["Image"] | None = Relationship(
        back_populates="tags", link_model=ImageTag
    )


class Image(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    filename: str  # e.g., "2024-11-20-123456.png"
    filepath: str  # Relative path from data dir
    timestamp: datetime.datetime
    description: Optional[str] = None  # LLM-generated description
    tags: List[Tag] | None = Relationship(back_populates="images", link_model=ImageTag)
    width: int
    height: int
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    # Needed for Column(JSON)
    class Config:
        arbitrary_types_allowed = True
