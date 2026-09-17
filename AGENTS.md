# Vinted listings

This folder is a Vinted selling workspace built around one skill: [SKILL.md](SKILL.md). The style
is in [TASTE.md](TASTE.md), and how to use it in [README.md](README.md).

- Photos in `inbox/` nothing claims, or they ask you to sort or organise them: SKILL.md, Step 2.
- They want listings — "create my listings", "let's go", "do these", "next", or they name an item:
  SKILL.md, Step 3. If the photos aren't grouped yet, do Step 2 first, get the groups OK'd, then
  carry straight on into Step 3 without being asked again.
- Show the groups and wait for an OK before running `organise`: that is the step that moves files.
- `python3 scripts/vinted.py organise`, `check` and `render`: see README.md.

## Rules

- `listings.json` is the source of truth. `items/` and `listings.md` are generated from it.
- Photos stay on this computer. Never upload them to a web service, a connector, a shared page or a
  repo. Previews go in `$TMPDIR`, never inside this folder.
- Phone photos store the GPS location they were taken at. If photos must go anywhere besides Vinted,
  use the `jpg/` copies from `scripts/heic_to_jpg.py`, which carry no location.
- No bots on Vinted: never use browser automation to fill in Vinted's Sell form or upload. The user
  uploads by hand.
- There is no price field. Vinted recommends a price in the Sell form; the user sets it there.
