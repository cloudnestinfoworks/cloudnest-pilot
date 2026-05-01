# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in Cloudnest Pilot, **please do
not open a public issue.** Instead, email us at:

**connect@cloudnestinfoworks.com**

Include:

- A description of the vulnerability
- Steps to reproduce
- Affected versions
- Your assessment of severity
- Any suggested mitigation (optional)

We aim to respond within **3 business days** and to release a fix within
**30 days** for critical issues, **60 days** for medium severity.

## What we consider security issues

- Arbitrary code execution from untrusted input
- Credential exposure (API keys, AWS secrets, kubeconfigs)
- Privilege escalation through the agent's tool system
- Bypass of the user-confirmation gate for destructive tools
- Injection via prompts that cause the agent to take destructive action
  without confirmation
- Cross-site scripting in the web UI
- Server-side request forgery via tool calls

## What we don't consider security issues

- Self-harm via approved commands (you approved them)
- Issues only exploitable with full filesystem access (already game over)
- Cosmetic issues in error messages
- Theoretical attacks without practical exploit
- Issues in dependencies that don't affect Cloudnest Pilot's behavior

## Disclosure policy

We follow **coordinated disclosure**:

1. You report privately
2. We acknowledge within 3 business days
3. We work on a fix
4. We release a patched version
5. We credit you (with your permission) in the release notes
6. After patch release, you may publicly disclose details

## Hall of fame

Security researchers who have helped us:

- *(your name here?)*

## Bounty

We don't currently offer a paid bounty program but we will publicly credit
researchers and provide swag for accepted reports.
