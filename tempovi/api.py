import datetime
import typing as T
from dataclasses import dataclass

import dateutil.parser
import requests


@dataclass
class Worklog:
    id: T.Optional[int]
    date: datetime.date
    duration: datetime.timedelta
    issue: str
    description: str


class TempoApi:
    def __init__(self, api_key: str, user_id: str) -> None:
        self.user_id = user_id
        self.session = requests.session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def get_worklogs(
        self, start: datetime.date, end: datetime.date
    ) -> T.Iterable[Worklog]:
        url = (
            f"https://api.tempo.io/core/3/worklogs/user/{self.user_id}"
            f"?from={start}&to={end}"
        )

        while True:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()

            for entry in data["results"]:
                yield Worklog(
                    id=entry["tempoWorklogId"],
                    issue=entry["issue"]["key"],
                    date=dateutil.parser.parse(entry["startDate"]).date(),
                    duration=datetime.timedelta(
                        seconds=entry["timeSpentSeconds"]
                    ),
                    description=entry["description"],
                )

            if "next" not in data["metadata"]:
                break
            url = data["metadata"]["next"]

    def create_worklog(self, worklog: Worklog) -> None:
        data = self._serialize_worklog(worklog)
        response = self.session.post(
            "https://api.tempo.io/core/3/worklogs", json=data
        )
        response.raise_for_status()

    def update_worklog(self, worklog: Worklog) -> None:
        data = self._serialize_worklog(worklog)
        response = self.session.put(
            f"https://api.tempo.io/core/3/worklogs/{worklog.id}", json=data
        )
        response.raise_for_status()

    def delete_worklog(self, worklog_id: int) -> None:
        response = self.session.delete(
            f"https://api.tempo.io/core/3/worklogs/{worklog_id}"
        )
        response.raise_for_status()

    def _serialize_worklog(self, worklog: Worklog) -> T.Any:
        return {
            "authorAccountId": self.user_id,
            "billableSeconds": None,
            "description": worklog.description,
            "issueKey": worklog.issue,
            "remainingEstimateSeconds": None,
            "startDate": str(worklog.date),
            "startTime": "00:00:00",
            "timeSpentSeconds": worklog.duration.total_seconds(),
        }
