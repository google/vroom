"""Patterns common to all vroom components."""
import sys

try:
  from ._version import __version__ as __version__
except ImportError:
  import warnings
  warnings.warn('Failed to load __version__ from setuptools-scm')
  __version__ = '__unknown__'


# Don't even try to run under python 2 or earlier. It will seem to work but fail
# in corner cases with strange encoding errors.
if sys.version_info[0] < 3:
  raise ImportError('Python < 3 is unsupported')


def Specification(*numbered, **named):
  """Creates a specification type, useful for defining constants.

  >>> Animal = Specification('PIG', 'COW')
  >>> Animal.PIG
  0
  >>> Animal.COW
  1
  >>> Animal.Lookup(1)
  'COW'

  >>> Animal = Specification(PIG='pig', COW='cow')
  >>> Animal.PIG
  'pig'
  >>> Animal.COW
  'cow'
  >>> tuple(sorted(Animal.Fields()))
  ('COW', 'PIG')
  >>> tuple(sorted(Animal.Values()))
  ('cow', 'pig')

  Args:
    *numbered: A list of fields (zero-indexed) that make up the spec.
    **named: A dict of fields to make up the spec.
  Returns:
    A 'Specification' type with the defined fields. It also has these methods:
      Lookup: Given a value, try to find a field with that value.
      Fields: Returns an iterable of all the fields.
      Values: Returns an iterable of all the values.
  """
  enum = dict({n: i for i, n in enumerate(numbered)}, **named)
  inverted = dict(zip(enum.values(), enum.keys()))
  data = dict(enum)
  data['Lookup'] = inverted.get
  data['Fields'] = enum.keys
  data['Values'] = enum.values
  return type('Specification', (), data)


class ParseError(Exception):
  """For trouble when parsing vroom scripts."""

  def __init__(self, *args, **kwargs):
    self.lineno = None
    super(ParseError, self).__init__(*args, **kwargs)

  def SetLineNumber(self, lineno):
    self.lineno = lineno


class ConfigurationError(Exception):
  """For improperly configured vroom scripts, syntax nonwithstanding."""
