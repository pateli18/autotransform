from sqlalchemy import VARCHAR, Column, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from autotransform.db.base import Base
from autotransform.db.mixins import TimestampMixin


class ConfigModel(Base, TimestampMixin):
    __tablename__ = "config"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    name = Column(VARCHAR, nullable=False)
    code = Column(VARCHAR, nullable=True)
    previous_records = Column(JSONB, nullable=True)
    current_records = Column(JSONB, nullable=True)
    output_schema = Column(JSONB, nullable=False)
    user_provided_records = Column(JSONB, nullable=True)
    bot_provided_records = Column(JSONB, nullable=True)

    process_events = relationship(
        "ProcessEventsModel",
        back_populates="config",
    )
