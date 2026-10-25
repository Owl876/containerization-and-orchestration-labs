# PandaRecovery release 1.2.0

- Report: `5ef23195c8ff438fa4280e306737f287`
- Policy decision: **BLOCKED**
- Scope: readiness review; this report does not deploy or approve a release.

## Mandatory checks (authoritative)

- pipeline: `failed`
- tests: `passed`
- image_scan: `failed`
- staging_smoke: `failed`
- approval: `pending`
- Rollback: MISSING

## Blocking reasons

- pipeline=failed
- image_scan=failed
- staging_smoke=failed
- approval=pending
- rollback plan missing

## AI analysis (advisory)

## Release Review for Pandarecovery 1.2.0

### Changes
- PR-51: Drop legacy jobs.payload column and use payload_v2 (Destructive schema migration; app:1.1.0 still reads payload)
- PR-52: Upgrade worker base image (Critical vulnerability found in image scan)

### Risks
- PR-51: Destructive schema migration
- PR-52: Critical vulnerability

### Checks
- Pipeline: failed
- Tests: passed
- Image Scan: failed
- Staging Smoke: failed
- Approval: pending

### Policy
- All five checks are mandatory: pipeline=passed, tests=passed, image_scan=passed, staging_smoke=passed and approval=approved. A non-empty rollback plan is mandatory.
- For a schema change, explain compatibility with the previous application version.
- For retry changes, mention queue latency and worker saturation during observation.
- If checks fail, name the failed checks and the team action required before re-review.
- Never invent successful checks, metrics, test results or a rollback plan.

### Next Actions
- PR-51 requires a rollback plan to ensure compatibility with app:1.1.0.
- PR-52 requires addressing the critical vulnerability.
- The pipeline, tests, image scan, and staging smoke checks are pending.
- The approval check is pending.


## Evidence obtained through MCP

```json
{
  "get_release": {
    "release_id": "1.2.0",
    "service": "pandarecovery",
    "owner": "platform-team",
    "commit": "9bc3a27",
    "changes": [
      {
        "id": "PR-51",
        "title": "Drop legacy jobs.payload column and use payload_v2",
        "risk": "Destructive schema migration; app:1.1.0 still reads payload"
      },
      {
        "id": "PR-52",
        "title": "Upgrade worker base image",
        "risk": "Critical vulnerability found in image scan"
      }
    ],
    "rollback": ""
  },
  "get_checks": {
    "release_id": "1.2.0",
    "pipeline": "failed",
    "tests": "passed",
    "image_scan": "failed",
    "staging_smoke": "failed",
    "approval": "pending"
  },
  "read_runbook": {
    "service": "pandarecovery",
    "policy": "# PandaRecovery release readiness policy\n\nThis is a read-only readiness review, never a deployment approval or a deploy action.\n\nAll five checks are mandatory: pipeline=passed, tests=passed, image_scan=passed,\nstaging_smoke=passed and approval=approved. A non-empty rollback plan is mandatory.\nA missing field or any other value blocks the release. Unknown releases must fail.\n\nFor a schema change, explain compatibility with the previous application version.\nFor retry changes, mention queue latency and worker saturation during observation.\nIf checks fail, name the failed checks and the team action required before re-review.\nNever invent successful checks, metrics, test results or a rollback plan.\n"
  }
}
```
