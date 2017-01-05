# PyPrimion

**PyPrimion is currently a work-in-progress. Only journal data downloading is supported yet.**

PyPrimion is a webinterface handler for the Primion Prime Web Systems used by many companies for employee time tracking purposes.

PyPrimion allows you to access data from your time tracking journal right from within Python, utilizing native datatypes such as `datetime.date`, and `datetime.timedelta` to represent values from the webinterface.

## Installation

Installing PyPrimion is as simple as is gets with pip: `pip install git+https://github.com/Janwillhaus/PyPrimion.git`.

## Initialization and login

To login to your employer's Prime Web instance, simply instantiate a `Primion` object with the base URL of the webinterface (which is shown in the browser when opening the login page). The `login` method takes `username`, and `password` to log you in:

```python
from pyprimion import Primion

p = Primion(baseurl='https://location.of-your.primion/primeweb/')
p.login(username='max4711', 'supersecurepassword')
```

**Caveat:** The Webinterface might have a relatively short session timeout configured, and new queries might fail after 10-15 minutes. PyPrimion currently does not have proper timeout detection, so you might have to try-except `AttributeError`s when querying in long intervals, or just re-login beforehand. Future versions of PyPrimion will do this automatically (see issue #1).

## Downloading journal data

To get the journal data of the past three days, simply execute the `journal` method of PyPrimion:

```python
p.journal()
```

The returned data will be a dictionary with `datetime.date` keys for each parsed date from today til three days ago. If you want to download data from a specific date range, you may provide `date_start`, and/or `date_end`:

```python
from datetime import date

# From May 17, 2016 til today
p.journal(date_start=date(2016,5,17))

# From April 25, 2015 til March 12, 2016
p.journal(date_start=date(2015,4,25),date_end=date(2016,3,12))
```

## Example: Determine today's closing time

If you're working variable hours (no mandatory check-in time), it might be hard to keep track of your worked hours, and your daily closing time. This little snipped outputs today's closing time determined by the journal's check-in time, and your target working hours:

```python
today = date.today()
data = p.journal(date_start=today)[today]

print('Today\'s closing time is',
      (data['login'] + data['target']).strftime('%H:%M'))
```

## License

PyPrimion is licensed under MIT License (a.k.a X11 license).<br />
(c) 2017, Jan Willhaus

See included `LICENSE` file for the full text.
