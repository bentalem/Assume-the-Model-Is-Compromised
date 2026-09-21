# Why nothing is armed

## Why this is not an armable control

Every other challenge in this track lets you break something and watch. This one does not, and the
reason is worth stating rather than hiding.

Session-scoped context is not a control at its wrong setting, the way row-level security being
disabled is. It is **a code path that leaks request context between users** — and making it
switchable would mean the API permanently contains that path, one environment variable from being
live, in the repository whose whole argument is that a runtime should not be able to turn its own
authorization off.

So this challenge is a reading exercise, and the thing you are reading is one argument in one
statement that everything else in track 2 depends on.

## What to do

The source panels are in **Stage 03**, below the console. Open the first one and find the argument.
Note two things about the code around it: the context is set with a bound parameter rather than
string-built SQL, and it sits inside an explicit transaction rather than on a bare connection.

Then read the second panel — `V-12` in the environment check — and work out what it actually
proves. In particular, why it asks its final question with no context set at all, and what that
means about the failure it can and cannot see.
