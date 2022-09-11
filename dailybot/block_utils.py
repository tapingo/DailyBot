from dataclasses import dataclass
from typing import List, Optional

from jira import Issue
from jira.resources import Status

from dailybot.constants import (DAILY_MODAL_SUBMISSION, ACTIONS_ISSUE_DAILY_FORM, ISSUE_LINK_ACTION,
                                ISSUE_SUMMERY_ACTION, GENERAL_COMMENTS_ACTION, BULK_ID_FORMAT, SAVE_USER_CONFIGURATIONS,
                                SELECT_USER_TEAM, SELECT_USER_BOARD, JIRA_EMAIL_ACTION, JIRA_API_TOKEN_ACTION,
                                JIRA_SERVER_ACTION, JiraHostType, JIRA_HOST_TYPE, MAX_LEN_SLACK_SELECTOR,
                                TYPE_USER_BOARD, TYPE_OR_SELECT_USER_BOARD, SAVE_USER_BOARD, IGNORE_ISSUE_IN_DAILY_FORM,
                                SELECT_STATUS_ISSUE_DAILY_FORM)
from dailybot.jira_utils import get_jira_projects, get_optional_statuses
from dailybot.mongodb import Team, User, SlackUserData, Daily, DailyIssueReport

DIVIDER = {"type": "divider"}

ISSUE_STATUSES = [
    'To Do',
    'ON HOLD',
    'In Progress',
    'IN REVIEW',
    'STAGING',
    'Done'
]


@dataclass
class SlackSelectorOption:
    text: str
    value: Optional[str] = None

    def __post_init__(self):
        self.value = self.value or self.text

    def as_dict(self):
        return {
            "text": {
                "type": "plain_text",
                "text": self.text,
                "emoji": True
            },
            "value": self.value
        }


def generate_issue_status_selector_component(status: Status, optional_statuses: List[str] = ISSUE_STATUSES) -> dict:
    initial_option = SlackSelectorOption(status.name).as_dict()
    options = [initial_option, *(SlackSelectorOption(s).as_dict() for s in optional_statuses if s != status.name)]
    return {
        "type": "static_select",
        "placeholder": {
            "type": "plain_text",
            "text": "Select current status",
            "emoji": True
        },
        "initial_option": initial_option,
        "options": options,
        "action_id": SELECT_STATUS_ISSUE_DAILY_FORM
    }


def generate_issue_report_component(user: User, issue: Issue, issue_reports: List[DailyIssueReport]):
    issue_report = None
    for report in issue_reports:
        if report.key == issue.key:
            issue_report = report
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f'{issue.key}: {issue.get_field("summary")}',
                "emoji": True
            }
        },
        {
            "type": "actions",
            "block_id": BULK_ID_FORMAT.format(key=issue.key, action=ACTIONS_ISSUE_DAILY_FORM),
            "elements": [
                {
                    "type": "checkboxes",
                    "options": [
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": "Ignore this issue"
                            },
                            "value": "ignore-issue"
                        }
                    ],
                    "action_id": IGNORE_ISSUE_IN_DAILY_FORM
                },
                generate_issue_status_selector_component(
                    status=issue.get_field('status'),
                    optional_statuses=get_optional_statuses(
                        user=user,
                        issue_key=issue.key
                    )
                ),
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Open in Jira",
                        "emoji": True
                    },
                    "value": f"link-issue-{issue.key}",
                    "url": issue.permalink(),
                    "action_id": ISSUE_LINK_ACTION
                }
            ]
        },
        {
            "type": "input",
            "block_id": BULK_ID_FORMAT.format(key=issue.key, action=ISSUE_SUMMERY_ACTION),
            "optional": True,
            "element": {
                "type": "plain_text_input",
                "action_id": ISSUE_SUMMERY_ACTION
            },
            "label": {
                "type": "plain_text",
                "text": "Progress details",
                "emoji": True
            }
        },
        *([{
            "type": "context",
            "elements": [
                {
                    "type": "plain_text",
                    "text": f"Stored data: {issue_report.details}",
                    "emoji": True
                }
            ]
        }] if issue_report and issue_report.details else []),
        DIVIDER
    ]


def generate_daily_modal(user: User, issues: List[Issue], daily: Daily):
    reports = daily.reports.get(user.slack_data.user_id)
    issue_reports = reports.issue_reports if reports else []
    issue_report_components = [
        component
        for issue in issues for component in generate_issue_report_component(user, issue, issue_reports)
    ]
    return {
        "type": "modal",
        "callback_id": DAILY_MODAL_SUBMISSION,
        "submit": {
            "type": "plain_text",
            "text": "Submit",
            "emoji": True
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel",
            "emoji": True
        },
        "title": {
            "type": "plain_text",
            "text": "Daily Report",
            "emoji": True
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Hi <@{user.slack_data.user_id}>!* Please change the statuses of the following issues "
                            f"to the updated status, and add comments of the progress of the issues. if you re-fill "
                            f"this form, copy the stored data to the input box"
                }
            },
            *issue_report_components,
            {
                "type": "input",
                "block_id": GENERAL_COMMENTS_ACTION,
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "action_id": GENERAL_COMMENTS_ACTION
                },
                "label": {
                    "type": "plain_text",
                    "text": "Other comments / blockers",
                    "emoji": True
                },
            },
            *([{
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": f"Stored data: {reports.general_comments}",
                        "emoji": True
                    }
                ]
            }] if reports and reports.general_comments else []),
        ]
    }


def generate_home_tab_view(teams: List[Team]):
    return {
        "type": "home",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Hey there! im DailyBot :smile:*"
                }
            },
            DIVIDER,
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "I was created by <@U020JKP23SR|Tugy> to bring happiness to the agile world by skipping "
                            "dailys and not wasting time each day, and just move this dailys into writing."
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Lets configure your profile :gear:"
                }
            },
            DIVIDER,
            {
                "type": "input",
                "block_id": JIRA_SERVER_ACTION,
                "element": {
                    "type": "plain_text_input",
                    "action_id": JIRA_SERVER_ACTION
                },
                "hint": {
                    "type": "plain_text",
                    "text": "https://<your-domain>.atlassian.net/ (if using cloud)  *<!> Dont forget the 'https://'*",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Jira server url",
                    "emoji": True
                }
            },
            {
                "type": "input",
                "block_id": JIRA_HOST_TYPE,
                "label": {
                    "type": "plain_text",
                    "text": "Select your Jira host type",
                    "emoji": True
                },
                "element": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select options",
                        "emoji": True
                    },
                    "initial_option": SlackSelectorOption(text=JiraHostType.Cloud.name).as_dict(),
                    "options": [
                        SlackSelectorOption(text=JiraHostType.Cloud.name).as_dict(),
                        SlackSelectorOption(text=JiraHostType.Local.name).as_dict()
                    ],
                    "action_id": JIRA_HOST_TYPE
                }
            },
            {
                "type": "input",
                "block_id": JIRA_EMAIL_ACTION,
                "element": {
                    "type": "plain_text_input",
                    "action_id": JIRA_EMAIL_ACTION
                },
                "label": {
                    "type": "plain_text",
                    "text": "Jira E-Mail",
                    "emoji": True
                }
            },
            DIVIDER,
            {
                "type": "input",
                "block_id": JIRA_API_TOKEN_ACTION,
                "element": {
                    "type": "plain_text_input",
                    "action_id": JIRA_API_TOKEN_ACTION
                },
                "label": {
                    "type": "plain_text",
                    "text": "Jira API Token",
                    "emoji": True
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "To generate Jra API Token go to "
                                "https://id.atlassian.com/manage-profile/security/api-tokens"
                    }
                ]
            },
            DIVIDER,
            {
                "type": "section",
                "block_id": SELECT_USER_TEAM,
                "text": {
                    "type": "mrkdwn",
                    "text": "*Select your team*"
                },
                "accessory": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Teams",
                        "emoji": True
                    },
                    "options": [SlackSelectorOption(text=team.name).as_dict() for team in teams],
                    "action_id": SELECT_USER_TEAM
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Save",
                            "emoji": True
                        },
                        "value": SAVE_USER_CONFIGURATIONS,
                        "action_id": SAVE_USER_CONFIGURATIONS
                    }
                ]
            }
        ]
    }


def generate_home_tab_view_set_jira_keys(user: User):
    projects = get_jira_projects(user)

    if len(projects) < MAX_LEN_SLACK_SELECTOR:
        field = [{
            "type": "section",
            "block_id": TYPE_OR_SELECT_USER_BOARD,
            "text": {
                "type": "mrkdwn",
                "text": "*Select your Jira boards from the select options*"
            },
            "accessory": {
                "type": "multi_static_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select options",
                    "emoji": True
                },
                "options": [SlackSelectorOption(text=project.key).as_dict() for project in projects],
                "action_id": SELECT_USER_BOARD
            }
        }]
    else:
        field = [
            {
                "type": "input",
                "block_id": TYPE_OR_SELECT_USER_BOARD,
                "label": {
                    "type": "plain_text",
                    "text": "Please write you issue keys:",
                    "emoji": True
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": TYPE_USER_BOARD
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "Please write the keys in a list like so: `EDGE,ULT` with , and no spaces",
                        "emoji": True
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Submit",
                            "emoji": True
                        },
                        "value": SAVE_USER_BOARD,
                        "action_id": SAVE_USER_BOARD
                    }
                ]
            }
        ]

    return {
        "type": "home",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Configurations is set",
                    "emoji": True
                }
            },
            *field
        ]
    }


def generate_home_tab_view_user_configured():
    return {
        "type": "home",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Well done! Every thing is configured!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Click the + button in the text area and write `daily`. "
                            "click `daily with Daily Bot` to fill out daily form."
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Other capabilities will come soon.."
                    }
                ]
            }
        ]
    }


def generate_user_from_config_action(body: dict) -> User:
    values = body['view']['state']['values']

    return User(
        team=values[SELECT_USER_TEAM][SELECT_USER_TEAM]['selected_option']['value'],
        jira_server_url=values[JIRA_SERVER_ACTION][JIRA_SERVER_ACTION]['value'],
        jira_api_token=values[JIRA_API_TOKEN_ACTION][JIRA_API_TOKEN_ACTION]['value'],
        jira_email=values[JIRA_EMAIL_ACTION][JIRA_EMAIL_ACTION]['value'],
        jira_host_type=values[JIRA_HOST_TYPE][JIRA_HOST_TYPE]['selected_option']['value'],
        slack_data=SlackUserData(
            team_id=body['team']['id'],
            team_domain=body['team']['domain'],
            user_id=body['user']['id'],
            user_name=body['user']['name'],
        )
    )


def generate_user_not_exists_modal():
    return {
        "type": "modal",
        "title": {
            "type": "plain_text",
            "text": "Daily Report",
            "emoji": True
        },
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Your user is not defined!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Press the `Add apps` button in the bottom left corner (bottom of the users list) "
                            "and add the `DailyBot` app, all the configurations are in the home tab. "
                            "It might not work the first time so please try again :P"
                }
            }
        ]
    }


def generate_text_section_if_not_empty(text):
    return [{
        "type": "section",
        "text": {
            "type": "plain_text",
            "text": ":speech_balloon: " + text,
            "emoji": True
        }
    }] if text else []


def generate_issue_for_daily_message(current_user: User, user_id: str, issue: DailyIssueReport):
    return [
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": f"{issue.key} - {issue.summary}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "plain_text",
                    "text": issue.status,
                    "emoji": True
                },
                {
                    "type": "mrkdwn",
                    "text": f"*<@{user_id}>*"
                }
            ],
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Open in Jira",
                    "emoji": True
                },
                "value": "click_me_123",
                "url": issue.link,
                "action_id": "button-action"
            }
        },
        *generate_text_section_if_not_empty(issue.details),
        DIVIDER
    ]


def generate_general_comments_with_gui(general_comments: str, user_id: str):
    if not general_comments:
        return []

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "General Comments",
                "emoji": True
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"<@{user_id}>"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": general_comments,
                "emoji": True
            }
        },
        DIVIDER
    ]


def generate_daily_for_user_with_gui(user: User, daily: Daily):
    return [
        [
            *([
                component
                for daily_issue in report.issue_reports
                for component in generate_issue_for_daily_message(user, user_id, daily_issue)
            ]),
            *(generate_general_comments_with_gui(report.general_comments, user_id=user_id)),
        ]
        for user_id, report in daily.reports.items()
    ]


def generate_daily_message(user: User, daily: Daily, with_gui: bool = False):
    if with_gui:
        blocks = [component for daily_report in generate_daily_for_user_with_gui(user, daily)
                  for component in daily_report]
    else:
        text = '\n'.join([
            '\n'.join([
                f"<@{user_id}>:",
                '\n'.join([
                    f" - <{issue.link}|{issue.summary}> - {issue.status}{f' - {issue.details}' if issue.details else ''}"
                    for issue in report.issue_reports
                ])
            ]) + (f"\n - {report.general_comments}" if report.general_comments else '')
            for user_id, report in daily.reports.items()])
        blocks = [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text
            }
        }] if text else []
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Daily Report for {daily.date}",
                "emoji": True
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "plain_text",
                    "text": "Feel free to extend and comment in the thread.",
                    "emoji": True
                }
            ]
        },
        *blocks,
    ]
