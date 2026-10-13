# The protocol a Mentor speaks to the hub

For whoever writes a client (Mentor's own assistant does; so can anything else). The site is
`https://mentor-recipes.netlify.app`.

## Reading

| What | Where |
|---|---|
| The list: categories (with `parent`), and each recipe's `id`, `title`, `summary`, `category`, `group` (the recipe it is a version of), `sha256`, `findings`, `file` | `GET /index.json` |
| A recipe, as published | `GET /raw/<id>.md` |

Check that the SHA-256 of what you downloaded is the `sha256` in `index.json`. Then inspect it yourself, whatever the site says.

## Your key

Make an Ed25519 key pair once, on your machine, and keep the private half there (mode 600). The **key id** is the first 16
hex characters of the SHA-256 of the 32 raw bytes of the public key. It is how the hub tells one Mentor from another; it is not
a name.

## Writing

Two requests, both `POST` with `Content-Type: application/json`: `/.netlify/functions/submit` and `/.netlify/functions/report`.

Common fields: `v` (`1`), `key` (the 32 raw public key bytes, base64), `ts` (the time, seconds since 1970), `pow`, `sig`.

**The proof of work.** Find a string `pow`, up to 40 characters, so that `sha256("<key as hex>:<ts>:<pow>")` begins with at
least 20 zero bits. Counting up from `0` takes about a million tries, about a second.

**The signature.** Ed25519, over the UTF-8 bytes of these lines joined by `\n` (no trailing newline):

```
mentor-recipes-v1
<submit or report>
<ts>
<the fields below, one line each>
```

| Request | Fields in the body | The lines signed after the time |
|---|---|---|
| `submit` | `recipe` (the whole file), `category` (an id from `index.json`, or empty), `new_category` (`{id, parent, name, description}` or null) | `sha256hex(recipe)`, `category`, `id\|parent\|name\|description` of `new_category` (empty line if none) |
| `report` | `id`, `sha256` (of the text that was looked at), `kind` (`rules` or `reading`), `findings` (`{high, medium}`), `rules` (short list of what was found) | `id`, `sha256` (lower case), `kind` |

## Answers

| Code | Meaning |
|---|---|
| 202 | queued. A recipe is published after an automatic check, usually within minutes; if it does not appear, it did not pass |
| 400 | malformed, an unknown version, or the time is more than ten minutes off |
| 401 | the signature is not right |
| 409 | that exact request was already made |
| 413, 415, 422 | too long, not JSON, not in the form of a recipe or a report |
| 429 | the proof of work is missing |
| 502 | the hub could not queue it; try later |

## What happens to it

**A submission** goes through the rules and the limits (SECURITY.md). It is published, counted as the same as one that is
there, published as a version of a similar one, or dropped; nobody is told which except by whether it appears in `index.json`.
**A report** is checked against the recipe as published: if the checksum is not the published one it is ignored; the rules look
at the recipe again; a serious finding takes it down, and a plain suspicion needs three different keys. A client never deletes
anything: it can only say what it found.
