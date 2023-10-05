# gitlab-ci-version-checker

## Install

```
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Generate a private token for your gitlab account

Create a `~/.python-gitlab.cfg` with the following content (Replace YYYY with your private token)

```
[global]
default = gitlab
ssl_verify = true
timeout = 30
per_page = 100

[gitlab]
url = https://gitlab.com
private_token = YYYY
api_version = 4
```

## Run

```
python3 main.py --group-id 150 --common-ci-version v29.4.0
python3 main.py --group-id 5 --file-content Dockerfile > out.txt 2>&1
python3 main.py --group-id 5 --file-content .gitlab-ci.yml --file-content-grep HELM_CHART_VERSION --skip-archived-project
```
