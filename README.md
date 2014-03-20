# Vroom: Launch vim tests

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

## Installation

The easiest way to install vroom is to cd into the vroom directory and run
```sh
python setup.py build && sudo python setup.py install
```

Vim syntax files for vroom can be found [here](https://github.com/google/vim-ft.vroom).

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
