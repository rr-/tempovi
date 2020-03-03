Simple tool to edit timesheets on Tempo
=======================================

### Setting it up

First, install the package:

```
git clone https://github.com/rr-/tempovi
cd tempovi
python3 -m pip install --user .
```

Then, provide your credentials by creating `tempovi.ini` file in your
`$XDG_CONFIG_HOME` directory (usually `~/.config`) with the following values:

```ini
user-id=<your jira user id>
api-key=<your api key for tempo>
```

To get the user ID:

- visit any of your Atlassian products
- in the bottom left corner of the screen, click on your avatar
- choose "Profile"
- copy the bold part of the URL https://*******.atlassian.net/jira/people/<b>user-id</b>

To set up the API key, visit here: https://id.atlassian.com/manage/api-tokens

### Usage

Now you can use the tool like so:

```console
tempovi
```

This will launch `$EDITOR` in interactive mode, where you can edit your
timesheet. It'll look like this:

```
# vim: syntax=config
# when adding a new work log, leave the id column empty.

# 2019-07-18 - total time: 9:00:00
# id  | duration | issue     | description
37647 | 0:30:00  | GAUS-538  | Working on issue GAUS-538
37650 | 0:30:00  | GENE-1226 | code review
37665 | 0:20:00  | GAUS-538  | Working on issue GAUS-538
37666 | 0:10:00  | GAUS-564  | code review
37667 | 1:00:00  | GAUS-563  | address code review
37676 | 3:00:00  | II-8      | work on tempovi
37678 | 1:00:00  | GAUS-570  | work
37679 | 0:10:00  | NC-329    | communication
37694 | 2:20:00  | NC-342    | work
```

For more options, make sure to check `--help`.
