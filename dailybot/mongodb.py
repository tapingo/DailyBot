import os
from datetime import date

from dacite import from_dict
from dataclasses import dataclass, asdict, field
from functools import lru_cache
from typing import List, Optional, Dict

from pymongo import MongoClient

from dailybot.constants import JiraHostType

MONGODB_USERNAME = "MONGODB_USERNAME"
MONGODB_PASSWORD = "MONGODB_PASSWORD"
CLUSTER_NAME = "CLUSTER_NAME"
MONGODB_DATABASE = "MONGODB_DATABASE"


DAILY_DB = 'daily'
REPORTS_DB = 'reports'
USERS_COLLECTION_NAME = 'users'
TEAMS_COLLECTION_NAME = 'teams'
DAILIES_COLLECTION_NAME = 'dailys'


@dataclass
class DailyIssueReport:
    key: str
    status: Optional[str] = field(init=False)
    details: Optional[str] = field(init=False)
    link: Optional[str] = field(init=False)
    summary: Optional[str] = field(init=False)


@dataclass
class DailyReport:
    issue_reports: List[DailyIssueReport]
    general_comments: Optional[str]


@dataclass
class Daily:
    team: str
    reports: Dict[str, DailyReport] = field(default_factory=dict)  # user_id: DailyReport
    date: Optional[str] = None
    _id: Optional[str] = None

    @staticmethod
    def _format_id(daily_date, team):
        return f"{daily_date}|{team}"

    @property
    def formatted_id(self):
        return self._format_id(self.date, self.team)

    def __post_init__(self):
        self.date = self.date or str(date.today())
        self._id = self.formatted_id

    def save_in_db(self):
        dailies_collection = get_collection(DAILIES_COLLECTION_NAME)
        dailies_collection.replace_one({"_id": self.formatted_id}, asdict(self), upsert=True)

    @classmethod
    def get_from_db(cls, team: str, daily_date: Optional[str] = None) -> "Daily":
        daily_date = daily_date or str(date.today())
        dailies_collection = get_collection(DAILIES_COLLECTION_NAME)
        daily: dict = dailies_collection.find_one({"_id": cls._format_id(daily_date, team)})
        return from_dict(cls, daily) if daily else cls(team=team, date=daily_date)


@dataclass
class Team:
    name: str
    daily_channel: str
    _id: Optional[str] = None

    def __post_init__(self):
        self._id = self.name

    def save_in_db(self):
        teams_collection = get_collection(TEAMS_COLLECTION_NAME)
        teams_collection.replace_one({"_id": self._id}, asdict(self), upsert=True)

    @classmethod
    def get_from_db(cls, team) -> "Team":
        teams_collection = get_collection(TEAMS_COLLECTION_NAME)
        team: dict = teams_collection.find_one({"_id": team})
        if team:
            return from_dict(cls, team)

    @classmethod
    def get_all_teams_from_db(cls) -> List["Team"]:
        teams_collection = get_collection(TEAMS_COLLECTION_NAME)
        return [from_dict(cls, team) for team in teams_collection.find({})]


@dataclass
class SlackUserData:
    team_id: str
    team_domain: str
    user_id: str
    user_name: str


@dataclass
class User:
    team: str
    jira_server_url: str
    jira_api_token: str
    jira_email: str
    slack_data: SlackUserData
    jira_keys: Optional[List[str]] = field(default_factory=list)
    jira_host_type: str = JiraHostType.Cloud.name
    _id: Optional[str] = None

    def __post_init__(self):
        self._id = self.slack_data.user_id

    def save_in_db(self):
        users_collection = get_collection(USERS_COLLECTION_NAME)
        users_collection.replace_one({"_id": self._id}, asdict(self), upsert=True)
        return self

    def update_jira_keys(self, jira_keys):
        users_collection = get_collection(USERS_COLLECTION_NAME)
        users_collection.update_one({"_id": self._id}, {"$set": {"jira_keys": jira_keys}})
        return self

    @classmethod
    def get_from_db(cls, user_id: str) -> Optional["User"]:
        users_collection = get_collection(USERS_COLLECTION_NAME)
        user: dict = users_collection.find_one({"_id": user_id})
        if user:
            return from_dict(cls, user)


def get_database():
    username = os.environ.get(MONGODB_USERNAME)
    password = os.environ.get(MONGODB_PASSWORD)
    cluster_name = os.environ.get(CLUSTER_NAME)

    connection_string = f"mongodb+srv://{username}:{password}@{cluster_name}.mongodb.net/?retryWrites=true&w=majority"
    return MongoClient(connection_string)


@lru_cache()
def get_daily_reports_database():
    database = get_database()
    return database[DAILY_DB]


@lru_cache
def get_collection(collection_name: str):
    return get_daily_reports_database()[collection_name]


def get_users() -> List[User]:
    users_collection = get_collection(USERS_COLLECTION_NAME)
    return [from_dict(User, user) for user in users_collection.find({})]
