from dataclasses import dataclass
from typing import List, Optional

from jira import Issue
from jira.resources import Status

from dailybot.constants import DAILY_MODAL_SUBMISSION, SELECT_STATUS_ACTION, ISSUE_LINK_ACTION, ISSUE_SUMMERY_ACTION, \
    GENERAL_COMMENTS_ACTION, BULK_ID_FORMAT, SAVE_USER_CONFIGURATIONS, SELECT_USER_TEAM, SELECT_USER_BOARD, \
    JIRA_EMAIL_ACTION, JIRA_API_TOKEN_ACTION, JIRA_SERVER_ACTION
from dailybot.jira_utils import get_jira_projects, get_issue
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


def generate_issue_status_selector_component(status: Status) -> dict:
    initial_option = SlackSelectorOption(status.name).as_dict()
    aa = {
        "type": "static_select",
        "placeholder": {
            "type": "plain_text",
            "text": "Select current status",
            "emoji": True
        },
        "initial_option": initial_option,
        "options": [SlackSelectorOption(s).as_dict() for s in ISSUE_STATUSES],
        "action_id": SELECT_STATUS_ACTION
    }
    return aa


def generate_issue_report_component(issue: Issue):
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
            "block_id": BULK_ID_FORMAT.format(key=issue.key, action=SELECT_STATUS_ACTION),
            "elements": [
                generate_issue_status_selector_component(
                    status=issue.get_field('status')
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
        DIVIDER
    ]


def generate_daily_modal(user: User, issues: List[Issue]):
    issue_report_components = [
        component
        for issue in issues for component in generate_issue_report_component(issue)
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
                            f"to the updated status, and add comments of the progress of the issues."
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
                }
            }
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
                    "text": "https://<your-domain>.atlassian.net/",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Jira server url",
                    "emoji": True
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
            {
                "type": "section",
                "block_id": SELECT_USER_BOARD,
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
            }
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
                            "and add the `DailyBot` app, all the configurations are in the home tab.",
                    "emoji": True
                }
            }
        ]
    }


def generate_issue_for_daily_message(user: User, issue: DailyIssueReport):
    jira_issue = get_issue(user, issue.key)
    return [
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": f"{issue.key} - {jira_issue.get_field('summary')}",
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
                    "text": f"*<@{user.slack_data.user_id}>*"
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
                "url": jira_issue.permalink(),
                "action_id": "button-action"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": issue.details or "No Details",
                "emoji": True
            }
        },
        DIVIDER
    ]


def generate_daily_for_user(user: User, daily: Daily):
    return [
        [
            *([
                component
                for daily_issue in report.issue_reports
                for component in generate_issue_for_daily_message(user, daily_issue)
            ]),
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
                        "text": f"<@{user.slack_data.user_id}>"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": report.general_comments or "No Details",
                    "emoji": True
                }
            },
            DIVIDER

        ]
        for report in daily.reports.values()
    ]


def generate_daily_message(user: User, daily: Daily):
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
        *([component
           for daily_report in generate_daily_for_user(user, daily)
           for component in daily_report]),
    ]
