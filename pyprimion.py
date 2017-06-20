#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import re
import pendulum
from os import path


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

        if self.fullname is not None:
            print('Login successful as:', self.fullname)

    def journal(self, date_start=None, date_end=None):

        if self._user_id is None:
            r_journal = self.session.get(self._baseurl + self._urls['journal_pre'])
            soup_journal = BeautifulSoup(r_journal.text, 'html.parser')
            self._user_id = soup_journal.find('input', attrs={'name': 'LSTUSERS'}).attrs['value']

        if date_end is None:
            date_end = pendulum.today()

        if date_start is None:
            date_start = date_end.subtract(days=self._default_date_delta)

        journal_data = {
            'LSTUSERS': self._user_id,
            'DATE_START': date_start.strftime('%d.%m.%Y'),
            'DATE_END': date_end.strftime('%d.%m.%Y'),
            'DISPLAY_TYPE': 'BUCHUNG',
            'FUEHRENDE_NULLEN': 'ON',
            'ZEIT_TAG': 'ON',
            'SOLL_TAG': 'ON',
            'SALDO_TAG': 'ON',
            'SALDO_SUM': 'ON,',
            'ANZPROTAG': 2,
            'OUTPUTART': 0,
            'CB_KONTENKZ_HIDDEN': 'ON',
            'RUND_B': 'ON',
        }

        r_journal = self.session.post(self._baseurl + self._urls['journal'], data=journal_data)
        soup_journal = BeautifulSoup(r_journal.text, 'html.parser')

        # Remove completely unnecessary children from soup
        for script in soup_journal.findChildren('script'):
            script.extract()
        for div in soup_journal.findChildren('div', id='ScrollTableHeadSpan'):
            div.extract()
        for img in soup_journal.findChildren('img'):
            img.extract()
        for headline in soup_journal.findChildren(re.compile('^h[1-6]')):
            headline.extract()

        if self._write_journal:
            with open(path.join(self._basepath, 'journal.html'), 'w') as f:
                print(soup_journal.prettify(), file=f)

        table = soup_journal.find('table', attrs={'id': 'ScrollTable'})
        self.table = table

        current_year = date_start.year
        prev_row_date = None
        row_date = None
        data = {}

        for row in table.find_all('tr', attrs={'class': re.compile('ZebraRow')}):
            cells = row.findChildren('td')

            # Assume first cell to be the date, and try to regex it
            date_match = re.search('^(\d+\.\d+.)', cells[0].string)
            if date_match is None:
                continue

            row_data = {}
            prev_row_date = row_date
            row_date = pendulum.strptime(date_match.group(), '%d.%m.')
            iso_date = row_date.isoformat()

            if prev_row_date and prev_row_date.month > row_date.month:
                current_year = current_year + 1

            row_date = row_date.replace(year=current_year)

            info = cells[2].string.strip()
            if info in self._info_strings.keys():
                row_data['info'] = self._info_strings[info]

            probable_login = cells[3].string
            holiday_match = re.search('\((.*)\)', probable_login)
            if holiday_match:
                row_data['holiday'] = holiday_match.group(1)
                data[row_date] = row_data
                continue

            comptime_match = re.search('Zeitausgleich', probable_login)
            if comptime_match:
                row_data['info'] = probable_login
                data[row_date] = row_data
                continue

            login_match = re.search('(\d+\:\d+)', cells[3].string)
            if login_match:
                row_login_time = pendulum.strptime(login_match.group(), '%H:%M').time()
                row_data['login'] = pendulum.combine(row_date, row_login_time)

            logout_match = re.search('(\d+\:\d+)', cells[4].string)
            if logout_match:
                row_logout_time = pendulum.strptime(logout_match.group(), '%H:%M').time()
                row_data['logout'] = pendulum.combine(row_date, row_login_time)

            if 'logout' in row_data.keys() and 'login' in row_data.keys():
                row_duration = row_data['logout'] - row_data['login']
                row_data['duration'] = row_duration

            target_match = re.search('(\d+)\:(\d+)', cells[6].string)
            if target_match:
                row_data['target'] = pendulum.interval(hours=int(target_match.group(1)),
                                                       minutes=int(target_match.group(2)))

            if 'target' in row_data.keys() and 'duration' in row_data.keys():
                row_data['day_balance'] = row_data['duration'] - row_data['target']

            balance_match = re.search('(-?\d+)\:(\d+)', cells[8].string)
            if balance_match:
                row_data['total_balance'] = pendulum.interval(hours=int(balance_match.group(1)),
                                                              minutes=int(balance_match.group(2)))

            data[row_date] = row_data

        return data

# if __name__ == "__main__":
#     import sys
#     fib(int(sys.argv[1]))
