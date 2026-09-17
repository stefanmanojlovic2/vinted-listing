---
name: vinted-listing
description: Writes Vinted listings from photos of clothes — groups the photos into items, then fills in the title, description, hashtags and every field the Sell form asks for. Use whenever someone wants a pile of clothing photos sorted, organised or named, or Vinted listings created, written or rewritten — including loose phrasings like "sort these out", "create my listings", "let's go", "do these" or "next".
---

# Vinted listings

> Groups the photos in `inbox/` into named items, then writes them, one or many, in `listings.json`.
> Short, chill copy: only what a buyer needs, plus an optional closing line with personality.
> The style (title, description format, tone, length) comes from TASTE.md; this file is the mechanics.
> Run every command from the folder that holds `listings.json` (your clone of this repo), and use
> that folder for every path here. If your shell resets its directory between calls, use absolute paths.

## What they're asking for

Read the intent, not the words. Nobody types a command; they say what they want done with the pile.

| They say something like | Do this |
|---|---|
| "organise these", "sort my photos", "I've dumped some photos in" | Step 2, then stop and report |
| "create my listings", "let's go", "do these", "write these up" | Step 2, then Step 3 — straight through |
| "next", "keep going", "more", "carry on", "do the rest" | Step 3 on the next batch |
| "do 012", "the blue jumper", "that Kappa one" | Step 3 on those items |
| "rewrite 012", "redo that one", "that doesn't sound like me" | Step 3, rewriting those items |

**Never make them ask twice.** If they want listings and the photos aren't grouped yet, run Step 2,
get the groups OK'd, then carry straight on into Step 3 without being asked again. The OK on the
groups is the only stop, and it is there because the next thing that happens is files moving on disk.

Photos in `inbox/` that no item claims, and nothing else asked for: say how many in one line and
start Step 2. Anything genuinely ambiguous: ask in one line, not a menu.

**When a command fails.** Any script that exits nonzero: stop, show its numbered problems as they
came out, fix what is yours to fix (`listings.json`), and run it again. Never delete a photo to
resolve a duplicate — show both paths and ask which to keep.

**Missing dependencies are yours to install, not the user's.** A script that exits saying Pillow or
pillow-heif is missing prints the command to fix it: run that command, then run the script again.
Say what you installed in one line; don't stop and ask. If pip refuses with
`externally-managed-environment`, install into a virtualenv or use `pipx`, and if that fails too,
then tell the user what is blocked.

## Step 1 — Taste check

Every session, before writing anything. Open [TASTE.md](TASTE.md): how listings sound, what never
goes in.

1. Look under its title for a `Confirmed-by: <name> (<date>)` line. If it's there, load the file and
   go on to Step 2.
2. No such line (TASTE.md ships without one): ask the questions under "Defaults" one at a time.
3. Write the answers into that table, then add `Confirmed-by: <user's name> (<date>)` under the title.

**User rules win and stick.** When they reject a closing line or state a rule mid-run ("no
cigarettes", "never say vintage"), follow it for the rest of the session and write it into TASTE.md
straight away: rejected lines with the reason under "Rejected, and why", lines they keep under
"Approved", rules under "Never in a description". Those lists ship empty and are the only way the
skill learns their voice, so never leave a reaction unwritten.

Step 1 runs even when Step 2 is skipped.

## Step 2 — Group photos into items

Whenever `inbox/` holds photos no item claims. This is also where each item gets its name.

1. Preview every photo in `inbox/`, in one call:
   ```bash
   python3 scripts/preview.py 500 $(find inbox -type f \( -iname '*.heic' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) | sort)
   ```
2. Read the previews it printed, in filename order (phones number photos as they're shot), at most
   12 per tool call.
3. Match the shots of each garment by colour, fabric, print and label — shots of one item are often
   taken rounds apart, flat lays first and labels later, so never group by position in the roll.
   - Not sure where a photo belongs (blurry, blank, a different garment, not clothes)? Leave it out
     of every item; `organise` puts it in `items/_unsorted/` for the user to check.
   - A photo that belongs to an item already in `listings.json` (a forgotten label shot): append it
     to that item's `source_photos` rather than making a new item.
   - Videos are ignored by every script. Don't list them; don't report them as missing photos.
4. Name each item: `id` is one higher than the highest `id` in `listings.json`, zero-padded to three
   digits, as a quoted string. Never reuse an id, even if its item was deleted. `slug` says what it
   is, from brand, type, colour or model: lowercase, dashes, max 40 characters
   (`levis-501-jeans`, `wool-coat-camel`).
5. Order each item's photos for upload: a worn shot first if there is one, then the flat lay, then
   details and flaws, then the label shots, marked `:label`. A slot with no shot is skipped; a slot
   with several keeps the clearest first.
6. Show the groups before changing anything, one line per item, then the photos left out:
   `001 levis-501-jeans: IMG_0001, IMG_0004, IMG_0005, IMG_0007:label`
   `Unsorted: IMG_0008 (blurry)`
   Say so here if an item has no label shot — the user may want to go and shoot one.
   Wait for OK or corrections.
7. On OK, add the new items to `listings.json` (see Reference — listings.json).
8. Run `python3 scripts/vinted.py organise`. It moves the photos, then renders and checks by itself,
   so don't run `render` or `check` again after it.
9. Report in at most 3 lines: items made, photos placed, photos in `items/_unsorted/`.

Fixing a group later works the same way: edit `source_photos` and run `organise` again. Every file
keeps its original photo name at the end of its name, so photos never get mixed up.

## Step 3 — Write listings

1. Read `listings.json`. Pick the items, in id order, from what they meant:
   - They named items, by id or by description ("012", "the blue jumper"): those.
   - They asked to carry on, or asked for nothing in particular: the first 5 whose `title` is empty.
   - They gave a number ("do three more"): that many, capped at 5.
   - They asked for the lot ("do the rest", "all of them"): the first 5 whose `title` is empty.

   Never more than 5 in one batch: each item is 4–8 photos to look at properly, and past that flaws
   in the photos start getting missed. **On the first batch after a fresh TASTE.md, write 3, not 5** —
   the voice is untrained and the point of a small batch is that they reject what doesn't sound like
   them. Write a batch, report it, and wait. Never roll straight into the next batch unasked.
2. Preview the item's photos, in one call:
   `python3 scripts/preview.py 900 <the paths in the item's images>`.
3. Read every preview it printed: the flat lay, each detail or flaw shot, and the label shot
   (`-label` in the filename).
4. Fill the fields in Reference — Fields. Keep what the label says in `size_label`, put Vinted's size
   in `size`.
5. Set `status` to `written`, but only if it is currently `draft`. `title` and `description` are the
   only protected fields: never overwrite a non-empty one unless they asked for that item again
   ("rewrite 012"). Every other field except `id`, `slug`, `folder`, `images`, `source_photos` and
   `vinted_url` is rewritten from the photos each time.
6. Run `python3 scripts/vinted.py check`. If it exits nonzero, fix what it lists and run it again
   before going on.
7. Run `python3 scripts/vinted.py render`.
8. Report in at most 5 lines: which ids were written, then "Next: open listings.md, Cmd+F <id>".

## Reference — Fields

Style comes from TASTE.md. These are only the rules Vinted's Sell form needs.

- `title`: the item, written the way TASTE.md says. Vinted's limit is 100 characters.
- `description`: TASTE.md's format and length, nothing from its "Never in a description" list.
  Always name every visible flaw (holes, marks, pilling, fading) and where it is; say "no visible
  flaws" only after checking every photo. Keep an existing closing line when rewriting, unless the
  user rejected it — then write a new one and log the old one under "Rejected, and why".
- `hashtags`: optional, 3–7 lowercase search words (brand, type, colour), no `#`.
- `category`: the Vinted leaf name (see vocab). `brand`: as on the label, "Unbranded" if none.
- `size`: Vinted's size, with the label's wording in `size_label`. Jeans: `W34 L30`. Labels that
  give a collar in cm (men's shirts): 38 = S, 39/40 = M, 41/42 = L, 43/44 = XL, 45/46 = XXL.
  No size on the label: ask, don't guess.
- `condition`: New with tags (tags still on) · New without tags (never worn, no tags) · Very good
  (worn, no wear visible in the photos) · Good (light wear, named in the description) · Satisfactory
  (obvious wear, or a flaw that has to be called out).
- `colours` (max 2), `material`, `parcel_size`: from the vocab below.

There is no price field. Vinted shows comparable sold prices in the Sell form, so the price is set
there when the listing is pasted in.

## Reference — Vinted vocab

`condition` and `parcel_size` are stored in **English, exactly as listed here** — `check` rejects
anything else. Pick the matching option on the Sell form in your own language when you paste.
`category`, `colours` and `material` are free text: use your Sell form's own names.

- Condition: New with tags · New without tags · Very good · Good · Satisfactory
- Colours: Black, White, Grey, Beige, Cream, Brown, Khaki, Navy, Blue, Light blue, Turquoise,
  Green, Dark green, Mint, Yellow, Mustard, Orange, Red, Burgundy, Pink, Rose, Purple, Lilac,
  Silver, Gold, Multi
- Material: Cotton, Polyester, Wool, Linen, Denim, Leather, Silk, Viscose, Nylon, Acrylic,
  Cashmere, Elastane, Fleece, Corduroy
- Parcel: Small (large envelope: tees, shirts, light knits) · Medium (shoebox: jeans, heavy
  knits, light jackets) · Large (moving box: coats, boots)
- Category leaves, menswear as the example: Plain t-shirts, Printed t-shirts, Striped t-shirts, Long-sleeved
  t-shirts, Polo shirts, Vests; Plain shirts, Checked shirts, Striped shirts, Denim shirts,
  Short-sleeved shirts; Crew neck jumpers, V-neck jumpers, Turtleneck jumpers, Cardigans,
  Hoodies, Sweatshirts; Straight fit jeans, Slim fit jeans, Skinny jeans, Ripped jeans,
  Wide-leg jeans; Chinos, Cargo trousers, Wide-leg trousers, Joggers, Shorts, Swim shorts;
  Bomber jackets, Denim jackets, Leather jackets, Overshirts, Coats.
  Selling womenswear, or another Vinted country: copy that Sell form's leaf names into this list
  on the first run, replacing these.

## Reference — listings.json

A JSON array at the repo root, one object per item. It doesn't exist on a fresh clone: create it
containing `[]` and add to that array. A new item needs only these three keys — `organise` fills in
the rest:

```json
{
  "id": "003",
  "slug": "levis-501-jeans",
  "source_photos": ["IMG_0001", "IMG_0004", "IMG_0007:label"]
}
```

`id` is a **quoted** three-digit string. Each `source_photos` entry is the filename **without its
extension**, exactly as the phone wrote it (`IMG_2520`, `PXL_20240115_143022`), with `:label`
appended on the label shots. A full worked item is in [examples/listings.example.json](examples/listings.example.json).

**Statuses:** `draft` → `written` (you set this, once every field is filled) → `listed` (posted;
put the link in `vinted_url`) → `sold`. Once an item is `listed` or `sold`, its photos may already
be deleted.
