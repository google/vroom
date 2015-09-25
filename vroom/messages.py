"""A module to keep track of vim messages."""

import re

import vroom
import vroom.controls
import vroom.test

from vroom.result import Result

# Pylint is not smart enough to notice that all the exceptions here inherit from
# vroom.test.Failure, which is a standard Exception.
# pylint: disable-msg=nonstandard-exception


ERROR_GUESS = re.compile(
    r'^(E\d+\b|ERR(OR)?\b|Error detected while processing .*)')
STRICTNESS = vroom.Specification(
    STRICT='STRICT',
    RELAXED='RELAXED',
    ERRORS='GUESS-ERRORS')
DEFAULT_MODE = vroom.controls.MODE.VERBATIM


def GuessNewMessages(old, new):
  """Guess which messages in a message list are new.

  >>> GuessNewMessages([1, 2, 3, 4], [1, 2, 3, 4, 5, 6, 7])
  [5, 6, 7]
  >>> GuessNewMessages([1, 2, 3, 4], [4, 5, 6, 7])
  [5, 6, 7]
  >>> GuessNewMessages([1, 2, 3, 4], [5, 6, 7])
  [5, 6, 7]
  >>> GuessNewMessages([1, 2, 3, 4], [4, 1, 2, 3])
  [1, 2, 3]

  Args:
    old: The old message list.
    new: The new message list.
  Returns:
    The new messages. Probably.
  """
  # This is made complicated by the fact that vim can drop messages, sometimes
  # after as few as 20 messages. When that's the case we have to guess a bit.
  # Technically, it's always possible to miss exactly [MESSAGE_MAX] messages
  # if you echo them out in a perfect cycle in one command. So it goes.
  # Message lists are straight from vim, so oldest is first.
  for i in range(len(old)):
    if old[i:] == new[:len(old) - i]:
      return new[len(old) - i:]
  return new[:]


def StartsWithBuiltinMessages(messages):
  """Whether the message list starts with the vim built in messages."""
  return len(messages) >= 2 and not messages[0] and messages[1] == (
      'Messages maintainer: Bram Moolenaar <Bram@vim.org>')


def StripBuiltinMessages(messages):
  """Strips the builtin messages."""
  assert len(messages) >= 2
  return messages[2:]


class Messenger(object):
  """Keeps an eye on vim, watching out for unexpected/error-like messages."""

  def __init__(self, vim, env, writer):
    """Creates the messenger.

    Args:
      vim: The vim handler.
      env: The vroom Environment object.
      writer: A place to log messages.
    """
    self.vim = vim
    self.env = env
    self.writer = writer.messages

  def Verify(self, old, new, expectations):
    """Verifies that the message state is OK.

    Args:
      old: What the messages were before the command.
      new: What the messages were after the command.
      expectations: What the command was supposed to message about.
    Returns:
      Result.Error(vroom.test.Failures[MessageFailure]):
          If any message-related failures were detected.
      Result.Success(): Otherwise
    """
    if StartsWithBuiltinMessages(old) and StartsWithBuiltinMessages(new):
      old = StripBuiltinMessages(old)
      new = StripBuiltinMessages(new)
    unread = GuessNewMessages(old, new)
    failures = []
    for message in unread:
      self.writer.Log(vroom.test.Received(message))
    for (desired, mode) in expectations:
      mode = mode or DEFAULT_MODE
      while True:
        try:
          message = unread.pop(0)
        except IndexError:
          expectation = '"%s" (%s mode)' % (desired, mode)
          failures.append(
              MessageNotReceived(expectation, new, self.vim.writer.Logs()))
          break
        if vroom.test.Matches(desired, mode, message):
          self.writer.Log(vroom.test.Matched(desired, mode))
          break
        # Consume unexpected blank if it's the last message. Vim adds spurious
        # blank lines after leaving insert mode.
        # This is done after checking for expected blank messages.
        if message == '' and not unread:
          break
        try:
          self.Unexpected(message, new)
        except MessageFailure as e:
          failures.append(e)
    # Consume unexpected blank if it's the last message.
    if unread and unread[-1] == '':
      unread.pop(-1)
    for remaining in unread:
      try:
        self.Unexpected(remaining, new)
      except MessageFailure as e:
        failures.append(e)

    if failures:
      return Result.Error(vroom.test.Failures(failures))
    else:
      return Result.Success()

  def Unexpected(self, message, new):
    """Handles an unexpected message."""
    self.writer.Log(vroom.test.Unexpected())
    if self.env.message_strictness == STRICTNESS.STRICT:
      raise UnexpectedMessage(message, new, self.vim.writer.Logs())
    elif self.env.message_strictness == STRICTNESS.ERRORS:
      if ERROR_GUESS.match(message):
        raise SuspectedError(message, new, self.vim.writer.Logs())
    raise UnexpectedMessage(
        message, new, self.vim.writer.Logs(), is_significant=False)


class MessageFailure(vroom.test.Failure):
  """For generic messaging troubles."""
  DESCRIPTION = 'Messaging failure.'
  CONTEXT = 12

  def __init__(self, message, messages, commands=None):
    self.messages = messages[-self.CONTEXT:]
    if commands:
      self.commands = commands[-self.CONTEXT:]
    msg = self.DESCRIPTION % {'message': message}
    super(MessageFailure, self).__init__(msg)


class MessageNotReceived(MessageFailure):
  """For when an expected message is never messaged."""
  DESCRIPTION = 'Expected message not received:\n%(message)s'


class UnexpectedMessage(MessageFailure):
  """For when an unexpected message is found."""
  DESCRIPTION = 'Unexpected message:\n%(message)s'

  def __init__(self, message, messages, commands=None, is_significant=True):
    super(UnexpectedMessage, self).__init__(message, messages, commands)
    self._is_significant = is_significant

  def IsSignificant(self):
    return self._is_significant


class SuspectedError(MessageFailure):
  """For when a message that looks like an error is found."""
  DESCRIPTION = 'Suspected error message:\n%(message)s'
