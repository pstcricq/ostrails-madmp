# What is next

Three lists, and the difference between them is the point: what is in progress, what is designed and waiting on something specific, and what is still being decided.

## In progress

### Assessment, in three layers

| Layer | Question | Evidence | Status |
|---|---|---|---|
| the plan | does the plan say valid things? | the document and the rules it pins | <span class="pill done">done</span> on every write; a failing plan is refused, see [Assessment](../guide/assessment.md) |
| the data | do the data match what the plan promised? | the datasets and their metadata | <span class="pill wip">in progress</span> a Python quality control used at SOCIB, outside the pipeline, to be folded in |
| FAIRness and links | are the described outputs FAIR, do their links hold? | the network | <span class="pill open">open</span> when to check, how often, and what a link unreachable one day means for a verdict |

Only the first can be derived from the rules.

### Production DMPs from a template version

The API takes them, the database versions them. What is missing is the program that takes one deployment's real values (dates, platform, instruments, resulting datasets) and fills a template version into a production DMP. It is what turns Track from "documents are versioned" into "every deployment has its own plan".

### Connecting the plans to a knowledge graph

The OSTrails and RDA models are the foundation of the Scientific Knowledge Graph developed within JERICO and Blue-Cloud, where a maDMP is the entry point to the datasets, software, services and publications it concerns. Two extensions are under way: reaching **external and domain graphs** through the OSTrails SKG Interoperability Framework, and a strategy for **persistent identifiers** across distributed graphs, which decides what a plan's own identifier should be.

### An operational instance

The chain is deployed by CD on a remote cluster. The next step is an instance in service: its own domain and TLS, backups, and the image pulled from the institution's registry.

## Designed, waiting on something specific

**A pre-filled baseline.** A starting DMP derived from an observing facility's instruments, so a researcher starts from something substantial. The mechanism is settled; the content waits on validation by a domain professional.

**A SOCIB application profile.** It would hold only what the institution has of its own, nothing the RDA standard or the OSTrails profile already says.

**Conditional rules.** A field required only when another has a given value. The rules language cannot express it yet.

## Still being decided

**Which tool assesses FAIRness and links.** An existing FAIR assessment tool, or one of ours.

**Publishing selected DMPs.** The database is the versioned store. Which DMPs become public, on which platform and with which identifiers is a separate decision.
