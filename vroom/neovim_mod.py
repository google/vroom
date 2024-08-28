from vroom.vim import CONFIGFILE
from vroom.vim import Communicator as VimCommunicator
import subprocess
import tempfile
import time
import neovim
import os

class Communicator(VimCommunicator):
  """Object to communicate with a Neovim server."""

  _listen_addr = None

  def __init__(self, args, env, writer):
    self.writer = writer.commands
    self.args = args
    self.start_command = [
        'nvim',
        '-u', args.vimrc,
        '-c', 'set shell=' + args.shell,
        '-c', 'source %s' % CONFIGFILE]
    self.env = env
    self._cache = {}

  def Quit(self):
    if not hasattr(self, 'nvim'):
      # Never started
      return

    self.nvim.quit()

  def Start(self):
    """Starts Neovim"""
    if self._listen_addr is not None:
      raise InvocationError('Called Start on already-running neovim instance')
    tmpdir = tempfile.mkdtemp()
    self._listen_addr = os.path.join(tmpdir, 'nvim.pipe')
    # Legacy env var, used by nvim <0.8
    self.env['NVIM_LISTEN_ADDRESS'] = self._listen_addr
    self.start_command += ['--listen', self._listen_addr]

    self.process = subprocess.Popen(self.start_command, env=self.env)
    start_time = time.time()
    # Wait at most 5s for the Neovim socket
    while not os.path.exists(self._listen_addr) \
            and time.time() - start_time < 5:
      time.sleep(0.01)
    self.nvim = neovim.attach('socket', path=self._listen_addr)

  def Communicate(self, command, extra_delay=0):
    """Sends a command to Neovim.

    Blocks forever if remote nvim quit unexpectedly.

    Args:
      command: The command to send.
      extra_delay: Delay in excess of --delay
    """
    self.writer.Log(command)
    parsed_command = self.nvim.replace_termcodes(command, True, True, True)
    self.nvim.feedkeys(parsed_command)
    self._cache = {}
    time.sleep(self.args.delay + extra_delay)

  def Ask(self, expression):
    """Asks vim for the result of an expression.

    Blocks forever if remote nvim quit unexpectedly.

    Args:
      expression: The expression to ask for.
    Returns:
      Return value from vim.
    """
    return self.nvim.eval(expression)

  def GetBufferLines(self, number):
    """Gets the lines in the requested buffer.

    Args:
      number: The buffer number to load. SHOULD NOT be a member of
          SpecialBuffer, use GetMessages if you want messages. Only works on
          real buffers.
    Returns:
      The buffer lines.
    """
    if number not in self._cache:
      if number is None:
        buf = self.nvim.current.buffer
      else:
        for b in self.nvim.buffers:
          if b.number == number:
            buf = b
            break

      self._cache[number] = list(buf)
    return self._cache[number]

  def GetCurrentLine(self):
    """Figures out what line the cursor is on.

    Returns:
      The cursor's line.
    """
    if 'line' not in self._cache:
      lineno = self.nvim.current.window.cursor[0]
      self._cache['line'] = int(lineno)
    return self._cache['line']

  def Kill(self):
    """Kills the Neovim process and removes the socket"""
    VimCommunicator.Kill(self)

    if os.path.exists(self._listen_addr):
      os.remove(self._listen_addr)


class InvocationError(Exception):
  """Raised when there's a problem starting or interacting with neovim instance.
  """
  is_fatal = True

