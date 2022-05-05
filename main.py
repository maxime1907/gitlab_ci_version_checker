from typing import Any
import click
import logging
import os
import base64
import yaml

from packaging.version import parse as parse_version

import gitlab

logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(name)-12s %(levelname)-8s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class GitlabChecker:
    def __init__(
        self,
        gitlab_config_file: str = "",
    ):
        self.gitlab_config_file = gitlab_config_file

        self.gitlab_api_client: gitlab.Gitlab = gitlab.Gitlab.from_config(
            config_files=[os.path.expanduser(self.gitlab_config_file)]
        )
        self.gitlab_api_client.auth()

        if self.gitlab_api_client.user:
            logger.info(
                f"User {self.gitlab_api_client.user.username} with "
                f"email {self.gitlab_api_client.user.email} connected"
                f" to {self.gitlab_api_client.url}"
            )

    def get_gitlab_item(self, project, filename) -> dict[str, Any] | None:
        try:
            items = project.repository_tree(path=".", ref="master")
        except Exception as master_e:
            try:
                items = project.repository_tree(path=".", ref="main")
            except Exception as main_e:
                logger.debug(f"[P:{str(project.id)}] {main_e}")
                logger.debug(f"[P:{str(project.id)}] {master_e}")

        for item in items:
            if item["name"] == filename:
                return item

        return None

    def get_gitlab_file_content(self, project, gitlab_item) -> bytes | None:
        try:
            file_info = project.repository_blob(gitlab_item["id"])
            if file_info["encoding"] == "base64":
                return base64.b64decode(file_info["content"])
        except Exception as e:
            logger.debug(e)

        return None

    def check_gitlab_ci_common_version_by_project_id(
        self, project_id, gitlab_common_ci_version_check
    ):
        project = self.gitlab_api_client.projects.get(project_id)
        gitlab_ci_item = self.get_gitlab_item(
            project=project, filename=".gitlab-ci.yml"
        )

        gitlab_ci_common_ref = ""
        if gitlab_ci_item:
            content = self.get_gitlab_file_content(
                project=project, gitlab_item=gitlab_ci_item
            )
            if content is not None:
                gitlab_ci_yaml = yaml.load(content, yaml.BaseLoader)
                if gitlab_ci_yaml and "include" in gitlab_ci_yaml:
                    for include_dict in gitlab_ci_yaml["include"]:
                        if "project" in include_dict:
                            gitlab_ci_common_ref = include_dict["ref"]

        if gitlab_ci_common_ref != "":
            if gitlab_common_ci_version_check != "":
                if (
                    parse_version(gitlab_ci_common_ref)
                    >= parse_version(gitlab_common_ci_version_check)
                    or gitlab_ci_common_ref == "master"
                    or gitlab_ci_common_ref == "main"
                ):
                    logger.info(
                        f"[{project.web_url}](#{project.id}) Matched {gitlab_ci_common_ref} >= {gitlab_common_ci_version_check}"
                    )
            else:
                logger.info(
                    f"[{project.web_url}](#{project.id}) has gitlab-ci-common version {gitlab_ci_common_ref}"
                )
        elif gitlab_common_ci_version_check == "":
            logger.info(
                f"[{project.web_url}](#{project.id}) doesnt have any gitlab-ci-common reference"
            )

    def get_gitlab_projects_by_group_id(self, group_id) -> list:
        try:
            group = self.gitlab_api_client.groups.get(group_id)
        except Exception as e:
            logger.debug(f"[G:{str(group_id)}] {e}")
            return []

        try:
            return group.projects.list(all=True, include_subgroups=True)
        except Exception as e:
            logger.debug(f"[G:{str(group_id)}] {e}")

        return []

    def print_gitlab_file_content(self, project_id, filename) -> None:
        project = self.gitlab_api_client.projects.get(project_id)
        gitlab_item = self.get_gitlab_item(project=project, filename=filename)
        content = self.get_gitlab_file_content(project=project, gitlab_item=gitlab_item)
        if content:
            content_decoded = content.decode("utf-8")
            logger.info(f"[{project.path_with_namespace}] {filename} --- START")
            logger.info(f"\n{content_decoded}")
            logger.info(f"[{project.path_with_namespace}] {filename} --- END")


@click.command()
@click.option(
    "--gitlab-config-file",
    help="Path to the python-gitlab configuration file.",
    type=str,
    default="~/.python-gitlab.cfg",
)
@click.option(
    "--group-id", help="Gitlab group ID", type=int, required=False, default=-1
)
@click.option(
    "--project-id", help="Gitlab project ID", type=int, required=False, default=-1
)
@click.option(
    "--common-ci-version",
    help="Gitlab ci common version to find",
    type=str,
    required=False,
    default=None,
)
@click.option(
    "--file-content",
    help="Gitlab file name to print content",
    type=str,
    required=False,
    default=None,
)
def run(
    gitlab_config_file: str,
    group_id: int,
    project_id: int,
    common_ci_version: str | None,
    file_content: str | None,
):
    gitlabChecker = GitlabChecker(gitlab_config_file)

    if group_id > -1:
        all_projects = gitlabChecker.get_gitlab_projects_by_group_id(group_id=group_id)
        for project in all_projects:
            project_id = project.id
            if common_ci_version is not None:
                gitlabChecker.check_gitlab_ci_common_version_by_project_id(
                    project_id=project_id,
                    gitlab_common_ci_version_check=common_ci_version,
                )
            if file_content is not None:
                gitlabChecker.print_gitlab_file_content(
                    project_id=project_id, filename=file_content
                )
    elif project_id > -1:
        if common_ci_version is not None:
            gitlabChecker.check_gitlab_ci_common_version_by_project_id(
                project_id, common_ci_version
            )
        if file_content is not None:
            gitlabChecker.print_gitlab_file_content(
                project_id=project_id, filename=file_content
            )
    else:
        logger.info("Nothing done")


if __name__ == "__main__":
    run()
