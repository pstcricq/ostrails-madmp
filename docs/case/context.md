# Context

The rules-driven engine described in this site is one component of a pilot that started before it and reaches further than it. This page says where the work comes from, what already existed around it, and where it goes.

## Where the work comes from

**CORIS.** The Coastal Ocean Resource Infrastructure System is a UN Ocean Decade endorsed initiative led by SOCIB. It aims at a digital platform for discovering, accessing and assessing coastal ocean data together with the digital research objects around them, and at a collaborative environment for services within the CoastPredict framework.

**JERICO.** JERICO-S3 and JERICO-DS laid the foundations of a digital ecosystem for the Joint European Research Infrastructure of Coastal Observatories, so that datasets, metadata, software, standards, best practices and Virtual Research Environments can be reached from one place. The JERICO Coastal Ocean Resource Environment, CORE, began as a prototype of that ecosystem and is becoming the long term infrastructure of JERICO-RI.

**Blue-Cloud.** The JERICO-CORE Virtual Research Environment is supported jointly by JERICO and Blue-Cloud, on the D4Science infrastructure. Within it, SOCIB has developed services that record the digital assets taking part in data workflows and check whether datasets exist as their Data Management Plan said they would.

**IDEMar.** SOCIB has been writing Data Management Plans since 2021 to document and coordinate its digital platforms. They began as ordinary documents and became, through IDEMar, reusable templates promoting harmonised practices at national level.

That trajectory produced the problem this pilot addresses. Templates harmonise what people write, and do nothing about what happens next: whether the described data flow ran, whether the datasets exist, whether their metadata are FAIR. Answering that needs descriptions a machine can read.

**OSTrails** takes this on along three dimensions: machine-actionable DMPs that evolve through the research lifecycle, Scientific Knowledge Graphs that make the relations between research outputs explicit, and interoperable ways of assessing FAIRness. Together they form the **Plan, Track, Assess** lifecycle the [D4.3 page](../project/d4-3.md) maps this case onto. The project brings together 41 partners from 17 countries, the five EOSC Science Clusters among them, and is funded by Horizon Europe.

## The SOCIB pilot

[SOCIB](https://www.socib.es), the Balearic Islands Coastal Observing and Forecasting System, is a multi-platform facility based in Palma: it operates ocean gliders, a research vessel, fixed and Lagrangian platforms, HF radar, beach monitoring and ocean forecasting models, and serves their data. It contributes the ENVRI/JERICO thematic pilot, which demonstrates these concepts inside an operational coastal observing infrastructure.

The use case is glider observations on the Canales endurance line. Running for more than a decade, it produces a rich set of interconnected digital objects: datasets, metadata records, software, workflows, publications and documentation. It was chosen because that history makes it well understood, not because it is simple.

The approach is meant to extend to other SOCIB observing systems, then to the OceanGliders community, and eventually to broader JERICO-RI data flows.

## What already existed around this work

The tools around the engine are the Track and Assess half of the pilot.

- **An earlier maDMP service.** A maDMP was already produced on demand: a service reads SOCIB's data management API, fills a template and returns a plan. The engine replaces that template with a derivation from declarative rules, and leaves the consumers of the plan undisturbed.
- **Three MCP servers**, so that the pilot's information is reachable by tools and agents and not only by people. They expose information drawn from the maDMPs, from the file system and from the THREDDS data server.
- **A quality control of the data.** Written in Python at SOCIB, it assesses datasets and their metadata. It runs outside the maDMP pipeline today and is meant to join the checks a submitted plan faces. It answers a different question from the rules, see [What is next](../project/next.md).
- **An agent and a monitoring interface.** An agent answers questions about the data flow through the institution's chat, and an interface shows, per project, which data are available and which are missing. The aim is to give glider operators a view of the state of their data.

## Already reused, as a proof of concept

In Blue-Cloud2026, SOCIB contributes a federated service drawing on the three OSTrails interoperability frameworks: SKG-IF to represent and link digital objects, maDMP-IF to describe plans and connect them to objects and data flows, and FAIR-IF to assess FAIRness and process compliance. It is hosted at SOCIB and federated into the Blue-Cloud Virtual Research Environment.

**It is a proof of concept, not an operational service implementing the three frameworks.** Its own deliverable makes it available *initially* through the JERICO-CORE Virtual Lab *for testing and validation*, as a *prototype implementation* other Labs could adopt as it matures.

What this site takes from it is an attribution, not a claim: that deliverable records that the service rests on the OSTrails SKG and maDMP data models originally developed for the ENVRI/JERICO thematic pilot, which is the pilot described here. Its first use case checks whether data from JERICO-S3 Transnational Access projects followed their data management plan, starting with glider missions operated by SOCIB.

Reference: Blue-Cloud2026, D5.5, *Blue-Cloud VRE federated infrastructures, 2nd release*, section 2.3.

## Where it goes

OSTrails ends. Its outcomes are folded into CORIS, which has no funding of its own and serves the wider coastal ocean community, so that what the project produced stays available to people who were never part of it. That is the sustainability path for everything here, and the reason this material is written to be read by another pilot and not only by us.
