# Exchange Calendar to CalDAV sync

This script synchronizes the default calendar of a Microsoft Exchange account with a calendar on a CalDAV server.
Currently, only one-way synchronization from Exchange to CalDAV is supported.
The synchronization is restricted to events – no tasks – but includes event series.

The script uses the prodigious [exchangelib](https://github.com/ecederstrand/exchangelib) to connect to Exchange's EWS interface and fetch incremental changes from the calendar folder.
It then uses the iCal representation in the `mimedata` field, provided by Exchange, of each changed calendar entry to add or update the entry in the CalDAV calendar.
[python-caldav](https://github.com/python-caldav/caldav) is used for interfacing with the CalDAV server.

Before storing the entry, a few changes are made to the data, using the [icalendar](https://github.com/collective/icalendar) library:

- A new custom property `X-EWSSYNC-ITEMID` with the EWS ItemId is added to query items for propageting item deletion from the Exchange server
- The `TRANSP` property is set to `TRANSPARENT` when the event's status is "FREE" according to the `'X-MICROSOFT-CDO-BUSYSTATUS` property
- The `STATUS` property is set to `TENTATIVE` when the event's status is "TENTATIVE" according to the `'X-MICROSOFT-CDO-BUSYSTATUS` property

## Setup & Usage

- Clone this repository
- Optional: create a Python virtual environment and activate it
  ```bash
  python3 -m virtualenv -p python3 venv && . venv/bin/activate
  ```
- Install the dependencies
  ```bash
  pip install -r requirements.txt
  ```
- Copy and customize the config file with the credentials of your Exchange and CalDAV accounts
  ```bash
  cp config.example.toml config.toml && $EDITOR config.toml
  ``` 
- Run `ews_calndar_sync.py` regularly to synchronize changes in the EWS calendar to the CalDAV calendar.
  Typically, you would do this using a cron job (`crontab`, etc.) or a systemd Timer Unit.
  Make sure to use the Python interpreter from the virtualenv (if you use one) and run the process in the working directory where the config.toml file is located.

On the first execution, the script will synchronize all contents of the Exchange Calendar to the CalDAV calendar.
This may take a while (currently, there is no parallelization implemented).
On every subsequent execution, only changes (new events, updated events, deleted events) since the last execution are propagated to the CalDAV server.
This is achieved by using the EWS SyncFolderitems service and storing the sync_state token from the Exchange server in the `statefile` as defined in the config file.
