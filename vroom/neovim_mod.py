from vroom.vim import CONFIGFILE, VimscriptString
from vroom.vim import Communicator as VimCommunicator
import subprocess
import time
import neovim
import os
try:
  from StringIO import StringIO
except ImportError:
  from io import StringIO

class Communicator(VimCommunicator):
  """Object to communicate with a Neovim server."""

  def __init__(self, args, env, writer):
    self.writer = writer.commands
    self.args = args
    self.start_command = [
        'nvim',
        '-u', args.vimrc,
        '-c', 'set shell=' + args.shell,
        '-c', 'source %s' % CONFIGFILE]
    env['NVIM_LISTEN_ADDRESS'] = args.servername
    self.env = env
    self._cache = {}

  def Quit(self):
    if not hasattr(self, 'conn'):
      # Never started
      return

    try:
      self.conn.command('qa!')
    except IOError:
      pass

  def Start(self):
    """Starts Neovim"""
    self.process = subprocess.Popen(self.start_command, env=self.env)
    start_time = time.time()
    # Wait at most 5s for the Neovim socket
    while not os.path.exists(self.args.servername) \
            and time.time() - start_time < 5:
        time.sleep(0.01)
    self.conn = neovim.connect(self.args.servername)

  def Communicate(self, command, extra_delay=0):
    """Sends a command to Neovim

    Args:
      command: The command to send.
      extra_delay: Delay in excess of --delay
    Raises:
      Quit: If vim quit unexpectedly.
    """
    self.writer.Log(command)
    parsed_command = self.conn.replace_termcodes(command, True, True, True)
    self.conn.feedkeys(parsed_command, '')
    self._cache = {}
    time.sleep(self.args.delay + extra_delay)

  def Ask(self, expression):
    """Asks vim for the result of an expression.

    Args:
      expression: The expression to ask for.
    Returns:
      Vim's output (as a string).
    Raises:
      Quit: If vim quit unexpectedly.
    """
    return self.conn.eval(expression).decode('utf-8')

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
        buf = self.conn.get_current_buffer()
      else:
        for i in range(len(self.conn.get_buffers())):
          b = self.conn.buffers[i]
          if b.get_number() == number:
            buf = b
            break

      linecount = buf.get_length()
      lines = []
      for i in range(linecount):
        lines.append(buf.get_line(i).decode('utf-8'))
      self._cache[number] = lines
    return self._cache[number]

  def GetCurrentLine(self):
    """Figures out what line the cursor is on.

    Returns:
      The cursor's line.
    """
    if 'line' not in self._cache:
      lineno = self.conn.get_current_window().cursor[0]
      self._cache['line'] = int(lineno)
    return self._cache['line']

  def Kill(self):
    """Kills the Neovim process and removes the socket"""
    VimCommunicator.Kill(self)

    if os.path.exists(self.args.servername):
        os.remove(self.args.servername)
