# Why it is worse

## Why this one is worse than indirect

Three reasons, and the third is the one people miss.

1. **The author field says the system wrote it.** A reader applying "distrust customer text" as a
   rule applies it correctly and still gets caught, because the rule was about the wrong column.
2. **The trigger is delayed.** The customer who started it is not in the session where it lands,
   is not on the access log for that session, and may have written their message weeks earlier.
3. **The text got promoted without gaining any authority.** It reads as an internal record. It is
   still just a string a customer put in a box. Nothing about the trip made it more trustworthy, and
   nothing about the trip made it more powerful either — which is what the flag is asking you to
   say.

## What to have ready before Stage 03

- The count by author, from the observation rather than from this page.
- Which field tells a later reader that a message was internal, and whether that field survives the
  trip into the model's context.
- Which registered operation could write a row like this one, and which could read it back.
