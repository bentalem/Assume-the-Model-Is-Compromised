# Conversation history is a second copy of private data

A transcript contains user messages, assistant replies and tool results. Some tool results may have been fetched using permissions that another user does not have.

The history database stores this copy even after the original request has finished.

By default, users can read their own conversations. In the lab, a setting can also allow managers to read the transcripts of colleagues **in the same organisation** for quality review.

That may be useful for a support team, but it changes who can read sensitive information. A manager who can see a transcript is not automatically allowed to see everything that the original user fetched from other systems.

## Your task

Try reading a colleague's session before and after enabling the quality-review setting. Compare the response and the audit record.

The setting changes **read** access only. The manager cannot add messages to the colleague's conversation. A user in another organisation still cannot read it.

Treat history access like access to any other database that stores private information.
