# Security Policy

UnrealEngine_Bridge is an MCP server that bridges Claude Code to Unreal Engine
5.7. Because it can spawn actors, set properties, execute editor Python, and
read the viewport on your behalf, it is a powerful tool that runs against a live
editor. This document explains the trust model it is designed for, how to deploy
it safely, and how to report a security issue.

## Supported Versions

Security fixes land on the `master` branch first. We do not maintain long-lived
release branches; the most reliable way to receive a fix is to track the latest
commit on `master`. Please update before reporting so we can confirm an issue
still reproduces.

| Version / Channel        | Supported          | Notes                                                             |
| ------------------------ | ------------------ | ----------------------------------------------------------------- |
| `master` (latest commit) | :white_check_mark: | Active development. All security fixes land here first.           |
| Latest tagged release    | :white_check_mark: | Receives backported fixes for high-severity issues when feasible. |
| Older releases / forks   | :x:                | Unmaintained. Please upgrade to the latest release or `master`.   |

**Runtime baseline.** The bridge targets **Unreal Engine 5.7** (`EngineVersion`
5.7.0 in both bundled `.uplugin` files) and **Python 3.11 or newer** for the MCP
server and Python bridge. Issues that only reproduce on unsupported engine
versions or older Python runtimes may be closed as out of scope, though the
report is still welcome.

## Trust Model and Scope

UnrealEngine_Bridge is built for a **single trusted operator on a single
machine** — the developer or artist who is also running Claude Code and the
Unreal Editor on the same workstation. It is **not** designed to be a
multi-tenant service, a shared server, or an internet-facing endpoint.

The bridge relies on two local network services:

| Service | Default address | Purpose |
|---|---|---|
| Unreal Remote Control API | `localhost:30010` | Spawn/transform/inspect actors, set properties, execute editor Python |
| ViewportPerception | `localhost:30011` | Viewport capture and scene metadata for AI perception |

**These are localhost services intended to be reachable only from the operator's
own machine.** They are designed around the assumption that anything able to
reach them is already trusted to drive the editor. They do not, by design,
provide authentication, authorization, or isolation suitable for exposure to
other users or untrusted clients.

### The trust boundary

The trust boundary is **your local machine and the user account running the
editor**. Inside that boundary — your own session, your own Claude Code — the
bridge is doing exactly what it is meant to do. Outside that boundary, there is
no intended access path, and providing one is outside the project's threat
model.

Treat `:30010` and `:30011` the same way you would treat a debug console, a
local database with no password, or a development web server bound to
`localhost`: useful and convenient *because* they assume a trusted local
operator, and therefore unsafe to expose more widely.

## Operator Guidance

To stay within the supported trust model:

- **Do not expose `:30010` or `:30011` to untrusted networks.** Keep them bound
  to `localhost` / loopback. Do not bind them to `0.0.0.0`, a LAN address, or a
  public interface, and do not place them behind a port-forward, reverse proxy,
  or tunnel that reaches an untrusted network.
- **Do not forward these ports** through routers, VPNs, SSH tunnels, container
  port mappings, or remote-development bridges unless the far end is equally
  trusted and the link is otherwise secured.
- **Run on a machine you control**, under your own user account, with a host
  firewall that blocks inbound connections to these ports from other hosts.
- **Treat the project content directory and bridge files as trusted input.**
  The bridge reads and writes editor state on the local filesystem; only run it
  against projects and files you trust.
- **Keep perception opt-in.** The ViewportPerception plugin ships **disabled by
  default** (`EnabledByDefault=false`); viewport capture is off until you turn it
  on. Before enabling it, keep `:30011` bound to loopback and behind your own
  access control; enable it only when you intend Claude to see your viewport, and
  disable it again when you are done. Understand what is being captured and where
  it goes before turning it on.
- **Keep secrets out of the repo and out of the editor session.** Do not commit
  API tokens or credentials to the repository or to bridge state files; provide
  them through environment variables or local, untracked configuration, and do
  not paste credentials into a session the bridge can read.
- **Keep dependencies current.** Pull the latest `master` to receive security
  and hardening updates.
- **Treat AI-driven actions as you would your own.** The bridge will faithfully
  carry out instructions to modify your scene, assets, and editor state. Review
  what you ask it to do, and keep your work under version control or backed up.

If you have a use case that genuinely requires remote or multi-operator access,
that is a deployment you must secure yourself (mutual TLS, an authenticating
gateway, network isolation, etc.). Such configurations are unsupported and
fall outside this policy.

## In Scope and Out of Scope

### In scope

We are interested in reports affecting the security of the bridge itself,
including:

- The **MCP server** (`ue_mcp/`) and its tool modules.
- The **Remote Control API wrapper** and the path between the MCP server and the
  editor.
- The **file-based bridge protocol** and the on-disk state files it reads and
  writes.
- The **Unreal Engine plugins** shipped in this repository
  (`Plugins/UEBridge`, `Plugins/ViewportPerception`) and the game module under
  `Source/`.
- **Supply-chain** concerns in our own packaging, dependency declarations, or CI
  configuration (`.github/workflows/`).
- **Secret handling** within the codebase — for example, credentials or tokens
  that should never be committed or logged.

Issues of particular interest include trust-boundary weaknesses (where untrusted
input could cross into command, code, or file-system execution), path traversal
in the file bridge, and insecure shipped defaults.

### Out of scope

The following are generally **not** treated as vulnerabilities in this project:

- **The Unreal Engine Remote Control API itself and engine-level behavior.**
  Remote Control is a powerful developer-facing interface provided by Unreal
  Engine; this bridge is a client of it. Restricting Remote Control is an
  *operator responsibility* (see Operator Guidance). The fact that Remote
  Control can drive the editor is intended, not a flaw in this project.
- **Risks inherent to running an AI agent with editor control.** Letting Claude
  Code spawn actors, execute editor Python, or modify a scene is the explicit
  purpose of this software, within the single-operator trust model described
  above. Reports amounting to "the agent can do what it was authorized to do"
  are out of scope.
- **Behavior that is expected within the trusted-local model** — for example,
  that a locally bound development endpoint is reachable from the same machine.
  Such reports are still welcome, but may be classified as documentation or
  hardening improvements rather than vulnerabilities.
- **Operator misconfiguration or insecure deployment** — for example,
  intentionally binding a localhost service to a public interface, disabling a
  shipped safety default, or running on an untrusted shared host — where the
  shipped defaults were not at fault.
- **Already-public vulnerabilities in third-party dependencies** that have an
  upstream fix; please report those upstream. We do want to hear if we pin a
  known-vulnerable version.
- Vulnerabilities in **Unreal Engine, the operating system, Python, or other
  software** outside this repository.
- Findings that require **physical access, an already-compromised host, or
  already-elevated local privileges** to exploit.
- Reports generated **solely by automated scanners** with no demonstrated,
  exploitable impact.
- Denial of service achievable only through **unrealistic resource exhaustion**
  (for example, volumetric flooding of a loopback service).
- **Social engineering**, spam, or attacks against maintainers' personal
  accounts or infrastructure.

When in doubt, report it. Scope decisions are made during triage, and a
borderline report is welcome.

## Reporting a Vulnerability

If you believe you have found a security vulnerability, please report it
privately. **Do not open a public issue, pull request, or discussion** that
describes the problem.

Preferred channel — **GitHub private security advisory**:

> https://github.com/JosephOIbrahim/UnrealEngine_Bridge/security/advisories/new

This keeps the report confidential between you and the maintainer while it is
being triaged and fixed. You may also contact the maintainer, **Joseph
Ibrahim**, directly through GitHub ([@JosephOIbrahim](https://github.com/JosephOIbrahim)).

Please include, where possible:

- The component and version/commit affected (e.g. a `master` commit hash).
- A clear description of the issue and its impact.
- Steps to reproduce, including configuration and any proof-of-concept.
- Your environment (OS, Python version, Unreal Engine version) where relevant.
- Whether the issue requires access beyond the intended local trust boundary
  (this helps us distinguish a real boundary violation from expected
  single-operator behavior).

### What to expect — disclosure timeline

We aim to follow a coordinated disclosure process:

| Stage | Target |
|---|---|
| Acknowledge your report | Within **3 business days** |
| Initial assessment and triage | Within **10 business days** |
| Status updates while we investigate | At least every **2 weeks** |
| Fix or mitigation for confirmed issues | Targeted within **90 days** of triage, severity permitting |
| Public disclosure / advisory | Coordinated with you, normally after a fix ships |

These are good-faith targets for a small, single-maintainer project, not a
contractual guarantee. We will keep you informed if an issue is complex enough
to need more time, and we are happy to credit reporters who wish to be named —
unless you prefer to remain anonymous.

## Safe Harbor for Researchers

We support good-faith security research and will not pursue or support legal
action against researchers who:

- Make a good-faith effort to comply with this policy.
- Report through the private channel above and give us a reasonable time to
  investigate and remediate before any public disclosure.
- Test **only against systems and accounts you own or are explicitly authorized
  to test** — never against another operator's machine, data, or session.
- Avoid privacy violations, data destruction, service degradation, and any
  disruption to others while testing.
- Do not exfiltrate, retain, or share data beyond the minimum needed to
  demonstrate the issue, and delete any such data after reporting.

If you make a good-faith effort to follow this policy, we will treat your
research as authorized, work with you to understand and resolve the issue
quickly, and recognize your contribution. If legal action is initiated by a
third party against you for activity conducted consistent with this policy, we
will make it known that your actions were authorized.

This safe harbor applies to research within the project's trust model. It does
not authorize attacks against third parties, against infrastructure you do not
control, or activity that violates applicable law.

---

*This project is licensed under the MIT License and provided "as is," without
warranty of any kind. Operators are responsible for deploying it safely within
the trust model described above.*
