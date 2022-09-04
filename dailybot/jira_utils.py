import os
from functools import lru_cache
from typing import List

from jira import JIRA, Issue, Project, JIRAError

from dailybot.mongodb import User, Daily, DailyIssueReport


@lru_cache
def get_jira(jira_server_url: str, jira_email: str, jira_api_token: str) -> JIRA:
    return JIRA(jira_server_url, basic_auth=(jira_email, jira_api_token))


def get_jira_projects(user: User) -> List[Project]:
    try:
        jira_client = get_jira(
            jira_server_url=user.jira_server_url,
            jira_email=user.jira_email,
            jira_api_token=user.jira_api_token
        )
        return jira_client.projects()
    except JIRAError:
        return []


@lru_cache
def get_optional_transitions(jira_server_url: str, jira_email: str, jira_api_token: str, issue_key: str):
    jira_client = get_jira(
        jira_server_url=jira_server_url,
        jira_email=jira_email,
        jira_api_token=jira_api_token
    )
    return jira_client.transitions(issue_key)


def get_optional_statuses(user: User, issue_key: str):
    transitions = get_optional_transitions(
        jira_server_url=user.jira_server_url,
        jira_email=user.jira_email,
        jira_api_token=user.jira_api_token,
        issue_key=issue_key
    )
    return [transition['to']['name'] for transition in transitions if transition['isAvailable']]


def get_my_issues(user: User) -> List[Issue]:
    issues: List[Issue] = []
    i = 0
    chunk_size = 100
    jira_client = get_jira(
        jira_server_url=user.jira_server_url,
        jira_email=user.jira_email,
        jira_api_token=user.jira_api_token
    )
    while user.jira_keys:  # if user has no jira keys don't enter
        chunk = jira_client.search_issues(
            f'assignee = currentUser() and project in ({", ".join(user.jira_keys)}) and status not in (DONE, "TO DO")',
            startAt=i, maxResults=chunk_size)
        i += chunk_size
        issues += chunk.iterable
        if i >= chunk.total:
            break
    return issues


def get_issue(user: User, issue_key: str) -> Issue:
    jira_client = get_jira(
        jira_server_url=user.jira_server_url,
        jira_email=user.jira_email,
        jira_api_token=user.jira_api_token
    )
    return jira_client.issue(issue_key)


def get_transition_name(user: User, issue_key: str, to_status: str):
    optional_transitions = get_optional_transitions(
        jira_server_url=user.jira_server_url,
        jira_email=user.jira_email,
        jira_api_token=user.jira_api_token,
        issue_key=issue_key
    )
    for transition in optional_transitions:
        if transition['to']['name'] == to_status:
            return transition['name']


def update_daily_report_status(user: User, daily: Daily, logger):
    jira_client = get_jira(
        jira_server_url=user.jira_server_url,
        jira_email=user.jira_email,
        jira_api_token=user.jira_api_token
    )
    daily_report = daily.reports[user.slack_data.user_id]
    for issue in daily_report.issue_reports:
        transition = get_transition_name(user, issue_key=issue.key, to_status=issue.status)
        if transition:
            try:
                jira_client.transition_issue(issue.key, transition=transition)
            except JIRAError:
                logger.info(f"could not move issue {issue.key} to `{issue.status}` status")
