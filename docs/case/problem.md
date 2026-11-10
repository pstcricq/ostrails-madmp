# The problem

Data Management Plans have been mandatory for years, and machine-actionable DMPs have had a common standard since 2019. What is still missing in practice is a way to produce one without hand-building three artifacts and then keeping them in agreement forever.

## Three artifacts saying the same thing

A working maDMP setup needs three things, and each is usually built by hand.

1. **A questionnaire.** In a DMP platform such as the Data Stewardship Wizard (DSW), a Knowledge Model: chapters, questions, answers, controlled vocabularies, normally assembled question by question in the web interface.
2. **A document template.** What turns a researcher's answers into a maDMP. In DSW, a Jinja template written by hand, every expression of which references a question by its identifier.
3. **A validator.** Whatever decides whether a produced DMP is any good, usually a separate script written against the standard rather than against the questionnaire.

All three encode the same knowledge: which fields exist, which are required, which carry a closed vocabulary. Nothing forces them to agree.

## What goes wrong

Nothing crashes, and that is the difficulty.

- A question is renamed in the Knowledge Model. The template still references the old identifier, and the rendered DMP silently loses a field.
- An institutional profile makes a field required. The validator is updated, the questionnaire is not, and every DMP fails a check for a question nobody was asked.
- A controlled vocabulary gains a value. Three artifacts have to learn about it. Two do.
- A vocabulary label contains an apostrophe. In a hand-written Jinja template that is a syntax error inside a string literal, found at render time, in front of a researcher.

Each is a small mistake. They are expensive because they are found late, by the wrong person, and because avoiding them is a permanent effort: every change to every standard means checking three places.

## A plan written once, describing nothing that happened

A DMP is usually written at proposal time, in general terms, and never updated.

For an observing infrastructure this is plain to see. A glider mission is planned once, but each deployment has its own dates, platform, instrument settings and resulting datasets. One document cannot describe all of them honestly, and nobody will write one per deployment by hand.

## No record of what a plan was judged by

Standards have versions. A verdict recorded today means nothing in two years unless it also records which version of which rules produced it.

Most setups keep the DMP in a platform's database, the rules in a script or in someone's head, and the verdict in a report. None of the three points at the others.

## What this case proposes

- **One declarative rule set**, and the three artifacts derived from it mechanically, so that a disagreement between them is not unlikely but impossible. See [The principle](principle.md).
- **A template DMP and its productions.** The maDMP produced from the questionnaire is the project's template DMP, versioned as it evolves; each deployment is a production DMP filled from one of its versions, versioned in turn. See [DMP database](../guide/database.md).
- **A store that remembers what judged what.** Every version is kept beside its assessment, the project version it came from and the rules that project version pins, never overwritten, behind an [API](../guide/api.md) that refuses a document that does not hold up.
