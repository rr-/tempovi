#!/usr/bin/env python3
import datetime
import itertools
import os
import re
import tempfile
import typing as T
from dataclasses import dataclass
from pathlib import Path
from subprocess import run

import configargparse
import dateutil.parser
import pytimeparse

from tempovi.api import TempoApi, Worklog

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
        "--user-id", required=True, help="Tempo API account ID"
    )
    parser.add_argument(
        "--api-key", required=True, help="Tempo API authentication token"
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
class WorklogDiff:
    added: T.List[Worklog]
    changed: T.List[Worklog]
    deleted: T.List[Worklog]


def dump_worklogs(worklogs: T.Iterable[Worklog], file: T.IO[str]) -> None:
    columns = ["id", "duration", "issue", "description"]
    column_widths = [
        max(len(str(getattr(worklog, column))) for worklog in worklogs)
        for column in columns
    ]

    print("# syntax:", file=file)
    print("# " + " | ".join(columns), file=file)
    print("# when adding a new item, leave the id column empty.", file=file)

    for date, group_iter in itertools.groupby(
        worklogs, key=lambda worklog: worklog.date
    ):
        group = list(group_iter)
        total_time = datetime.timedelta(
            seconds=sum(worklog.duration.total_seconds() for worklog in group)
        )

        print(file=file)
        print(f"# {date} - total time: {total_time}", file=file)

        for worklog in group:
            for column, column_width in zip(columns, column_widths):
                is_last = column == columns[-1]
                item = str(getattr(worklog, column))
                if is_last:
                    print(item, file=file)
                else:
                    print(item.ljust(column_width), end=" | ", file=file)


def read_worklogs(file: T.IO[str]) -> T.Iterable[Worklog]:
    last_date: T.Optional[datetime.date] = None
    for line in file:
        if not line.strip():
            continue

        match = re.search(r"#.*(\d{4}-\d{2}-\d{2})", line)
        if match:
            last_date = dateutil.parser.parse(match.group(1)).date()
            continue
        elif line.startswith("#"):
            last_date = None
            continue

        row = [word.strip() for word in line.split("|")]
        if not last_date:
            raise ValueError("unknown date")
        yield Worklog(
            id=int(row[0]) if row[0] else None,
            date=last_date,
            duration=datetime.timedelta(seconds=pytimeparse.parse(row[1])),
            issue=row[2],
            description=row[3],
        )


def compute_diff(
    source_worklogs: T.List[Worklog], target_worklogs: T.List[Worklog]
) -> WorklogDiff:
    diff = WorklogDiff(changed=[], added=[], deleted=[])
    source_worklog: T.Optional[Worklog]
    target_worklog: T.Optional[Worklog]
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
    api = TempoApi(args.api_key, args.user_id)

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "report.txt"

        worklogs = list(api.get_worklogs(args.start.date(), args.end.date()))

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
            api.create_worklog(worklog)
        for worklog in diff.changed:
            api.update_worklog(worklog)
        for worklog in diff.deleted:
            assert worklog.id
            api.delete_worklog(worklog.id)


if __name__ == "__main__":
    main()
