"""Vroom test utilities."""
import fnmatch
import re
import traceback

import vroom
import vroom.controls

RESULT = vroom.Specification(
    PASSED='passed',
    ERROR='error',
    FAILED='failed',
    SENT='sent')

LOG = vroom.Specification(
    RECEIVED='received',
    MATCHED='matched',
    RESPONDED='responded',
    UNEXPECTED='unexpected',
    ERROR='error')


def IsBad(result):
  """Whether or not a result is something to worry about.

  >>> IsBad(RESULT.PASSED)
  False
  >>> IsBad(RESULT.FAILED)
  True

  Args:
    result: The RESULT.
  Returns:
    Whether the result is bad.
  """
  return result in (RESULT.ERROR, RESULT.FAILED)


def Matches(request, mode, data):
  """Checks whether data matches the requested string under the given mode.

  >>> sentence = 'The quick brown fox jumped over the lazy dog.'
  >>> Matches(sentence, vroom.controls.MODE.VERBATIM, sentence)
  True
  >>> Matches('The * * fox * * the ???? *', vroom.controls.MODE.GLOB, sentence)
  True
  >>> Matches('The quick .*', vroom.controls.MODE.REGEX, sentence)
  True
  >>> Matches('Thy quick .*', vroom.controls.MODE.REGEX, sentence)
  False

  Args:
    request: The requested string (likely a line in a vroom file)
    mode: The match mode (regex|glob|verbatim)
    data: The data to verify
  Returns:
    Whether or not the data checks out.
  """
  if mode is None:
    mode = vroom.controls.DEFAULT_MODE
  if mode == vroom.controls.MODE.VERBATIM:
    return request == data
  elif mode == vroom.controls.MODE.GLOB:
    return fnmatch.fnmatch(data, request)
  else:
    return re.match(request + '$', data) is not None


class Failure(Exception):
  """Raised when a test fails."""


class Failures(Failure):
  """Raised when multiple Failures occur."""

  def __init__(self, failures):
    super(Failures, self).__init__()
    self.failures = failures

  def GetFlattenedFailures(self):
    flattened_failures = []
    for f in self.failures:
      if hasattr(f, 'GetFlattenedFailures'):
        flattened_failures.extend(f.GetFlattenedFailures())
      else:
        flattened_failures.append(f)
    return flattened_failures

  def __str__(self):
    flattened_failures = self.GetFlattenedFailures()
    if len(flattened_failures) == 1:
      return str(flattened_failures[0])
    assert len(flattened_failures) > 0
    return (
        'Multiple failures:\n' +
        '\n\n'.join(str(f) for f in flattened_failures))


class Log(object):
  """A generic log type."""
  TYPE_WIDTH = 10  # UNEXPECTED

  def __init__(self, message=''):
    self.message = message

  def __str__(self):
    # Makes every header be padded as much as the longest message.
    header = ('%%%ds' % self.TYPE_WIDTH) % self.TYPE.upper()
    leader = ('\n%%%ds ' % self.TYPE_WIDTH) % ''
    return ' '.join((header, leader.join(self.message.split('\n'))))


class Received(Log):
  """For received commands."""
  TYPE = LOG.RECEIVED


class Matched(Log):
  """For matched commands."""
  TYPE = LOG.MATCHED

  def __init__(self, line, mode):
    message = 'with "%s" (%s mode)' % (line, mode)
    super(Matched, self).__init__(message)


class Responded(Log):
  """For system responses."""
  TYPE = LOG.RESPONDED


class Unexpected(Log):
  """For unexpected entities."""
  TYPE = LOG.UNEXPECTED


class ErrorLog(Log):
  """For error logs."""
  TYPE = LOG.ERROR

  def __init__(self, extype, exval, tb):
    message = ''.join(traceback.format_exception(extype, exval, tb))
    super(ErrorLog, self).__init__(message)
