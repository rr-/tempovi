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
timesheet. To add new entries, simply add a new row without specifying item ID.

For more options, make sure to check `--help`.
