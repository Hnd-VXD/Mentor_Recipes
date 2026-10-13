# Adding a recipe

1. **Have Mentor write it.** After something you asked for has worked, tell your assistant "make a recipe of this". It writes a Markdown
   file in `Documents/Mentor recipes` from what it really did, keeps only what ended up working, and keeps your name, keys and
   addresses out. Read it before you share it.
2. **Add the header** at the very top of the file, between two lines of three dashes:

   ```
   ---
   category: desktop
   summary: One sentence in plain words: what the user gets.
   submitted: 2026-10-13
   ---
   ```

   `category` is one of the ids in `categories.json`. If none fits, use `other`; a new category can be proposed in the pull request.
3. **Put the file in `recipes/`**, named for what it does, in lower case with dashes: `clock-with-seconds.md`.
4. **Open a pull request.** It is checked automatically (`tools/check_recipes.py`): a recipe with serious findings fails, and one with
   things to look at is explained in the check's summary. One that passes is published when it is merged; nobody else has to
   read it, and Mentor inspects it again itself before anyone follows it.

## What a good recipe has

Follow the form in Mentor's own instructions (`RECIPES.md` in Mentor_OS): what you get, what to check before starting, numbered steps
with every file in full and every command complete, how to check that it works, how to take it away again, what did not work, and notes
for the agent. Someone who has never seen your conversation must be able to follow it.

## What is not accepted

- Anything that changes sudoers, the polkit rules or Mentor's own files, or switches off the firewall.
- Anything that downloads a program and runs it unseen, or that fetches from an address of numbers, a shortener or a paste site.
- Anything that reads or sends private files, keys, saved logins or browser data.
- Text addressed to the assistant that tells it to skip a warning, a preview or a question.
- Keys, passwords, email addresses, names or other personal things.

By submitting a recipe you agree that it is shared under CC0 1.0 (public domain).
