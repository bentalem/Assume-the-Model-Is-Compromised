# A second copy of everything

An agent's history is not a log file somebody might look at. It is a store, and it holds:

- what the user typed — which is often more than they would write anywhere else;
- what every tool returned — fetched **with that user's permissions**, from every system the agent can reach;
- what the model said back.

So a transcript is a copy of a person's access, taken at the moment they used it, kept for as long
as history is kept. Whoever can read it later gets that access without holding it.

## Quality review is a real requirement

Support organisations review conversations. Managers want to see how their team — and now their
agent — handles customers. "Let managers read transcripts" is a reasonable-sounding setting, and it
is the kind that gets turned on in a settings page without anyone treating it as the access-control
change it is.

The question it raises is not whether review is legitimate. It is: **when alice spoke to the agent,
did she know this was the audience?** And: **does bob's reading it mean reading data alice was
allowed to see and he is not?**
