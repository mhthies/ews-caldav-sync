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
- Run `ews_calendar_sync.py` regularly to synchronize changes in the EWS calendar to the CalDAV calendar.
  Typically, you would do this using a cron job (`crontab`, etc.) or a systemd Timer Unit.
  Make sure to use the Python interpreter from the virtualenv (if you use one) and run the process in the working directory where the config.toml file is located.

Alternatively, using the Docker container:

- Download the [config file template](./config.example.toml) from this repository, save it as `config.toml` and customize it with the credentials of your Exchange and CalDAV accounts
- Run `ews_calendar_sync` via docker:
  ```bash
  docker run -it --rm --name ews-caldav-sync -v ./config.toml:/app/config.toml -v ./syncstate.txt:/app/syncstate.txt ghcr.io/mhthies/ews-caldav-sync:latest
  ```

On the first execution, the script will synchronize all contents of the Exchange Calendar to the CalDAV calendar.
This may take a while (currently, there is no parallelization implemented).
On every subsequent execution, only changes (new events, updated events, deleted events) since the last execution are propagated to the CalDAV server.
This is achieved by using the EWS SyncFolderitems service and storing the sync_state token from the Exchange server in the `statefile` as defined in the config file.

## Known Issues

Issues when syncing to a Nextcloud calendar:
- Nextcloud (since version 22) forbids recreating/updating a calendar item with the id of a previously deleted item.
  ("400 Bad Request: Deleted calendar object with uid already exists in this calendar collection.")
  Updates/recreations of previously deleted events in the Exchange calendar – which often happen due to meeting invitation updates – will result in an exception of the ews_calendar_sync script and the update being ignored in the CalDAV calendar.
  This issue is caused by Nextcloud's new calendar recycle bin feature and is already reported to Nextcloud: https://github.com/nextcloud/server/issues/30096
- ~~Nextcloud sets ContentType to `text/html` in emtpy responses. The caldav library logs this as a warning to the console ("unexpected content type from server: text/html; charset=UTF-8. Please raise an issue[…]").
  Reported to caldav library: https://github.com/python-caldav/caldav/issues/142~~
  Fixed with `caldav` version 0.8.1.

General issues:
- ~~Events with with a slash in their iCal UID cause errors when being uploaded to the CalDAV server, due to unescaped slashes in the CalDAV object path.
  Exchange does not create such UIDs itself, but they may be imported with existing iCal datasets into Outlook/Exchange
  Reported to caldav library: https://github.com/python-caldav/caldav/issues/143~~
  Mostly fixed with `caldav` version 0.8.1.
