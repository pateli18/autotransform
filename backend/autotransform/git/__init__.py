import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import async_scoped_session

from autotransform.autotransform_types import (
    GitClient,
    GitConfig,
    ProcessEventMetadata,
    ProcessingConfig,
    ProcessingMessage,
)
from autotransform.db.api import (
    save_processing_config,
    update_processing_event,
)
from autotransform.utils import GitType, settings

logger = logging.getLogger(__name__)


def get_git_client(
    config_id: UUID,
    config_name: str,
    git_config: GitConfig,
    process_id: Optional[UUID],
) -> GitClient:
    if git_config is None:
        raise ValueError("Git config is required")

    if settings.git_provider == GitType.github:
        from .github import GithubGitClient

        return GithubGitClient(
            owner=git_config.owner,
            repo_name=git_config.repo_name,
            primary_branch_name=git_config.primary_branch_name,
            block_human_review=git_config.block_human_review,
            service_name=config_name,
            service_id=config_id,
            event_id=process_id,
        )
    else:
        raise ValueError(f"Unsupported git type: {settings.git_provider}")


async def refresh_config_from_git(
    config: ProcessingConfig,
    latest_event: Optional[ProcessingMessage | ProcessEventMetadata],
    db: async_scoped_session,
) -> tuple[
    ProcessingConfig, Optional[ProcessingMessage | ProcessEventMetadata]
]:
    if config.git_config is None:
        raise ValueError("Git config is required")

    if latest_event is None:
        process_id = None
    else:
        process_id = latest_event.id

    git_client = get_git_client(
        config.config_id, config.name, config.git_config, process_id
    )

    # check if PR status has changed
    if latest_event is not None and latest_event.status == "awaiting_review":
        status = git_client.check_pr_status()
        if status != latest_event.status:
            latest_event.status = status
            await update_processing_event(latest_event, db)

    # get latest assets
    output_schema, code = git_client.get_latest_assets()
    update = False
    if output_schema.output_schema != config.output_schema.output_schema:
        update = True
        config.output_schema = output_schema
    if config.code is None or (
        code is not None and code.code != config.code.code
    ):
        update = True
        config.code = code

    if update:
        await save_processing_config(config.config_id, config, db)

    return config, latest_event
