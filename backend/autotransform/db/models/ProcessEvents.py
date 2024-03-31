from sqlalchemy import VARCHAR, Column, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from autotransform.db.base import Base
from autotransform.db.mixins import TimestampMixin


class ProcessEventsModel(Base, TimestampMixin):
    __tablename__ = "process_events"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )

    config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("config.id"),
    )
    input_count = Column(Integer, nullable=False)
    output_count = Column(Integer, nullable=True)
    status = Column(VARCHAR, nullable=False)
    event_history = Column(JSONB, nullable=False)
    pr_uri = Column(VARCHAR, nullable=True)

    config = relationship(
        "ConfigModel",
        back_populates="process_events",
    )
