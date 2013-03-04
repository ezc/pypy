"""Tests for _sqlite3.py"""

import sys
if sys.version_info < (2, 7):
    skip("lib_pypy._sqlite3 doesn't work with python < 2.7")

import pytest
from lib_pypy import _sqlite3

def test_list_ddl():
    """From issue996.  Mostly just looking for lack of exceptions."""
    connection = _sqlite3.connect(':memory:')
    cursor = connection.cursor()
    cursor.execute('CREATE TABLE foo (bar INTEGER)')
    result = list(cursor)
    assert result == []
    cursor.execute('INSERT INTO foo (bar) VALUES (42)')
    result = list(cursor)
    assert result == []
    cursor.execute('SELECT * FROM foo')
    result = list(cursor)
    assert result == [(42,)]

def test_connection_check_init():
    class Connection(_sqlite3.Connection):
        def __init__(self, name):
            pass

    con = Connection(":memory:")
    e = pytest.raises(_sqlite3.ProgrammingError, "con.cursor()")
    assert '__init__' in e.value.message
