# Who decides the list

Every control in this lab sits downstream of one assumption that nobody states out loud: **the list
of things the model may call was fixed before anybody reviewed anything.**

It is a reasonable assumption here, and you can check it rather than take it. Seven operations,
generated from the running code, committed to the repository, compared on every export against a
literal set of approved names. Five tool modules, mounted by `create_app` alongside one router that
is deliberately not a tool. The list is decided when the process starts, from code that was already
in the image, by whoever last merged a pull request.

Now connect a tool server.
