# Mentor recipes

Recipes for [Mentor](https://github.com/Hnd-VXD/Mentor_OS): an Arch Linux with an assistant that you talk to.

**The site: https://mentor-recipes.netlify.app**
When someone builds something with Mentor that works, their assistant writes down how, in a Markdown file
detailed enough that another Mentor can build the same thing. Those files are collected here and published as a
website.

## What is here

| | |
|---|---|
| `recipes/*.md` | the recipes, one file each, with a few header lines |
| `categories.json` | the categories and what each is for |
| `build_site.py` | builds the website (`dist/`) from the two above; standard-library Python only |
| `inspector.py` | the rules Mentor itself uses to look at a recipe before following it; every recipe's page shows its report |
| `netlify.toml` | how Netlify builds and serves it, with headers that keep any script from running |
| `tools/check_recipes.py` | the check a submission has to pass |

To try it: `python3 build_site.py`, then open `dist/index.html` through any static server.

## Adding a recipe

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: Mentor writes the recipe for you (say "make a recipe of this" after something
worked), you add the header lines, and open a pull request. A submission is checked by the same rules Mentor uses, and a person reads
it before it is published.

## Safety

A recipe is instructions from a stranger, and it asks an assistant to change a computer. So:

- **Nothing here is trusted.** Mentor inspects every recipe itself, whatever this site says, and tells its user everything it would do
  before it changes anything.
- **A recipe with serious findings is not published.**
- **The pages run no script.** A recipe is shown as escaped text; no image, link target or markup from it is ever loaded or executed.
- **Each recipe has a checksum** on its page and in `index.json`, so that the file Mentor gets is the file that was reviewed.

If you find a recipe here that does harm, open an issue or write to the address in the Mentor_OS repository: it is taken down first and
looked at after.

## Licence

The site and its tools are under the [MIT licence](LICENSE). Recipes are shared under CC0 1.0 (public domain) by whoever submits them.
