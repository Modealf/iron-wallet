import uuid

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column


from db.models.model_base import Base

class Statement(Base):
    __tablename__ = "statements"
    statement_id = Column(
        UUID(as_uuid=True), nullable=False, primary_key=True, default=uuid.uuid4
    )