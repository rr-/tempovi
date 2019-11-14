#!/usr/bin/env python3
import calendar
import datetime
import itertools
import os
import re
import sys
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


def get_date_range(
    args: configargparse.Namespace
) -> T.Tuple[datetime.date, datetime.date]:
    today = datetime.datetime.today().date()
    if args.start or args.end:
        return (
            today if not args.start else args.start.date(),
            today if not args.end else args.end.date(),
        )
    if args.date:
        return (args.date.date(), args.date.date())
    if args.month:
        _, days_in_month = calendar.monthrange(today.year, today.month)
        start = datetime.datetime(today.year, today.month, 1)
        end = datetime.datetime(today.year, today.month, days_in_month)
        return (start.date(), end.date())
    return (today, today)


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

    parser.add_argument(
        "--start",
        type=dateutil.parser.parse,
        help="Start date of the range to edit",
    )
    parser.add_argument(
        "--end",
        type=dateutil.parser.parse,
        help="End date of the range to edit",
    )

    parser.add_argument(
        "-d",
        "--date",
        "--day",
        type=dateutil.parser.parse,
        help="Date to edit",
    )

    parser.add_argument(
        "-M",
        "--month",
        action="store_true",
        help="Edit the entire current month",
    )

    parser.add_argument("output", type=Path, help="Output path", nargs="?")

    return parser.parse_args()


@dataclass
class WorklogDiff:
    added: T.List[Worklog]
    changed: T.List[Worklog]
    deleted: T.List[Worklog]


def dump_worklog_day(
    date: datetime.date,
    total_time: datetime.timedelta,
    columns: T.List[str],
    rows: T.List[T.List[str]],
    file: T.IO[str],
) -> None:
    print(file=file)
    print(f"# {date} - total time: {total_time}", file=file)

    rows = rows[:]
    rows.insert(0, columns[:])
    rows[0][0] = "# " + rows[0][0]

    column_widths = [
        max(len(row[i]) for row in rows) for i in range(len(columns))
    ]

    for row in rows:
        for column, column_width, item in zip(columns, column_widths, row):
            is_last = column == columns[-1]
            if is_last:
                print(item, file=file)
            else:
                print(item.ljust(column_width), end=" | ", file=file)


def dump_worklogs(
    start_date: datetime.date,
    end_date: datetime.date,
    worklogs: T.Iterable[Worklog],
    file: T.IO[str],
) -> None:
    columns = ["id", "duration", "issue", "description"]

    print("# when adding a new work log, leave the id column empty.", file=file)

    for day in range((end_date - start_date).days + 1):
        date = start_date + datetime.timedelta(days=day)
        group = [worklog for worklog in worklogs if worklog.date == date]
        total_time = datetime.timedelta(
            seconds=sum(worklog.duration.total_seconds() for worklog in group)
        )

        dump_worklog_day(
            date=date,
            total_time=total_time,
            columns=columns,
            rows=[
                [str(getattr(worklog, column)) for column in columns]
                for worklog in group
            ],
            file=file,
        )


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
            continue
        elif not line:
            last_date = None

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


def apply_diff(api: TempoApi, diff: WorklogDiff) -> None:
    for worklog in diff.added:
        api.create_worklog(worklog)
    for worklog in diff.changed:
        api.update_worklog(worklog)
    for worklog in diff.deleted:
        assert worklog.id
        api.delete_worklog(worklog.id)


def run_editor_and_apply_diff(
    api: TempoApi, source_worklogs: T.List[Worklog], path: Path
) -> None:
    result = run([EDITOR, path])
    if result.returncode != 0:
        print("Editor exited with non-zero status, bailing out")
        exit(1)

    with path.open("r") as handle:
        new_worklogs = list(read_worklogs(file=handle))

    diff = compute_diff(
        source_worklogs=source_worklogs, target_worklogs=new_worklogs
    )
    apply_diff(api, diff)


def main() -> None:
    args = parse_args()
    api = TempoApi(args.api_key, args.user_id)

    start, end = get_date_range(args)
    if end < start:
        print("End date cannot be earlier than start date")
        exit(1)

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "report.txt"

        worklogs = list(api.get_worklogs(start, end))

        with path.open("w") as handle:
            dump_worklogs(start, end, worklogs, file=handle)

        while True:
            try:
                run_editor_and_apply_diff(api, worklogs, path)
            except Exception as ex:
                print("Error:", file=sys.stderr)
                print(ex, file=sys.stderr)
                try:
                    input("Press enter to edit the file again, ^C to exit")
                except KeyboardInterrupt:
                    exit(0)
            else:
                exit(0)


if __name__ == "__main__":
    main()
