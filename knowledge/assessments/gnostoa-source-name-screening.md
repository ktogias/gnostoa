---
type: Source
title: Gnostoa source-publication name-risk screening
description: Owner-confirmed, bounded screening of the Gnostoa working identity for first source-repository visibility in Greece and the European Union.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-15T20:22:43+03:00"
verified:
  by: human:ktogias
  at: "2026-08-15T20:22:43+03:00"
sources:
  - id: publication-baseline-work-item
    resource: https://github.com/ktogias/gnostoa/issues/1
    title: Prepare the Gnostoa publication baseline
  - id: obi-trade-mark-availability
    resource: https://www.obi.gr/emporika-simata/diadikasia-katochyrosis-simatos/elegchos-diathesimotitas-simaton/
    title: OBI trade-mark availability guidance
  - id: tmview
    resource: https://www.tmdn.org/tmview/
    title: TMview
  - id: wipo-global-brand-database
    resource: https://www.wipo.int/en/web/global-brand-database
    title: WIPO Global Brand Database
  - id: jotson-madrid-record
    resource: https://www3.wipo.int/madrid/monitor/en/showData.jsp?ID=ROM.1839073
    title: JOTSON international registration 1839073
  - id: neotoa-french-record
    resource: https://data.inpi.fr/marques/FR5084470
    title: NEOTOA French record FR5084470
x-project-knowledge:
  id: kit.assessment.gnostoa-source-name-screening
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0009-adopt-gnostoa-project-name.md
    - kind: references
      target: /project/gnostoa.md
    - kind: references
      target: /assessments/first-publication-provider-audit.md
---

# Gnostoa source-publication name-risk screening

## Result and owner disposition

The accountable owner records a source-only `CONDITIONAL GO` for the working
identity `Gnostoa` after manually submitting and confirming the official
database searches described below. No material conflict was found in this
bounded screening.

The owner selected this exact semantic control on 2026-08-15:

```text
accept-source-name-conditional-go: GNOSTOA/SOURCE-PUBLICATION/2026-08-15
  a7848a000d2618919cf6a247da64f9464bedf1474216bfdaa942e35910fc73ec
```

The digest identifies the complete reviewed screening worksheet. This record
is its durable, repository-native projection. The projection preserves the
approved result, scope, queries, findings, evidence digests, residual risks and
escalation triggers; it introduces no broader permission.

The disposition closes Decision 0009's name-risk gate only for first
source-repository visibility. It is not trade-mark clearance, a registrability
opinion or authorization for a visibility change, merge, release, package,
OCI image, public site, trade-mark filing, paid service or other commercial
reliance.

## Fixed scope

| Dimension | Bound value |
| --- | --- |
| Name | `Gnostoa` / `GNOSTOA` |
| Territory | Greece and European Union |
| Goods and services | Nice classes 9 and 42 |
| Publication effect | First visibility of the source repository only |
| Source basis | Commit `4a6eb01dde8e6ce19eea595e7cd2ff90d4797073` |
| Search session | 2026-08-15, Europe/Athens (`UTC+03:00`) |

Nice class 41 is outside this source-only scope because no branded training or
educational service is currently offered. It must be screened before such a
service is offered under the name.

## Method and evidence boundary

The owner manually submitted the official-database searches in a shared,
visible browser and confirmed their rendered results. The facilitator prepared
the query forms, inspected only the submitted results, opened plausible primary
records and calculated SHA-256 digests for the captures. WIPO queries were not
automated or scraped.

The durable result is the query, rendered fact and evidence digest recorded
here. Third-party user-interface captures are not part of the public source
tree. Their digests bind the owner-inspected session evidence without implying
permission to redistribute a registry interface.

The first result page was assessed in relevance order and plausible
overlapping records were opened. A finite search cannot prove absence, and
similarity ranking is intentionally broad and noisy. Status, ownership,
territorial effect and goods or services can change.

## Official register screening

### OBI and EUIPO/TMview route

The OBI availability guidance was inspected to confirm the official national,
EU and international search route. Its capture SHA-256 was
`9a7d14db9594964712a8f365908817a1c21de2fc00a5a6d655a38883a572b7e4`.

The TMview query `Contains GNOSTOA` returned `No rows found`. This supplied the
EUIPO/TMview result for EU and participating national-office records, including
the Greek scope. The exact result URL was:

```text
https://www.tmdn.org/tmview/#/tmview/results?page=1&pageSize=30&criteria=C&basicSearch=GNOSTOA
```

The result capture SHA-256 was
`af529cd7a7964a2eb9b1fc5c263117e980940cddf8af443f6d376d3bd10b4a48`.

### WIPO Global Brand Database

| Query | Rendered result and assessment | Capture SHA-256 |
| --- | --- | --- |
| `GNOSTOA`, Embedded, all classes | `No results found!`; no exact or embedded record surfaced | `2f6610b41ec54408b7c75f90cc61b99cbedeafe3fb7e1c93440f3cca5b178fcf` |
| `GNOSTOA`, Fuzzy, all classes | 1,243 results; top result `AOTSON`; no exact result | `6227a137d9d09f4bf4c7cebcc1f6d6c324d62f3528e372350fe48ebff69b592f` |
| `GNOSTOA`, Fuzzy, class 9 | 155 results; top `AOTSON` and `GNOSSOS` class-9 records were ended | `ba5239040ff18f48450ccd6225446e94a5276e625056408b2185d8205c54bd2b` |
| `GNOSTOA`, Fuzzy, class 42 | 112 results; active `JOTSON` required primary-record review | `3176b983d9479468f730dd53d2d15479261aa3750e5a593e0905cf5884ec5642` |
| `GNOSTOA`, Phonetic, all classes | 19,844 broad results; top `NASTOA` records were ended or expired | `4edba949b087454690b6dee9f4d5d8f9c6a4f9df4dc71f3de31a73ef43fa7349` |
| `GNOSTOA`, Phonetic, class 9 | 2,383 results; top `NASTOA` USA application ended in 2023 and Malaysian registration expired in 2023 | `efe6fe38e42adfbcdae0e365cdd3105323057ddecf683b15ed568bb47236580b` |
| `GNOSTOA`, Phonetic, class 42 | 1,837 results; active `NEOTOA` required record review | `80b7a7e610ff20ccf8dd250ac475268cf610c6c9008c55f5309f19b8f0c21c78` |

## Material residuals

### `JOTSON`

WIPO Madrid Monitor showed active international word-mark registration
`1839073`, registered on 2024-12-18 and expiring on 2034-12-18. The primary
record showed designations for Australia, the European Union, the United
Kingdom, New Zealand and the United States, with an EU grant statement dated
2025-07-17. Its classes are 9, 35, 41 and 42. The displayed class-42 services
concern SaaS for tracking energy cost, consumption, carbon emissions, energy
and fuel.

This is the strongest software-related residual because it is active,
EU-designated and includes class-42 software services. It is not an obvious
source-publication blocker: the word and sound differ materially from
`GNOSTOA`, and the identified market is specialised energy-management SaaS
rather than a Git-native project-knowledge toolkit. It remains an explicit
escalation item before stable package, image, site, trade-mark or commercial
branding.

Primary-record capture digests:

- record summary:
  `0eeff4c3b1d4ac35f5f4e5570fd7c188c3c468af2ecc6e2acdb6c313a6e9ed7c`;
- class-42 description:
  `7046a332aa0b0c7900442a85eb99c928dc80ed746d03bb33c3cc174cb4dde55e`;
  and
- EU grant statement:
  `b0b1b964199f1c7aeb09d245340dd3ddb14d446ccf588d468cfd7b26c84e80cf`.

### `NEOTOA`

The French record `FR5084470` was active with an expiry displayed as
2034-09-23. Its classes are 36, 37, 39, 42 and 43. The class-42 description
concerns architectural design, urban planning, structural, technical and
environmental engineering and building research, not software or developer
tooling.

The similar ending and active class-42 coverage make it a retained residual,
but the presentation, sound, territorial basis and architecture or urban-
development market are materially different. It is not an obvious blocker for
the bounded source-only use.

Primary-record capture digests:

- record summary:
  `d998a851a6ac4b52c9f3f6c878f450caff05b3965ae2b739594bcfce315db41c`;
  and
- class-42 description:
  `bded141cdf605149dec12ce50f671ced768af937aba8b0e8ce852411ce6df242`.

## Web and software-registry screening

- GitHub repository-name search returned only the current private
  `ktogias/gnostoa` repository.
- The exact coordinate `gnostoa` returned HTTP 404 from PyPI, npm and the
  Docker Hub official or library route on 2026-08-15.
- crates.io rejected the API request under its data-access policy. Indexed
  search did not surface an exact crate, but this remains inconclusive and is
  not counted as availability evidence.
- Exact indexed-web searches combining `GNOSTOA` with software, developer,
  Greece and European Union terms did not surface relevant third-party
  software use. Visible exact-string hits were linguistic or document-index
  artefacts rather than a competing software identity.

Search indexing is incomplete and cannot exclude unregistered or poorly
indexed use.

## Residual risk and repeat triggers

The accepted residual risk is limited to first source visibility and includes:

- incomplete indexing and register coverage;
- future status, territory, ownership or goods-and-services drift;
- unregistered rights and poorly indexed use;
- `JOTSON`'s active EU-designated class-42 software coverage;
- the broad and noisy phonetic result sets;
- the inconclusive crates.io request; and
- the absence of an independent legal opinion.

Repeat the screening or escalate to independent or qualified professional
review before:

- branded class-41 education or training;
- a stable package, OCI image, domain or public site identity;
- a trade-mark filing;
- paid or commercial services or other material brand reliance;
- a change in name, territory, goods or services; or
- a materially closer active Greek or EU result or other material search drift.

This record changes no repository visibility, branch, Pull Request, Issue,
protection, source integration or artifact-publication state. Those effects
retain their separate gates and authority.
