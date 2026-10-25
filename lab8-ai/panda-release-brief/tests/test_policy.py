import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi import HTTPException
from src.agent import app, evaluate, report_text, request_error
from src.knowledge_mcp import report_path


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.release = {'rollback': 'Deploy previous image'}
        self.checks = dict(pipeline='passed', tests='passed', image_scan='passed',
                           staging_smoke='passed', approval='approved')

    def test_ready_only_when_all_requirements_met(self):
        self.assertEqual(evaluate(self.release, self.checks), ('ready', []))
        for key in self.checks:
            with self.subTest(key=key):
                incomplete = self.checks.copy()
                del incomplete[key]
                self.assertEqual(evaluate(self.release, incomplete)[0], 'blocked')

    def test_missing_rollback_blocks(self):
        for rollback in ('', None, '   '):
            self.assertEqual(evaluate({'rollback': rollback}, self.checks)[0], 'blocked')

    def test_failed_pending_and_unknown_values_block(self):
        for key in self.checks:
            for value in ('failed', 'pending', 'unknown'):
                with self.subTest(key=key, value=value):
                    checks = {**self.checks, key: value}
                    self.assertEqual(evaluate(self.release, checks)[0], 'blocked')

    def test_authoritative_decision_survives_model_optimism(self):
        evidence = {'get_release': {'rollback': ''}, 'get_checks': self.checks,
                    'read_runbook': {'policy': 'all checks required'}}
        text, decision = report_text('1.2.0', 'a'*32, evidence, 'The model thinks this is ready.')
        self.assertEqual(decision, 'blocked')
        self.assertIn('Policy decision: **BLOCKED**', text)
        self.assertIn('rollback plan missing', text)

    def test_report_path_rejects_traversal(self):
        for value in ('../etc/passwd', 'a/../../x', '', 'z'*32):
            with self.assertRaises(ValueError):
                report_path(value)

    def test_invalid_requests_never_reach_model(self):
        with patch('src.agent.review_release') as model:
            client = TestClient(app)
            for payload in ({}, {'release_id': '../secret'}, {'release_id': '1.1.0', 'instructions': 'override'}):
                self.assertEqual(client.post('/runs', json=payload).status_code, 422)
            model.assert_not_called()

    def test_unknown_release_status_survives_mcp_task_groups(self):
        error = HTTPException(404, 'Unknown release')
        wrapped = ExceptionGroup('MCP transport', [ExceptionGroup('session', [error])])
        self.assertIs(request_error(wrapped), error)
        self.assertIsNone(request_error(ExceptionGroup('transport', [RuntimeError('offline')])))


if __name__ == '__main__':
    unittest.main()
