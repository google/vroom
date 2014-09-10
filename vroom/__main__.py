"""The vroom test runner."""
import os
import signal
import subprocess
import sys

import vroom.args
import vroom.color
import vroom.output
import vroom.runner
import vroom.vim


def main(argv=None):
  if argv is None:
    argv = sys.argv

  try:
    args = vroom.args.Parse(argv[1:])
  except ValueError as e:
    sys.stderr.write('%s\n' % ', '.join(e.args))
    return 1

  if args.murder:
    try:
      output = subprocess.check_output(['ps', '-A']).decode('utf-8')
    except subprocess.CalledProcessError:
      sys.stdout.write("Can't find running processes.\n")
      return 1
    for line in output.splitlines():
      if line.endswith('vroom'):
        pid = int(line.split(None, 1)[0])
        # ARE YOU SUICIDAL?!
        if pid != os.getpid():
          sys.stdout.write('Killing a vroom: %s\n' % line)
          os.kill(pid, signal.SIGKILL)
          break
    else:
      sys.stdout.write('No running vrooms found.\n')
      return 0
    end = 'VroomEnd()'
    kill = ['vim', '--servername', args.servername, '--remote-expr', end]
    sys.stdout.write("I hope you're happy.\n")
    return subprocess.call(kill)

  dirty = False
  writers = []
  try:
    for filename in args.filenames:
      with open(filename) as f:
        runner = vroom.runner.Vroom(filename, args)
        writers.append(runner(f))
        if runner.dirty:
          dirty = True
  except vroom.vim.ServerQuit as e:
    # If the vim server process fails, the details are probably on stderr, so hope
    # for the best and exit without shell reset.
    sys.stderr.write('Exception: {}\n'.format(e))
    return 2

  if dirty:
    # Running vim in a process can screw with shell line endings. Reset terminal.
    subprocess.call(['reset'])

  for writer in writers:
    writer.Write()

  vroom.output.WriteBackmatter(writers, args)

  failed_tests = [w for w in writers if w.Status() != vroom.output.STATUS.PASS]
  if failed_tests:
    return 3


if __name__ == '__main__':
  sys.exit(main())
