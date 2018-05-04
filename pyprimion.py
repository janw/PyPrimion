#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta, date
from dateutil.parser import parse
from os import path
import json

TIMEDELTA_FMT = "+%d:%02d:%02d"
TIMEDELTA_FMT_NEG = "-%d:%02d:%02d"

HERE = path.dirname(path.realpath(__file__))
CONFIG_FILENAME = 'pyprimion.ini'
GLOBAL_VERBOSITY = 0

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


def parse_timedelta_to_TDFMT(timedelta_obj):
    seconds = timedelta_obj.total_seconds()
    if seconds < 0:
        m, s = divmod(seconds * (-1), 60)
        h, m = divmod(m, 60)
        return TIMEDELTA_FMT_NEG % (h, m, s)
    else:
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return TIMEDELTA_FMT % (h, m, s)


class DateTimeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, timedelta):
            return parse_timedelta_to_TDFMT(obj)

        return super().default(obj)


class Primion:

    _lunchbreak_duration = timedelta(minutes=30)
    _lunchbreak_after_duration = timedelta(hours=6)

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

        if not baseurl.endswith('/'):
            baseurl += '/'

        self._baseurl = baseurl
        self._HERE = path.dirname(path.abspath(__file__))
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


def cli():
    from configparser import ConfigParser
    import argparse
    import keyring
    from os import environ

    now = datetime.now()
    today = datetime.today()
    verbose = GLOBAL_VERBOSITY

    XDG_CONFIG_HOME = environ.get(
        'XDG_CONFIG_HOME',
        path.expandvars(path.join('$HOME', '.config')))

    configfile = path.join(XDG_CONFIG_HOME, CONFIG_FILENAME)
    config = ConfigParser(allow_no_value=True)
    config.read(configfile)

    parser = argparse.ArgumentParser(description='Track your today\'s working hours.')

    parser.add_argument('-d', '--delta', dest='delta', action='store_true',
                        help='''
                        Only output the delta of work time, nothing more.
                        ''')
    parser.add_argument('-co', '--check-out', dest='checkout', action='store_true',
                        help='''
                        Only output the target check-out time, nothing more.
                        ''')
    parser.add_argument('-v', '--verbose', dest='verbose', action='count',
                        help='''
                        Increase the level of verbosity of the command.
                        ''')
    parser.add_argument('-U', '--URL', dest='url',  # action='count',
                        help='''
                        URL of your company's PrimeWeb website.
                        ''')
    parser.add_argument('-u', '--user', dest='user',  # action='count',
                        help='''
                        Username to use to log in.
                        ''')
    parser.add_argument('-p', '--pass', dest='passwd',  # action='count',
                        help='''
                        Password to use to log in.
                        ''')
    parser.add_argument('-s', '--save-login', dest='save_login', action='store_true',
                        help='''
                        Save the entered login details (URL, username) in a
                        config file, and the password in the system keyring.
                        Next time you run pyprimion, you won't need to add
                        -U, -u, -p.
                        ''')

    args = parser.parse_args()

    if args.delta or args.checkout:
        verbose = -1

    primion_url = ''
    primion_user = ''
    primion_passwd = ''
    if 'Primion' in config:
        primion_url = config['Primion'].get('url', '')
        primion_user = config['Primion'].get('username', '')
        primion_passwd = keyring.get_password('pyprimion', primion_user)

    # Input arguments override settings in configfile
    if args.url is not None:
        primion_url = args.url
    if args.user is not None:
        primion_user = args.user
    if args.passwd is not None:
        primion_passwd = args.passwd
    if args.verbose is not None:
        verbose = args.verbose

    if '' in [primion_url, primion_user, primion_passwd]:
        print('please provide URL, username, and password')
        parser.print_usage()
        return

    if args.save_login:
        if 'Primion' not in config:
            config['Primion'] = {}
        config['Primion']['url'] = primion_url
        config['Primion']['username'] = primion_user
        config.write(configfile)
        keyring.set_password('pyprimion', primion_user, primion_passwd)

    prim = Primion(primion_url)
    if verbose > 1:
        prim._print_login_name = True

    prim.login(username=primion_user,
               password=primion_passwd)
    journ = prim.journal(date_start=today, date_end=today)
    journ = journ.popitem()[1]
    day_balance = journ['periods'][-1]['day_balance']
    coretime = journ['periods'][-1]['target']

    try:
        time_of_checkin = journ['periods'][-1].get('login', None)
    except IndexError:
        time_of_checkin = None

    if time_of_checkin is None:
        raise Exception('Journal contains no check-in time for today. Have you checked in?')

    time_of_checkout = time_of_checkin - day_balance
    time_after_lunchbreak = time_of_checkout + prim._lunchbreak_duration

    verb_print(verbose, 'Your core time from Primion: %s' % coretime, verbose=2)
    verb_print(verbose, 'Downloaded check-in time from Primion:   %s' % time_of_checkin, verbose=1)
    verb_print(verbose, 'Your current period\'s balance was: %s' % parse_timedelta_to_TDFMT(day_balance), verbose=2)
    verb_print(verbose, 'Your target check-out time from Primion: %s' % time_of_checkout, verbose=1)

    time_delta = time_of_checkout - now
    time_delta_lunchbreak = time_after_lunchbreak - now
    time_delta_overtime = now - time_after_lunchbreak

    if args.delta:
        if (now - time_of_checkout).total_seconds() < 0:
            print('-%s' % (time_of_checkout - now))
        else:
            print(now - time_of_checkout)

    elif args.checkout:
        print(time_of_checkout)

    else:
        if time_delta.total_seconds() > 0:
            print('You still have %s to go' % time_delta)
        elif time_delta_lunchbreak.total_seconds() > 0:
            print('Core time is done. You are still %s in limbo' % time_delta_lunchbreak)
        else:
            print('Time to check out. You are in overtime for %s' % time_delta_overtime)

    return


def verb_print(verbosity_level, *args, **kwargs):
    import builtins
    """My custom print() function."""
    # Adding new arguments to the print function signature
    # is probably a bad idea.
    # Instead consider testing if custom argument keywords
    # are present in kwargs
    if kwargs.get('verbose') is not None:
        if kwargs.pop('verbose') <= verbosity_level:
            return builtins.print(*args, **kwargs)
    else:
        return builtins.print(*args, **kwargs)


if __name__ == "__main__":
    cli()
