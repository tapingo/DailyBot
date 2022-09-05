import os
from typing import Tuple, List, Optional, Dict

from slack_bolt import App

from dailybot.block_utils import generate_daily_modal, generate_home_tab_view, generate_user_from_config_action, \
    generate_home_tab_view_set_jira_keys, generate_home_tab_view_user_configured, generate_user_not_exists_modal, \
    generate_daily_message
from dailybot.constants import DAILY_MODAL_SUBMISSION, SELECT_STATUS_ACTION, ISSUE_LINK_ACTION, ISSUE_SUMMERY_ACTION, \
    GENERAL_COMMENTS_ACTION, BULK_ID_SEPERATOR, SAVE_USER_CONFIGURATIONS, SELECT_USER_BOARD, SELECT_USER_TEAM, \
    DAILY_MODAL, SHOW_DAILY, ADD_TEAM, SAVE_USER_BOARD, TYPE_OR_SELECT_USER_BOARD, TYPE_USER_BOARD
from dailybot.jira_utils import get_my_issues, update_daily_report_status_and_enrich_status, get_optional_statuses
from dailybot.mongodb import Team, User, Daily, DailyIssueReport, DailyReport

app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)


@app.shortcut(DAILY_MODAL)
def daily_report(ack, body, client):
    user_id = body['user']['id']
    user = User.get_from_db(user_id)
    daily = Daily.get_from_db(user.team)

    client.views_open(
        trigger_id=body["trigger_id"],
        view=(generate_daily_modal(user=user, issues=get_my_issues(user), daily=daily)
              if user else generate_user_not_exists_modal())
    )
    ack()


@app.action(SELECT_STATUS_ACTION)
def select_status_action(ack, body):
    status = body['actions'][0]['selected_option']['value']
    issue_key, _ = body['actions'][0]['block_id'].split(BULK_ID_SEPERATOR)
    user_id = body['user']['id']
    ack()
    user = User.get_from_db(user_id)
    optional_statuses = get_optional_statuses(
        user=user,
        issue_key=issue_key
    )
    if status not in optional_statuses:
        # TODO: add error to view somehow
        return


@app.action(ISSUE_LINK_ACTION)
def issue_link_action(ack):
    ack()


@app.action(ISSUE_SUMMERY_ACTION)
def issue_summery_action(ack):
    ack()


@app.action(GENERAL_COMMENTS_ACTION)
def general_comments_action(ack, body, logger):
    pass


def get_details_from_view(view: dict) -> Tuple[List[DailyIssueReport], Optional[str]]:
    general_comments = None
    issues: Dict[str, DailyIssueReport] = {}
    for key, value in view['state']['values'].items():
        if key == GENERAL_COMMENTS_ACTION:
            general_comments = value[key]['value']
        else:
            issue_key, action = key.split(BULK_ID_SEPERATOR)
            issue_report = issues.get(issue_key, DailyIssueReport(key=issue_key))
            if action == ISSUE_SUMMERY_ACTION:
                issue_report.details = value[action]['value']
            if action == SELECT_STATUS_ACTION:
                issue_report.status = value[action]['selected_option']['value']
            issues[issue_key] = issue_report

    return list(issues.values()), general_comments


@app.view(DAILY_MODAL_SUBMISSION)
def handle_daily_submission(ack, body, view, logger):
    user = User.get_from_db(body['user']['id'])
    issue_reports, general_comments = get_details_from_view(view)
    daily = Daily.get_from_db(user.team)
    daily.reports[user.slack_data.user_id] = DailyReport(
        issue_reports=issue_reports,
        general_comments=general_comments
    )
    ack()

    # Update Jira:
    update_daily_report_status_and_enrich_status(user=user, daily=daily, logger=logger)
    daily.save_in_db()


@app.event("app_home_opened")
def update_home_tab(client, event, logger):
    user_id = event['user']
    user = User.get_from_db(user_id)

    if not user:
        try:
            # views.publish is the method that your app uses to push a view to the Home tab
            client.views_publish(
                user_id=event["user"],
                view=generate_home_tab_view(teams=Team.get_all_teams_from_db())
            )

        except Exception as e:
            logger.error(f"Error publishing home tab: {e}")
        return

    if not user.jira_keys:
        app.client.views_publish(
            user_id=user.slack_data.user_id,
            view=generate_home_tab_view_set_jira_keys(user)
        )
        return

    app.client.views_publish(
        user_id=user.slack_data.user_id,
        view=generate_home_tab_view_user_configured()
    )


@app.action(SAVE_USER_CONFIGURATIONS)
def save_user_config_action(ack, body, client):
    user = generate_user_from_config_action(body).save_in_db()
    client.views_publish(
        user_id=user.slack_data.user_id,
        view=generate_home_tab_view_set_jira_keys(user)
    )
    ack()

@app.action(SELECT_USER_BOARD)
def select_user_board_action(ack, body):
    user = User.get_from_db(body['user']['id'])
    jira_keys = [
        option['value']
        for option in body['view']['state']['values'][TYPE_OR_SELECT_USER_BOARD][SELECT_USER_BOARD]['selected_options']
    ]
    user.update_jira_keys(jira_keys)

    app.client.views_publish(
        user_id=user.slack_data.user_id,
        view=generate_home_tab_view_user_configured()
    )

    ack()


@app.action(SAVE_USER_BOARD)
def select_user_board_action(ack, body):
    user = User.get_from_db(body['user']['id'])
    jira_keys = body['view']['state']['values'][TYPE_OR_SELECT_USER_BOARD][TYPE_USER_BOARD]['value'].split(',')
    user.update_jira_keys(jira_keys)

    app.client.views_publish(
        user_id=user.slack_data.user_id,
        view=generate_home_tab_view_user_configured()
    )

    ack()


@app.action(SELECT_USER_TEAM)
def select_user_team_action(ack, body, logger):
    logger.info(body)
    ack()


@app.command(SHOW_DAILY)
def show_daily(ack, command, client):
    with_gui = 'gui' in command.get('text', '')
    user = User.get_from_db(command['user_id'])
    daily = Daily.get_from_db(user.team)
    blocks = generate_daily_message(user, daily, with_gui=with_gui)
    client.chat_postMessage(
        channel=command['channel_id'],
        text="Daily Report",
        blocks=blocks
    )
    ack()


@app.command(ADD_TEAM)
def add_team(ack, respond, command):
    ack()
    name, daily_channel = command['text'].split()
    Team(name, daily_channel).save_in_db()
    respond(f"Added team {name} with daily channel {daily_channel}")


def run():
    app.start(port=int(os.environ.get("PORT", 3000)))


if __name__ == '__main__':
    run()
