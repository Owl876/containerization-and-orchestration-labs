# PandaRecovery release readiness policy

This is a read-only readiness review, never a deployment approval or a deploy action.

All five checks are mandatory: pipeline=passed, tests=passed, image_scan=passed,
staging_smoke=passed and approval=approved. A non-empty rollback plan is mandatory.
A missing field or any other value blocks the release. Unknown releases must fail.

For a schema change, explain compatibility with the previous application version.
For retry changes, mention queue latency and worker saturation during observation.
If checks fail, name the failed checks and the team action required before re-review.
Never invent successful checks, metrics, test results or a rollback plan.
