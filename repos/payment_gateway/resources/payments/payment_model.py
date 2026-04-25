import uuid

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column


from db.models.model_base import Base

class Payment(Base):
    __tablename__ = "payments"
    payment_id = Column(
        UUID(as_uuid=True), nullable=False, primary_key=True, default=uuid.uuid4
    )