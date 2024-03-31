from sqlalchemy import VARCHAR, Boolean, Column, text
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
    previous_records = Column(JSONB, nullable=True)
    current_records = Column(JSONB, nullable=True)
    user_provided_records = Column(JSONB, nullable=True)
    bot_provided_records = Column(JSONB, nullable=True)

    # code columns
    code = Column(VARCHAR, nullable=True)
    code_commit = Column(VARCHAR, nullable=True)

    # output schema columns
    output_schema = Column(JSONB, nullable=False)
    output_schema_commit = Column(VARCHAR, nullable=True)

    # git columns
    git_owner = Column(VARCHAR, nullable=True)
    git_repo_name = Column(VARCHAR, nullable=True)
    git_primary_branch_name = Column(VARCHAR, nullable=True)
    git_block_human_review = Column(Boolean, nullable=True)

    process_events = relationship(
        "ProcessEventsModel",
        back_populates="config",
    )
