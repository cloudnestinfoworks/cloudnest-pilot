# Changelog

All notable changes to Cloudnest Pilot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- (placeholder for next release)

## [0.1.0] - 2026-04-29

### Added
- Initial public release
- Conversational agent for OpenShift cluster operations
- Web UI at `localhost:8765` and CLI mode
- Demo mode (`--demo`) that runs without an API key
- Tools:
  - `run_shell` — execute commands with user approval
  - `read_file` — read text files
  - `write_file` — write text files (with approval)
  - `check_aws` — validate AWS prerequisites
  - `list_clusters` — discover installed clusters
  - `get_cluster_status` — check cluster health
- Hard-coded blocklist for dangerous shell patterns
- Audit logging to `~/.cloudnest-pilot/history.log`
- Cross-platform support (Windows, macOS, Linux)
- Pre-flight validation for AWS deployments (credentials, region, Route53,
  EC2 quotas)
- Apache 2.0 license

### Known issues
- Multi-cloud support not yet implemented (AWS only)
- No conversation persistence across sessions
- No team / multi-user features

[Unreleased]: https://github.com/cloudnestinfoworks/cloudnest-pilot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cloudnestinfoworks/cloudnest-pilot/releases/tag/v0.1.0
