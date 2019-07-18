Simple tool to edit timesheets on Tempo
---------------------------------------

# Usage

Create `tempovi.ini` file in your `$XDG_CONFIG_HOME` dir (usually `~/.config`)
and provide following values there:

```ini
api_key=<your api key for tempo>
user_id=<your jira user id>
```

Now you can use use tool like so:

```console
tempovi
```

This will launch `$EDITOR` in interactive mode, where you can edit your
timesheet. It'll look like this:

```
# syntax:
# id | date | duration | issue | description
# when adding a new item, leave the id column empty.

# 2019-07-18 - total time: 6:30:00
37647 | 2019-07-18 | 0:30:00 | GAUS-538  | work
37650 | 2019-07-18 | 0:30:00 | GENE-1226 | code review
37665 | 2019-07-18 | 0:20:00 | GAUS-538  | work
37666 | 2019-07-18 | 0:10:00 | GAUS-564  | code review
37667 | 2019-07-18 | 1:00:00 | GAUS-563  | address code review
37676 | 2019-07-18 | 3:00:00 | II-8      | work on tempovi
37678 | 2019-07-18 | 1:00:00 | GAUS-570  | work
```

For more options, make sure to check `--help`.
