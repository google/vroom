"""A vroom test execution environment.

This is an object with all of the vroom verifiers asked. Good for one file.
"""
import vroom.buffer
import vroom.messages
import vroom.output
import vroom.shell
import vroom.vim


class Environment(object):
  """The environment object.

  Sets up all the verifiers and managers and communicators you'll ever need.
  """

  def __init__(self, filename, args):
    self.args = args
    self.message_strictness = args.message_strictness
    self.system_strictness = args.system_strictness
    self.filename = filename
    self.writer = vroom.output.Writer(filename, args)
    self.shell = vroom.shell.Communicator(filename, self, self.writer)
    if args.neovim:
        import vroom.neovim_mod as neovim_mod
        self.vim = neovim_mod.Communicator(args, self.shell.env, self.writer)
    else:
        self.vim = vroom.vim.Communicator(args, self.shell.env, self.writer)
    self.buffer = vroom.buffer.Manager(self.vim)
    self.messenger = vroom.messages.Messenger(self.vim, self, self.writer)
