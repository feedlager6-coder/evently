from sqlalchemy import Column, String, Boolean, Float
from sqlalchemy.orm import relationship
from app.database import Base


class City(Base):
    __tablename__ = "cities"

    id = Column(String(50), primary_key=True, index=True)  # e.g. "makhachkala", "moscow"
    name = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    timezone = Column(String(100), nullable=False)  # e.g. "Europe/Moscow"
    currency = Column(String(10), nullable=False)   # e.g. "RUB"
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    events = relationship("Event", back_populates="city", cascade="all, delete-orphan")
    users = relationship("User", back_populates="default_city")

    def __repr__(self) -> str:
        return f"<City(id='{self.id}', name='{self.name}', country='{self.country}')>"
