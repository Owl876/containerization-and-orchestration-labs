# PandaRecovery release 1.1.0

- Report: `b174dc33e62942348860c875e7d70931`
- Policy decision: **READY**
- Scope: readiness review; this report does not deploy or approve a release.

## Mandatory checks (authoritative)

- pipeline: `passed`
- tests: `passed`
- image_scan: `passed`
- staging_smoke: `passed`
- approval: `approved`
- Rollback: Deploy app:1.0.0; the additive index is compatible with both versions.

## Blocking reasons

None.

## AI analysis (advisory)

### Release 1.1.0

#### Changes:
- [ ] Feature A (PR-41)
- [ ] Feature B (PR-42)

#### Risks:
- [ ] Queue processing latency may increase (PR-41)
- [ ] CREATE INDEX CONCURRENTLY is backward compatible (PR-42)

#### Rollback Plan:
- [ ] Deploy app:1.0.0

#### Checks:
- [x] Pipeline=passed
- [x] Tests=passed
- [x] Image scan=passed
- [x] Staging smoke=passed
- [x] Approval=approved

#### Policy Decision:
- [ ] Policy A
- [ ] Policy B

## Evidence obtained through MCP

```json
{
  "get_release": {
    "release_id": "1.1.0",
    "service": "pandarecovery",
    "owner": "platform-team",
    "commit": "7ad8b12",
    "changes": [
      {
        "id": "PR-41",
        "title": "Retry transient worker failures with bounded exponential backoff",
        "risk": "Queue processing latency may increase"
      },
      {
        "id": "PR-42",
        "title": "Add PostgreSQL index on pending recovery jobs",
        "risk": "CREATE INDEX CONCURRENTLY is backward compatible"
      }
    ],
    "rollback": "Deploy app:1.0.0; the additive index is compatible with both versions."
  },
  "get_checks": {
    "release_id": "1.1.0",
    "pipeline": "passed",
    "tests": "passed",
    "image_scan": "passed",
    "staging_smoke": "passed",
    "approval": "approved"
  },
  "read_runbook": {
    "service": "pandarecovery",
    "policy": "# PandaRecovery release readiness policy\n\nThis is a read-only readiness review, never a deployment approval or a deploy action.\n\nAll five checks are mandatory: pipeline=passed, tests=passed, image_scan=passed,\nstaging_smoke=passed and approval=approved. A non-empty rollback plan is mandatory.\nA missing field or any other value blocks the release. Unknown releases must fail.\n\nFor a schema change, explain compatibility with the previous application version.\nFor retry changes, mention queue latency and worker saturation during observation.\nIf checks fail, name the failed checks and the team action required before re-review.\nNever invent successful checks, metrics, test results or a rollback plan.\n"
  }
}
```
