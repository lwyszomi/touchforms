from java.util import Date
from java.util import Vector

from datetime import datetime, date, time

from setup import init_classpath
init_classpath()
import com.xhaus.jyson.JysonCodec as json

datetime.__json__ = lambda self: json.dumps(self.strftime('%Y-%m-%d'))
date.__json__ = lambda self: json.dumps(self.strftime('%Y-%m-%d'))
time.__json__ = lambda self: json.dumps(self.strftime('%H:%M'))

from org.javarosa.core.model import FormIndex
FormIndex.__json__ = lambda self: json.dumps(self.toString())

def to_jdate(pdate):
    return Date(pdate.year - 1900, pdate.month - 1, pdate.day)

def to_jtime(ptime):
    return Date(1970, 0, 1, ptime.hour, ptime.minute)

def to_pdate(jdate):
    return datetime(jdate.getYear() + 1900, jdate.getMonth() + 1, jdate.getDate())

def to_ptime(jtime):
    return time(jtime.getHours(), jtime.getMinutes())

def to_vect(it):
    v = Vector()
    for e in it:
        v.addElement(e)
    return v
