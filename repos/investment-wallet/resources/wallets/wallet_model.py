import uuid

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column


from db.models.model_base import Base


class Wallet(Base):
    __tablename__ = "wallets"
    Wallet_id = Column(
        UUID(as_uuid=True), nullable=False, primary_key=True, default=uuid.uuid4
    )
