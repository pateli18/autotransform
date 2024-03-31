import json
import logging
from typing import Optional

from github import (
    Auth,
    Github,
    GithubException,
    PullRequest,
    Repository,
    UnknownObjectException,
)

from autotransform.autotransform_types import (
    Code,
    GitClient,
    OutputSchema,
    ProcessingStatus,
)
from autotransform.utils import settings

logger = logging.getLogger(__name__)


def _initialize_client() -> Github:
    if settings.git_provider_secret:
        github_client = Github(auth=Auth.Token(settings.git_provider_secret))
    else:
        raise ValueError(
            "Github PAT is required to be set as GIT_PROVIDER_SECRET in order to use Github"
        )
    return github_client


class GithubGitClient(GitClient[PullRequest.PullRequest]):
    client: Github = _initialize_client()

    def _get_repo(self) -> Repository.Repository:
        # check if _repo is already set
        if not hasattr(self, "_repo"):
            self._repo = self.client.get_repo(f"{self.owner}/{self.repo_name}")

        return self._repo

    def _create_branch(self, branch_name: str) -> None:
        repo = self._get_repo()

        # do nothing if branch already exists
        try:
            repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=repo.get_branch(self.primary_branch_name).commit.sha,
            )
        except GithubException as e:
            if e.data["message"] == "Reference already exists":
                logger.warning(f"Branch {branch_name} already exists")
                return
            else:
                raise e

    def _upsert_file(
        self,
        file_content: str,
        file_path: str,
        message: str,
        branch_name: str,
    ) -> str:
        repo = self._get_repo()
        try:
            contents = repo.get_contents(file_path, ref=branch_name)
            if isinstance(contents, list):
                raise ValueError(f"File {file_path} is a directory")
            response = repo.update_file(
                path=file_path,
                message=message,
                content=file_content,
                sha=contents.sha,
                branch=branch_name,
            )
        except UnknownObjectException:
            logger.info("File path: %s", file_path)
            response = repo.create_file(
                path=file_path,
                message=message,
                content=file_content,
                branch=branch_name,
            )

        return response["commit"].html_url

    def _create_pull_request(
        self, title: str, body: str, branch_name: str
    ) -> tuple[PullRequest.PullRequest, str]:
        repo = self._get_repo()
        pull_request = repo.create_pull(
            title=title,
            body=body,
            head=branch_name,
            base=self.primary_branch_name,
        )
        return pull_request, pull_request.html_url

    def _merge_pull_request(
        self, pull_request: PullRequest.PullRequest
    ) -> None:
        pull_request.merge()

    def _get_file_contents(self, file_path: str) -> tuple[str, str]:
        repo = self._get_repo()
        contents = repo.get_contents(file_path, ref=self.primary_branch_name)
        if isinstance(contents, list):
            raise ValueError(f"File {file_path} is a directory")
        return contents.decoded_content.decode(), contents.html_url

    def get_latest_assets(self) -> tuple[OutputSchema, Optional[Code]]:
        output_schema_raw, output_schema_commit = self._get_file_contents(
            self.output_schema_filepath
        )
        output_schema = OutputSchema(
            output_schema=json.loads(output_schema_raw),
            commit=output_schema_commit,
        )

        try:
            code_raw, commit = self._get_file_contents(self.code_filepath)
            code = Code(code=code_raw, commit=commit)
        except UnknownObjectException:
            code = None

        return output_schema, code

    def _check_pr_status(self, branch_name: str) -> ProcessingStatus:
        repo = self._get_repo()

        pull_requests = repo.get_pulls(
            state="all",
            head=f"{self.owner}:{branch_name}",
        )

        pr: Optional[PullRequest.PullRequest] = None
        for pull_request in pull_requests:
            if pull_request.head.ref == branch_name:
                pr = pull_request
                break

        if pr is None:
            raise ValueError(
                f"Pull request for branch {branch_name} not found"
            )

        # check if pr was merged
        processing_status = ProcessingStatus.awaiting_review
        if pr.merged:
            processing_status = ProcessingStatus.completed
        elif pr.state == "closed":
            processing_status = ProcessingStatus.failed

        return processing_status
