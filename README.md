# PyPrimion

PyPrimion is a webinterface handler for the Primion Prime Web Systems used by many companies for employee time tracking purposes.

PyPrimion allows you to access data from your time tracking journal right from within Python, utilizing native datatypes such as `datetime.date`, and `datetime.timedelta` to represent values from the webinterface.

PyPrimion is licensed under MIT License (a.k.a X11 license).
(c) 2017, Jan Willhaus

## Installation

Installing PyPrimion is as simple as is gets with pip: `pip install git+https://github.com/Janwillhaus/PyPrimion.git`.

## Initialization and login

To login to your employer's Prime Web instance, simply instantiate a `Primion` object with the base URL of the webinterface (which is shown in the browser when opening the login page). The `login` method takes `username`, and `password` to log you in:

```
from pyprimion import Primion

p = Primion(baseurl='https://location.of-your.primion/primeweb/')
p.login(username='max4711', 'supersecurepassword')
```
