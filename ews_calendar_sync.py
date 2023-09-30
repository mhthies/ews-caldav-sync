#!/usr/bin/env python3

# Copyright 2021 Michael Thies <mail@mhthies.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import datetime
import logging
import argparse
import toml
from exchangelib import Credentials, Configuration, Account, DELEGATE, IMPERSONATION, CalendarItem
import caldav
import icalendar

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='Incrementally synchronizes a Microsoft Exchange calendar to a CalDAV server.')
parser.add_argument('--config', default='config.toml', help='Path of the TOML configuration file')
args = parser.parse_args()

with open(args.config, encoding='utf-8') as f:
    config = toml.load(f)

logging.basicConfig(level=config['misc']['loglevel'])

# EWS connection
ews_credentials = Credentials(username=config['ews']['username'], password=config['ews']['password'])
ews_config = Configuration(server=config['ews']['server'], credentials=ews_credentials)
ews_account = Account(config['ews']['account'], access_type=IMPERSONATION if config['ews']['impersonate'] else DELEGATE,
                      config=ews_config)
ews_calendar = ews_account.calendar

# CalDAV connection
dav_client = caldav.DAVClient(url=config['caldav']['url'], username=config['caldav']['username'],
                              password=config['caldav']['password'])
dav_principal = dav_client.principal()
dav_calendar: caldav.Calendar = dav_principal.calendar(name=config['caldav']['calendar'])


def create_ewsid_filter(the_id):
    from caldav.elements import cdav, dav

    data = cdav.CalendarData()
    prop = dav.Prop() + data
    query = cdav.TextMatch(the_id)
    query = cdav.PropFilter("X-EWSSYNC-ITEMID") + query
    query = cdav.CompFilter("VEVENT") + query
    vcalendar = cdav.CompFilter("VCALENDAR") + query
    the_filter = cdav.Filter() + vcalendar
    return cdav.CalendarQuery() + [prop, the_filter]


try:
    with open(config['misc']['statefile'], 'r') as f:
        sync_state = f.read()
except FileNotFoundError:
    sync_state = None

now = datetime.datetime.now(tz=ews_account.default_timezone)

fetch_ids = []
for change_type, item in ews_calendar.sync_items(sync_state=sync_state, only_fields=['uid', 'id', 'changekey']):
    if change_type in ('create', 'update'):
        fetch_ids.append((item.id, item.changekey))
    elif change_type == 'delete':
        try:
            dav_object = dav_calendar.search(create_ewsid_filter(item.id))[0]
        except IndexError:
            logger.error("Deleted item %s not found on CalDAV server", item)
            continue
        except Exception as e:
            logger.error("Error while fetching deleted item %s from CalDAV server:", item, exc_info=e)
            continue
        logger.info('Deleting event from CalDAV server: %s', dav_object)
        try:
            dav_object.delete()
        except Exception as e:
            logger.error("Error while deleting item from CalDAV server: %s", dav_object, exc_info=e)
            continue

for item in ews_account.fetch(ids=fetch_ids):
    if isinstance(item, CalendarItem):
        logger.info('Adding/Updating %s to CalDAV server', item.subject)
        if not item.mime_content:
            logger.warning("Item %s has no mime_content field", item.subject)
            continue
        try:
            data: icalendar.Calendar = icalendar.Calendar.from_ical(item.mime_content.decode('utf-8'))
            del data['method']
            event_data = next(iter(c for c in data.subcomponents if isinstance(c, icalendar.Event)))
            status = event_data['X-MICROSOFT-CDO-BUSYSTATUS']
            event_data['transp'] = 'TRANSPARENT' if status == 'FREE' else 'OPAQUE'
            if status == 'TENTATIVE':
                event_data['status'] = 'TENTATIVE'
            event_data['X-EWSSYNC-ITEMID'] = item.id
        except Exception as e:
            logger.error("Error while parsing Exchange iCal item: %s", item, exc_info=e)
            continue
        try:
            dav_calendar.save_event(data.to_ical())
        except Exception as e:
            logger.error("Error while adding/updating item on CalDAV server: %s", data, exc_info=e)
            continue
    else:
        logger.warning("Ignoring non-calendar item %s from Exchange server", item)

with open(config['misc']['statefile'], 'w') as f:
    f.write(ews_calendar.item_sync_state)
