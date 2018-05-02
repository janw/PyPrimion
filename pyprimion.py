#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta, date
from dateutil.parser import parse
from os import path
import pandas as pd
from pandas.io.parsers import TextParser
import json

TIMEDELTA_FMT = "+%02d:%02d"
TIMEDELTA_FMT_NEG = "-%02d:%02d"


def parse_hhmm_to_timedelta(hhmm, allow_negatives=False, parse_as_time=False):
    import re
    from datetime import timedelta

    if allow_negatives and not parse_as_time:
        re_match = re.search('(-?\d+)\:(\d+)', hhmm)
    else:
        re_match = re.search('(\d+)\:(\d+)', hhmm)

    if re_match:
        if parse_as_time:
            return datetime.strptime(re_match.group(), '%H:%M').time()

        hourgroup = re_match.group(1)
        minutesgroup = re_match.group(2)
        if hourgroup.startswith('-'):
            hourgroup = hourgroup[1:]
            return timedelta(hours=-int(hourgroup), minutes=-int(minutesgroup))
        else:
            return timedelta(hours=int(hourgroup), minutes=int(minutesgroup))

    return None


class DateTimeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, timedelta):
            seconds = obj.total_seconds()
            if seconds < 0:
                m, s = divmod(seconds * (-1), 60)
                h, m = divmod(m, 60)
                return TIMEDELTA_FMT_NEG % (h, m)
            else:
                m, s = divmod(seconds, 60)
                h, m = divmod(m, 60)
                return TIMEDELTA_FMT % (h, m)

        return super().default(obj)


class Primion:

    _urls = {'login': 'Login.jsp',
             'journal_pre': 'Querybuchungsjournal.jsp',
             'journal': 'buchungsjournal.jsp'
             }

    _info_strings = {'**': 'Deleted',
                     '++': 'Corrected relatively',
                     '==': 'Corrected absolutely',
                     'FK': 'Erronous entry',
                     '*': 'Holiday'
                     }

    _write_journal = False
    _print_login_name = False

    _default_date_delta = 3

    fullname = None
    _user_id = None

    def __init__(self, baseurl):

        self._baseurl = baseurl
        self._basepath = path.dirname(path.abspath(__file__))
        self.session = requests.session()

    def login(self, username, password):

        self._username = username
        self._password = password

        login_data = {
            'post': 'true',
            'language': 'de',
            'screensize': 1024,
            'browser': 'NS5',
            'browser_java_en': 'true',
            'HasJavascript': 'true',
            'userid': self._username,
            'password': self._password
        }

        r = self.session.post(self._baseurl + self._urls['login'], data=login_data)

        soup = BeautifulSoup(r.text, 'html.parser')

        items_beschriftung = soup.find_all('font', attrs={'class': 'beschriftung'})
        for idx, item in enumerate(items_beschriftung):
            if len(item.contents) and item.contents[0] == 'Name\xa0\xa0':
                self.fullname = items_beschriftung[idx + 1].contents[0]

        if self.fullname is not None and self._print_login_name:
            print('Login successful as:', self.fullname)

    def _construct_post_data(self, date_start=None, date_end=None):

        if self._user_id is None:
            r_journal = self.session.get(self._baseurl + self._urls['journal_pre'])
            soup_journal = BeautifulSoup(r_journal.text, 'html.parser')
            self._user_id = soup_journal.find('input', attrs={'name': 'LSTUSERS'}).attrs['value']

        if date_end is None:
            date_end = datetime.today()
        elif isinstance(date_end, datetime):
            date_end = date_end.date()
        elif isinstance(date_end, str):
            date_end = parse(date_end).date()


        if date_start is None:
            date_start = date_end - timedelta(days=self._default_date_delta)
        elif isinstance(date_start, datetime):
            date_start = date_start.date()
        elif isinstance(date_start, str):
            date_start = parse(date_start).date()

        return ({
            'LSTUSERS': self._user_id,
            'DATE_START': date_start.strftime('%d.%m.%Y'),
            'DATE_END': date_end.strftime('%d.%m.%Y'),
            'DISPLAY_TYPE': 'BUCHUNG',
            'LSTUSERS': '514500000545710F',
            'NNAME': 'Willhaus, Jan',
            'ZEIT_TAG': 'ON',
            'ZEIT_SUM': 'ON',
            'CB_KONTENKZ': 'ON',
            'OUTPUTARTKZ': '0',
            'OUTPUTART': '0',
            'KONTOGRUPPE': '0',
            'SOLL_TAG': 'ON',
            'SOLL_SUM': 'ON',
            'SALDO_TAG': 'ON',
            'SALDO_SUM': 'ON',
            'SUMMENWERTE': 'ON',
            'KORRFEHLKONT': 'ON',
            'KORRLOHNKONT': 'ON',
            'RUND_B': 'ON',
            'ANZPROTAG': '2',
            'FUEHRENDE_NULLEN': 'ON',
            'LAYOUT': '0',
            'AKTKONTEN': 'ON',
        }, date_start)

    def journal(self, date_start=None, date_end=None):

        journal_data, date_start = self._construct_post_data(date_start, date_end)
        r_journal = self.session.post(self._baseurl + self._urls['journal'], data=journal_data)
        soup_journal = BeautifulSoup(r_journal.text, 'html.parser')

        table = soup_journal.find('table', attrs={'id': 'ScrollTable'})
        self.table = table

        current_year = date_start.year
        prev_row_date = None
        row_date = None
        data = {}

        for row in table.find_all('tr', attrs={'class': re.compile('ZebraRow')}):
            cells = row.findChildren('td')

            # DATUM
            date_match = re.search('^(\d+\.\d+.)', cells[0].string)
            if date_match is None:
                continue

            prev_row_date = row_date
            row_date = datetime.strptime(date_match.group(), '%d.%m.')

            if prev_row_date and prev_row_date.month > row_date.month:
                current_year = current_year + 1

            row_date = row_date.replace(year=current_year)

            idx = row_date.date().isoformat()
            if data.get(idx) is None:
                data[idx] = {
                    'periods': [],
                }

            # INFO
            info = cells[2].string.strip()
            if info in self._info_strings.keys():
                data[idx]['info'] = self._info_strings[info]

            # KOMMEN ZEIT
            probable_login = cells[3].string
            holiday_match = re.search('\((.*)\)', probable_login)
            if holiday_match:
                data[idx]['holiday'] = holiday_match.group(1)
                continue

            comptime_match = re.search('Zeitausgleich', probable_login)
            if comptime_match:
                data[idx]['info'] = probable_login
                continue

            row_data = {}
            result = parse_hhmm_to_timedelta(cells[3].string, parse_as_time=True)
            if result is not None:
                row_data['login'] = datetime.combine(row_date, result)

            # GEHEN ZEIT
            result = parse_hhmm_to_timedelta(cells[4].string, parse_as_time=True)
            if result is not None:
                row_data['logout'] = datetime.combine(row_date, result)

            # Insert calculated period duration
            if 'logout' in row_data.keys() and 'login' in row_data.keys():
                row_duration = row_data['logout'] - row_data['login']
                row_data['duration'] = row_duration

            # TAG SOLLZEIT
            result = parse_hhmm_to_timedelta(cells[6].string, allow_negatives=False)
            if result is not None:
                row_data['target'] = result

            # TAG SALDO
            result = parse_hhmm_to_timedelta(cells[7].string, allow_negatives=True)
            if result is not None:
                row_data['day_balance'] = result

            # MONAT SALDO
            result = parse_hhmm_to_timedelta(cells[10].string, allow_negatives=True)
            if result is not None:
                row_data['total_balance'] = result

            data[idx]['periods'].append(row_data)
        return data

    def print_journal(self):
        print(json.dumps(self.journal(), indent=4, cls=DateTimeJSONEncoder))
