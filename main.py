import click
import logging
import os
import base64
import yaml

from packaging.version import parse as parse_version

import gitlab

logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class GitlabChecker():
    def __init__(
        self,
        gitlab_config_file: str = "",
    ):
        self.gitlab_config_file = gitlab_config_file

        self.gitlab_api_client: gitlab.Gitlab = gitlab.Gitlab.from_config(
            config_files=[os.path.expanduser(self.gitlab_config_file)]
        )
        self.gitlab_api_client.auth()

        logger.info(
            f"User {self.gitlab_api_client.user.username} with email {self.gitlab_api_client.user.email} connected to {self.gitlab_api_client.url}"
        )
    def check_gitlab_ci_common_version_by_project_id(self, project_id, gitlab_common_ci_version_check):
        try:
            project = self.gitlab_api_client.projects.get(project_id)
        except Exception as e:
            logger.debug(f"[P:{str(project_id)}] {e}")
            return False

        try:
            items = project.repository_tree(path='.', ref='master')
        except Exception as master_e:
            try:
                items = project.repository_tree(path='.', ref='main')
            except Exception as main_e:
                logger.debug(f"[P:{str(project_id)}] {main_e}")
                return False

        gitlab_ci_common_ref = ""
        gitlab_ci_item = None
        for item in items:
            if item['name'] == '.gitlab-ci.yml':
                gitlab_ci_item = item

        if gitlab_ci_item:
            file_info = project.repository_blob(gitlab_ci_item['id'])
            if file_info['encoding'] == 'base64':
                content = base64.b64decode(file_info['content'])
                gitlab_ci_yaml = yaml.load(content, yaml.BaseLoader)
                if gitlab_ci_yaml and 'include' in gitlab_ci_yaml:
                    for include_dict in gitlab_ci_yaml['include']:
                        if 'project' in include_dict:
                            gitlab_ci_common_ref = include_dict['ref']

        if gitlab_ci_common_ref != "":
            if gitlab_common_ci_version_check != "":
                if (parse_version(gitlab_ci_common_ref) >= parse_version(gitlab_common_ci_version_check)
                    or gitlab_ci_common_ref == "master" or gitlab_ci_common_ref == "main"
                    ):
                    logger.info(f"[{project.web_url}](#{project.id}) Matched {gitlab_ci_common_ref} >= {gitlab_common_ci_version_check}")
            else:
                logger.info(f"[{project.web_url}](#{project.id}) has gitlab-ci-common version {gitlab_ci_common_ref}")
        elif gitlab_common_ci_version_check == "":
            logger.info(f"[{project.web_url}](#{project.id}) doesnt have any gitlab-ci-common reference")

    def check_gitlab_ci_common_version_by_group_id(self, group_id, gitlab_common_ci_version_check):
        try:
            group = self.gitlab_api_client.groups.get(group_id)
        except Exception as e:
            logger.debug(f"[G:{str(group_id)}] {e}")
            return False

        try:
            all_projects: list = group.projects.list(all=True, include_subgroups=True)
        except Exception as e:
            self.errors.append(f"[G:{str(group_id)}] {e}")
            return False

        for project in all_projects:
            self.check_gitlab_ci_common_version_by_project_id(project.id, gitlab_common_ci_version_check)

@click.command()
@click.option(
    "--gitlab-config-file",
    help="Path to the python-gitlab configuration file.",
    type=str,
    default="~/.python-gitlab.cfg",
)
@click.option("--group-id", help="Gitlab group ID", type=int, required=False, default=-1)
@click.option("--project-id", help="Gitlab project ID", type=int, required=False, default=-1)
@click.option("--common-ci-version", help="Gitlab ci common version to find", type=str, required=False, default="")
def run(gitlab_config_file: str, group_id: int, project_id: int, common_ci_version: str):
    gitlabChecker = GitlabChecker(gitlab_config_file)

    if group_id > -1:
        gitlabChecker.check_gitlab_ci_common_version_by_group_id(group_id, common_ci_version)
    elif project_id > -1:
        gitlabChecker.check_gitlab_ci_common_version_by_project_id(project_id, common_ci_version)
    else:
        logger.info("Nothing done")


if __name__ == "__main__":
    run()
