from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(String(50), primary_key=True, index=True)  # e.g. "concerts", "parties", "sports"
    name = Column(String(100), nullable=False)              # e.g. "Концерты"
    slug = Column(String(100), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    events = relationship("Event", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Category(id='{self.id}', name='{self.name}', slug='{self.slug}')>"
