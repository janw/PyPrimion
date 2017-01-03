#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import re
import configparser
import os
from collections import namedtuple
from datetime import datetime, date, timedelta

default_user = ''
default_pass = ''


class Primion:

    _urls = dict(base='',
                 login='Login.jsp',
                 journal='PersoBuchungen.jsp')

    fullname = None

    def __init__(self, baseurl=None, username=None, password=None):

        self._basepath = os.path.dirname(os.path.realpath(__file__))

        if baseurl is None:
            self._baseurl = self._urls['base']
        else:
            self._baseurl = baseurl

        if username is None:
            self._username = default_user
        else:
            self._username = username

        if password is None:
            self._password = default_pass
        else:
            self._password = password

        self.session = requests.session()

    def login(self):

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

        if date_end is None:
            date_end = date.today()

        if date_start is None:
            date_start = date_end + timedelta(days=-31)

        current_year = date_start.year

        journal_data = {
            'DATE_START': date_start,
            'DATE_END': date_end,
            'DISPLAY_TYPE': 'BUCHUNG',
            'FUEHRENDE_NULLEN': 'ON',
            'ZEIT_TAG': 'ON',
            'SOLL_TAG': 'ON',
            'SALDO_TAG': 'ON',
        }

        r_journal = self.session.post(self._baseurl + self._urls['journal'], data=journal_data)
        soup_journal = BeautifulSoup(r_journal.text, 'html.parser')

        tables = soup_journal.find_all('table', attrs={'id': 'ScrollTable'})

        if len(tables):
            table = tables[0]
        else:
            raise Exception('Did not find journal on page')

        self.table = table
        prev_row_date = None
        for row in table.find_all('tr', attrs={'class': re.compile('ZebraRow')}):
            first_col = next(row.children)
            row_date = None

            if len(first_col.contents):
                try:
                    probable_date = first_col.contents[0].contents[0]
                except AttributeError:
                    pass

                try:
                    row_date = datetime.strptime(probable_date, '%d.%m.')

                    if prev_row_date and prev_row_date.month > row_date.month:
                        current_year = current_year + 1

                    row_date = row_date.replace(year=current_year)
                except ValueError:
                    pass
                except TypeError:
                    pass

            if row_date:
                prev_row_date = row_date
                print('Parsing', row_date.strftime('%a, %d.%m.%Y'))


# if __name__ == "__main__":
#     import sys
#     fib(int(sys.argv[1]))
