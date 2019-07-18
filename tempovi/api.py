import datetime
import typing as T
from dataclasses import dataclass

import dateutil.parser
import requests


@dataclass
class Worklog:
    id: T.Optional[int]
    date: datetime.datetime
    duration: datetime.timedelta
    issue: str
    description: str


def get_worklogs(
    tempo_token: str,
    tempo_account_id: str,
    start: datetime.date,
    end: datetime.date,
) -> T.Iterable[Worklog]:
    url = (
        f"https://api.tempo.io/core/3/worklogs/user/{tempo_account_id}"
        f"?from={start}&to={end}"
    )

    while True:
        response = requests.get(
            url, headers={"Authorization": f"Bearer {tempo_token}"}
        )
        response.raise_for_status()
        data = response.json()

        for entry in data["results"]:
            yield Worklog(
                id=entry["tempoWorklogId"],
                issue=entry["issue"]["key"],
                date=dateutil.parser.parse(entry["startDate"]).date(),
                duration=datetime.timedelta(seconds=entry["timeSpentSeconds"]),
                description=entry["description"],
            )

        if "next" not in data["metadata"]:
            break
        url = data["metadata"]["next"]


def create_worklog(
    tempo_token: str, tempo_account_id: str, worklog: Worklog
) -> None:
    data = {
        "authorAccountId": tempo_account_id,
        "billableSeconds": None,
        "description": worklog.description,
        "issueKey": worklog.issue,
        "remainingEstimateSeconds": None,
        "startDate": str(worklog.date),
        "startTime": "00:00:00",
        "timeSpentSeconds": worklog.duration.total_seconds(),
    }

    response = requests.post(
        "https://api.tempo.io/core/3/worklogs",
        json=data,
        headers={"Authorization": f"Bearer {tempo_token}"},
    )
    response.raise_for_status()


def update_worklog(
    tempo_token: str, tempo_account_id: str, worklog: Worklog
) -> None:
    data = {
        "authorAccountId": tempo_account_id,
        "billableSeconds": None,
        "description": worklog.description,
        "issueKey": worklog.issue,
        "remainingEstimateSeconds": None,
        "startDate": str(worklog.date),
        "startTime": "00:00:00",
        "timeSpentSeconds": worklog.duration.total_seconds(),
    }

    response = requests.put(
        f"https://api.tempo.io/core/3/worklogs/{worklog.id}",
        json=data,
        headers={"Authorization": f"Bearer {tempo_token}"},
    )
    response.raise_for_status()


def delete_worklog(
    tempo_token: str, tempo_account_id: str, worklog_id: int
) -> None:
    response = requests.delete(
        f"https://api.tempo.io/core/3/worklogs/{worklog_id}",
        headers={"Authorization": f"Bearer {tempo_token}"},
    )
    response.raise_for_status()
