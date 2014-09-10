"""Patterns common to all vroom components."""


def __read_version_txt():
  import pkgutil
  return pkgutil.get_data('vroom', 'VERSION.txt').strip()

__version__ = __read_version_txt()


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
