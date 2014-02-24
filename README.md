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
