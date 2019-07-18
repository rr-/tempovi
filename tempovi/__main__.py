#!/usr/bin/env python3
import datetime
import itertools
import os
import sys
import tempfile
import typing as T
from dataclasses import dataclass
from pathlib import Path
from subprocess import run

import configargparse
import dateutil.parser
import pytimeparse
import requests

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
EDITOR = os.environ.get("EDITOR", "vim")


def get_default_range() -> T.Tuple[datetime.datetime, datetime.datetime]:
    today = datetime.datetime.today()
    return (today, today)
    # import calendar
    # _, days_in_month = calendar.monthrange(today.year, today.month)
    # start = datetime.datetime(today.year, today.month, 1)
    # end = datetime.datetime(today.year, today.month, days_in_month)
    # return (start, end)


def parse_args() -> configargparse.Namespace:
    parser = configargparse.ArgumentParser(
        prog="tempovi", default_config_files=[CONFIG_DIR / "tempovi.ini"]
    )

    parser.add_argument(
        "--tempo-account-id", required=True, help="Tempo API account ID"
    )
    parser.add_argument(
        "--tempo-token", required=True, help="Tempo API authentication token"
    )

    start, end = get_default_range()
    parser.add_argument(
        "--start", type=dateutil.parser.parse, default=start, help="Start date"
    )
    parser.add_argument(
        "--end", type=dateutil.parser.parse, default=end, help="End date"
    )

    parser.add_argument("output", type=Path, help="Output path", nargs="?")

    return parser.parse_args()


@dataclass
class Worklog:
    id: T.Optional[int]
    date: datetime.datetime
    duration: datetime.timedelta
    issue: str
    description: str


@dataclass
class WorklogDiff:
    added: T.List[Worklog]
    changed: T.List[Worklog]
    deleted: T.List[Worklog]


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


def dump_worklogs(worklogs: T.Iterable[Worklog], file: T.IO[str]) -> None:
    columns = ["id", "date", "duration", "issue", "description"]
    column_widths = [
        max(len(str(getattr(worklog, column))) for worklog in worklogs)
        for column in columns
    ]

    for date, group in itertools.groupby(
        worklogs, key=lambda worklog: worklog.date
    ):
        group = list(group)
        total_time = datetime.timedelta(
            seconds=sum(worklog.duration.total_seconds() for worklog in group)
        )
        max_time = datetime.timedelta(hours=8)

        print(f"# {date} - {total_time} of {max_time}", file=file)
        for worklog in group:
            for column, column_width in zip(columns, column_widths):
                is_last = column == columns[-1]
                item = str(getattr(worklog, column))
                if is_last:
                    print(item, file=file)
                else:
                    print(item.ljust(column_width), end=" | ", file=file)


def read_worklogs(file: T.IO[str]) -> T.Iterable[Worklog]:
    for line in file:
        if line.startswith("#"):
            continue
        row = [word.strip() for word in line.split("|")]
        yield Worklog(
            id=int(row[0]) if row[0] else None,
            date=dateutil.parser.parse(row[1]).date(),
            duration=datetime.timedelta(seconds=pytimeparse.parse(row[2])),
            issue=row[3],
            description=row[4],
        )


def compute_diff(
    source_worklogs: T.List[Worklog], target_worklogs: T.List[Worklog]
) -> WorklogDiff:
    diff = WorklogDiff(changed=[], added=[], deleted=[])
    source_worklog_map = {worklog.id: worklog for worklog in source_worklogs}
    target_worklog_map = {worklog.id: worklog for worklog in target_worklogs}

    for source_worklog in source_worklogs:
        target_worklog = target_worklog_map.get(source_worklog.id)
        if target_worklog is None:
            diff.deleted.append(source_worklog)
        elif target_worklog != source_worklog:
            diff.changed.append(target_worklog)

    for target_worklog in target_worklogs:
        source_worklog = source_worklog_map.get(target_worklog.id)
        if source_worklog is None:
            diff.added.append(target_worklog)

    return diff


def main() -> None:
    args = parse_args()

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "report.txt"

        worklogs = list(
            get_worklogs(
                args.tempo_token,
                args.tempo_account_id,
                args.start.date(),
                args.end.date(),
            )
        )

        with path.open("w") as handle:
            dump_worklogs(worklogs, file=handle)

        result = run([EDITOR, path])
        if result.returncode != 0:
            print("Editor exited with non-zero status, bailing out")
            exit(1)

        with path.open("r") as handle:
            try:
                new_worklogs = list(read_worklogs(file=handle))
            except ValueError as ex:
                print(f"Invalid syntax ({ex}), bailing out")
                exit(1)

        diff = compute_diff(
            source_worklogs=worklogs, target_worklogs=new_worklogs
        )

        for worklog in diff.added:
            create_worklog(args.tempo_token, args.tempo_account_id, worklog)
        for worklog in diff.changed:
            update_worklog(args.tempo_token, args.tempo_account_id, worklog)
        for worklog in diff.deleted:
            delete_worklog(args.tempo_token, args.tempo_account_id, worklog.id)


if __name__ == "__main__":
    main()
