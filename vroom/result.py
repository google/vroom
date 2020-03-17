"""Result type."""

from collections import namedtuple
from enum import Enum

class ResultType(Enum):
  result = 1
  error = 2

# Inherit from namedtuple so we get an immutable value.
class Result(namedtuple('Result', ['status', 'value'])):
  """Holds the result or error of a function call.

  status should be one of ResultType.result or ResultType.error
  """

  @classmethod
  def Result(cls, value):
    return super(Result, cls).__new__(
        cls, status=ResultType.result, value=value)

  @classmethod
  def Error(cls, value):
    return super(Result, cls).__new__(cls, status=ResultType.error, value=value)

  @classmethod
  def Success(cls):
    """Used to indicate success when the actual value is irrelevant."""
    return super(Result, cls).__new__(cls, status=ResultType.result, value=True)

  def IsError(self):
    return self.status is ResultType.error

  def IsSignificant(self):
    if self.status is ResultType.result:
      return False
    return self.value.IsSignificant()
