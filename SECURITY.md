# Security policy

## Supported versions

Gnostoa has **No supported release** yet. The current repository is a
pre-release source candidate; no package, image, documentation site or hosted
service is supported for production use.

Security fixes for the source candidate are handled on a best-effort basis.
Once a version is released, this section will identify the supported release
line and security-update policy explicitly.

## Reporting a vulnerability

Do not disclose an unpatched vulnerability, exploit or sensitive reproduction
in a public Issue.

After the repository becomes public, use GitHub **private vulnerability
reporting** when the provider exposes that option. If the private route is not
available, open a minimal GitHub Issue titled `Security contact request` that
contains no exploit details, credentials, private repository data or personal
information. The maintainer will establish a private follow-up channel before
technical details are exchanged.

Include, when safe:

- the affected revision, command or artifact;
- the expected and observed security boundary;
- a minimal reproduction with secrets and private data removed;
- likely impact and prerequisites; and
- whether the report is subject to a disclosure deadline.

There is **No response-time guarantee**, security SLA or bounty program. The
maintainer will acknowledge and investigate credible reports as capacity
allows, preserve reporter attribution when requested, and coordinate public
disclosure only after a remediation or an explicit residual-risk decision.

## Scope and limits

This route covers the Gnostoa source, validation tools, schemas, CI and release
artifacts produced by this repository. Vulnerabilities in third-party
dependencies should also be reported to their upstream maintainers; Gnostoa
will track its affected use separately.

This policy is a reporting route, not a security certification, warranty or
claim that the pre-release source has completed an independent security audit.
