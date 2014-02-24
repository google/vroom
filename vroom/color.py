"""Vroom terminal coloring."""
import subprocess

# Grab the colors from the system.
try:
  BOLD = subprocess.check_output(['tput', 'bold']).decode('utf-8')
  RED = subprocess.check_output(['tput', 'setaf', '1']).decode('utf-8')
  GREEN = subprocess.check_output(['tput', 'setaf', '2']).decode('utf-8')
  YELLOW = subprocess.check_output(['tput', 'setaf', '3']).decode('utf-8')
  BLUE = subprocess.check_output(['tput', 'setaf', '4']).decode('utf-8')
  VIOLET = subprocess.check_output(['tput', 'setaf', '5']).decode('utf-8')
  TEAL = subprocess.check_output(['tput', 'setaf', '6']).decode('utf-8')
  WHITE = subprocess.check_output(['tput', 'setaf', '7']).decode('utf-8')
  BLACK = subprocess.check_output(['tput', 'setaf', '8']).decode('utf-8')
  RESET = subprocess.check_output(['tput', 'sgr0']).decode('utf-8')
except subprocess.CalledProcessError:
  COLORED = False
else:
  COLORED = True


# We keep the unused argument for symmetry with Colored
def Colorless(text, *escapes):  # pylint: disable-msg=unused-argument
  """Idempotent.

  Args:
    text: The text to color.
    *escapes: Ignored.
  Returns:
    text
  """
  return text


def Colored(text, *escapes):
  """Prints terminal color escapes around the text.

  Args:
    text: The text to color.
    *escapes: The terminal colors to print.
  Returns:
    text surrounded by the right escapes.
  """
  if not COLORED:
    return text
  return '%s%s%s' % (''.join(escapes), text, RESET)
