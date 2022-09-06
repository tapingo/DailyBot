from functools import lru_cache
from typing import List

from jira import JIRA, Issue, Project, JIRAError

from dailybot.constants import JiraHostType
from dailybot.mongodb import User, Daily


@lru_cache
def get_jira(jira_server_url: str, jira_email: str, jira_api_token: str, jira_host_type: str) -> JIRA:
    if jira_host_type == JiraHostType.Local.name:
        return JIRA(jira_server_url, token_auth=jira_api_token)
    if jira_host_type == JiraHostType.Cloud.name:
        return JIRA(jira_server_url, basic_auth=(jira_email, jira_api_token))
    raise Exception  # todo: handle


def get_jira_projects(user: User) -> List[Project]:
    try:
        jira_client = get_jira(
            jira_server_url=user.jira_server_url,
            jira_email=user.jira_email,
            jira_api_token=user.jira_api_token,
            jira_host_type=user.jira_host_type
        )
        return jira_client.projects()
    except JIRAError:
        return []


@lru_cache
def get_optional_transitions(jira_server_url: str, jira_email: str, jira_api_token: str, jira_host_type: str,
                             issue_key: str):
    jira_client = get_jira(
        jira_server_url=jira_server_url,
        jira_email=jira_email,
        jira_api_token=jira_api_token,
        jira_host_type=jira_host_type
    )
    return jira_client.transitions(issue_key)


def get_optional_statuses(user: User, issue_key: str):
    transitions = get_optional_transitions(
        jira_server_url=user.jira_server_url,
        jira_email=user.jira_email,
        jira_api_token=user.jira_api_token,
        jira_host_type=user.jira_host_type,
        issue_key=issue_key
    )
    return list(set(transition['to']['name'] for transition in transitions if transition.get('isAvailable', True)))


def get_my_issues(user: User) -> List[Issue]:
    issues: List[Issue] = []
    i = 0
    chunk_size = 100
    jira_client = get_jira(
        jira_server_url=user.jira_server_url,
        jira_email=user.jira_email,
        jira_api_token=user.jira_api_token,
        jira_host_type=user.jira_host_type
    )
    # TODO: SUOER IMPORTANT : think about how to understand what status to filter, not all the same in each board!
    while user.jira_keys:  # if user has no jira keys don't enter
        chunk = jira_client.search_issues(
            f'assignee = currentUser() and project in ({", ".join(user.jira_keys)}) and status not in (DONE, "TO DO", Closed)',
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
        jira_api_token=user.jira_api_token,
        jira_host_type=user.jira_host_type
    )
    return jira_client.issue(issue_key)


def get_transition_name(user: User, issue_key: str, to_status: str):
    optional_transitions = get_optional_transitions(
        jira_server_url=user.jira_server_url,
        jira_email=user.jira_email,
        jira_api_token=user.jira_api_token,
        jira_host_type=user.jira_host_type,
        issue_key=issue_key
    )
    for transition in optional_transitions:
        if transition['to']['name'] == to_status:
            return transition['name']


def update_daily_report_status_and_enrich_status(user: User, daily: Daily, logger):
    jira_client = get_jira(
        jira_server_url=user.jira_server_url,
        jira_email=user.jira_email,
        jira_api_token=user.jira_api_token,
        jira_host_type=user.jira_host_type
    )
    daily_report = daily.reports[user.slack_data.user_id]
    for issue in daily_report.issue_reports:
        jira_issue = jira_client.issue(issue.key)
        issue.link = jira_issue.permalink()
        issue.summary = jira_issue.get_field('summary')
        transition = get_transition_name(user, issue_key=issue.key, to_status=issue.status)
        if transition:
            try:
                jira_client.transition_issue(issue.key, transition=transition)
            except JIRAError:
                # should handle unsuccessful update and remove update from daily
                logger.info(f"could not move issue {issue.key} to `{issue.status}` status")
