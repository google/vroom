# Vroom: Launch vim tests

![Vroom](/images/vroom_logo.png?raw=true)

![usage screencast](/images/usage_screencast.gif)

_**Vroom is experimental.** There are still some issues with vim that we
haven't figured out how to work around. We reserve the right to make backwards
incompatible changes in order to address these._

Vroom is for testing vim.

Let's say you're a vimscript author. You want to test your new plugin. You could
find a nice vimscript test suite, but that only lets you test your vimscript
functions. What you really want is a way to specify vim commands — actual input
keys that that the user hits — and then verify vim's output.

Enter vroom.

    This is a vroom test.

      > iHello, world!<ESC>
      Hello, world!

The above vroom test opens vim, sends the keys `iHello, world!<ESC>` and then
verifies that the contents of the current buffer is `Hello, world!`.

Things can get much more complex than this, of course. You need to be able to
check the output of multiple buffers. You need to check what messages your
functions echo. You need to sandbox vim, capture its system commands, and
respond with dummy data. And a few shortcuts would be nice.

Never fear! Vroom has it all. Check the examples for details and more
documentation. examples/basics.vroom is a good place to start.

Run `vroom -h` to learn about vroom's configuration options.

Did you accidentally set off a giant vroom test that's running too fast to halt?
Never fear! Pop open another terminal and `vroom --murder`.
Make sure the `--servername` flag matches with the vroom you're trying to kill.
You may need to run `reset` in the terminal with the murdered vroom.

See the
[Tips and Tricks page](https://github.com/google/vroom/wiki/Tips-and-Tricks)
page for some strategies for getting the most out of vroom.

## Usage

Vroom is invoked from the command-line on `.vroom` files. Here are some
examples of usage:

* Running a single file, native vim runner (must have `+clientserver` enabled):

  ```sh
  vroom myplugin/vroom/somefile.vroom --servername=FOO
  ```

* With native vim, finding files below current directory:

  ```sh
  vroom --crawl --servername=FOO`
  ```

* With neovim (must have installed both neovim and neovim python plugin):

  ```sh
  vroom --crawl --neovim --servername=FOO
  ```

* Without running setup.py and with neovim, assuming curdir=vroom repo root:

  ```sh
  PYTHONPATH=$PWD python3 vroom/__main__.py --neovim --crawl --servername=FOO`
  ```

See `vroom --help` and https://github.com/google/vroom/wiki for more info on
usage.

## Installation

Note that Vroom requires a version of vim built with the `+clientserver`
option (run `vim --version` to check).  See `:help clientserver` for
additional requirements.

If you're on Ubuntu or Debian, you can install
[release packages](https://github.com/google/vroom/releases) from GitHub.

Otherwise, the easiest way to install vroom is to clone the vroom repository
from GitHub, cd into the vroom directory, and run
```sh
python3 setup.py build && sudo python3 setup.py install
```

Vim 7.4.384 and later have built-in syntax support for the vroom filetype. You
can install the standalone
[ft-vroom plugin](https://github.com/google/vim-ft-vroom) for older versions of
vim.

## Vroom cheat sheet

Below is a table of the special symbols and conventions vroom recognizes. See
the files under [examples/](examples/) and in particular
[examples/basics.vroom](examples/basics.vroom) for explanations.

<!-- Note for editors: the code spans below use NO-BREAK SPACE characters to
render literal spaces -->
| Symbol  | Description     | Action          | Example                   | Controls                             |
| ------- | --------------- | --------------- | ------------------------- | ------------------------------------ |
|         | unindented line | comment         | `This is a comment`       |                                      |
| `  > `  | gt leader       | input           | `  > iHello, world!<ESC>` | `(N.Ns)` (delay)                     |
| `  :`   | colon leader    | command         | `  :echomsg 'A message'`  | `(N.Ns)` (delay)                     |
| `  % `  | percent leader  | text            | `  % Sent to buffer`      | `(N.Ns)` (delay)                     |
| `  `    | 2-space indent  | output (buffer) | `  Compared to buffer`    | `(N)` (buf number)                   |
| `  & `  | ampersand       | output          | `  & :LiteralText`        | `(N)` (buf number)                   |
| `  ~ `  | tilde leader    | message         | `  ~ Echo'd!`             | match modes<br>(default: verbatim)   |
| `  \|`  | pipe leader     | continuation    | `  \|…TO A BIGGER HOUSE!` |                                      |
| `  ! `  | bang leader     | system          | `  ! echo From Vim`       | match modes<br>(default: regex)      |
| `  $ `  | dollar leader   | hijack          | `  $ Nope, from vroom`    | output channels<br>(default: stdout) |
| `  @`   | at leader       | directive       | `  @clear`                | varies                               |

Special controls:

  * match modes (for message and system): `(verbatim)`, `(glob)`, `(regex)`
  * output channels (for hijack): `(stdout)`, `(stderr)`, `(status)`, `(command)`

Vroom also supports several built-in directives. See
[examples/directives.vroom](examples/directives.vroom) and
[examples/macros.vroom](examples/macros.vroom) for explanations.

Directives:

  * `@clear` — Clear buffer contents (also triggered by 3 blank vroom lines).
  * `@end` — Ensure buffer matching reached end of buffer lines.
  * `@messages` — Override strictness for unexpected messages.
  * `@system` — Override strictness for unexpected system calls.
  * `@macro` — Define vroom macro.
  * `@endmacro` — End vroom macro and resume normal vroom processing.
  * `@do` — Invoke vroom macro defined with `@macro`.

## Neovim mode

By default, vroom uses vim to execute vroom files. You can instead invoke it
with the `--neovim` flag to execute vroom files inside neovim.

To use it, you need to install the neovim-mode dependencies:

  * Install neovim for your platform according to the directions at
    https://github.com/neovim/neovim/wiki/Installing.
  * Install [neovim/python-client](https://github.com/neovim/python-client):
```sh
sudo pip3 install neovim
```

## Travis CI

You can configure your vim plugin's vroom files to be tested continuously in
[Travis CI](https://travis-ci.org).

Just create a .travis.yml file at the root of your repository. The particulars
may vary for your plugin, but here's an example configuration:

```YAML
language: generic
before_script:
  # Install your desired version of vroom.
  - wget https://github.com/google/vroom/releases/download/v0.12.0/vroom_0.12.0-1_all.deb
  - sudo dpkg -i vroom_0.12.0-1_all.deb
  # Install vim.
  - sudo apt-get install vim-gnome
  # Vroom's vim mode currently requires a running X server.
  - export DISPLAY=:99.0
  - sh -e /etc/init.d/xvfb start
  # If your plugin depends on maktaba, clone maktaba into a sibling directory.
  - git clone https://github.com/google/vim-maktaba.git ../maktaba/
script:
  - vroom --crawl ./vroom/
```

It's also possible to test your plugin against neovim, but the recommended
instructions are still being finalized. Details coming soon.

## Known issues

Vroom uses vim as a server. Unfortunately, we don't yet have a reliable way to
detect when vim has finished processing commands. Vroom currently relies upon
arbitrary delays. As such, tests run more slowly than is necessary. Furthermore,
some lengthy commands in vroom tests require additional arbitrary delays in
order to make the tests pass.

We're still looking for workarounds. (If you, like us, wish vim had a sane
client/server architecture, consider
[supporting](https://www.bountysource.com/fundraisers/539-neovim-first-iteration)
[neovim](https://github.com/neovim/neovim).)
