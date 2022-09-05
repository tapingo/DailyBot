from enum import Enum

DAILY_MODAL = "daily"
ADD_TEAM = "/add-team-daily"
SHOW_DAILY = "/show-daily-report"
DAILY_MODAL_SUBMISSION = "daily_modal_submission"
SELECT_STATUS_ACTION = "select_status_action"
ISSUE_LINK_ACTION = "issue_link_action"
ISSUE_SUMMERY_ACTION = "issue_summery_action"
GENERAL_COMMENTS_ACTION = "general_comments_action"
SAVE_USER_CONFIGURATIONS = "save_user_configurations"
SELECT_USER_TEAM = "select_user_team"
TYPE_OR_SELECT_USER_BOARD = "type_or_select_user_board"
SELECT_USER_BOARD = "select_user_board"
TYPE_USER_BOARD = "type_user_board"
SAVE_USER_BOARD = "save_user_board"
JIRA_HOST_TYPE = "jira_host_type"
JIRA_SERVER_ACTION = 'jira_server_url_action'
JIRA_EMAIL_ACTION = 'jira_email_action'
JIRA_API_TOKEN_ACTION = 'jira_api_token_action'

BULK_ID_SEPERATOR = "|"
BULK_ID_FORMAT = "{key}" + BULK_ID_SEPERATOR + "{action}"

MAX_LEN_SLACK_SELECTOR = 100

class JiraHostType(Enum):
    Local = "Local"
    Cloud = "Cloud"
