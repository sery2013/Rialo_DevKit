import unittest
from datetime import datetime, timedelta, timezone
from examples.scale_demo import Ledger, ScaleError, State, Task


class ScaleTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.ledger = Ledger({'requester': 100, 'worker': 0, 'judge': 0})
        self.task = Task.create(self.ledger, 'requester', 'worker', 'judge', 25,
                                self.now + timedelta(hours=1), self.now)

    def conserved(self):
        self.assertEqual(sum(self.ledger.balances.values()) + self.task.escrow, 100)

    def test_pass_pays_worker_once(self):
        self.conserved()
        self.task.submit('worker', 'result', self.now + timedelta(minutes=1))
        self.task.decide('judge', True)
        self.assertEqual((self.task.state, self.ledger.balance('worker')), (State.PAID, 25))
        self.conserved()
        with self.assertRaises(ScaleError): self.task.decide('judge', True)
        with self.assertRaises(ScaleError): self.task.refund_expired(self.now + timedelta(hours=2))
        self.conserved()

    def test_failed_verdict_refunds_requester(self):
        self.task.submit('worker', 'result', self.now)
        self.task.decide('judge', False)
        self.assertEqual((self.task.state, self.ledger.balance('requester')), (State.REFUNDED, 100))
        self.conserved()

    def test_deadline_and_authorization(self):
        with self.assertRaises(ScaleError): self.task.submit('other', 'result', self.now)
        with self.assertRaises(ScaleError): self.task.refund_expired(self.now)
        with self.assertRaises(ScaleError): self.task.submit('worker', 'result', self.task.deadline)
        self.task.refund_expired(self.task.deadline)
        self.assertEqual(self.ledger.balance('requester'), 100)
        with self.assertRaises(ScaleError): self.task.submit('worker', 'result', self.now)
        self.conserved()

    def test_judge_permissions_and_no_timeout_after_submission(self):
        self.task.submit('worker', 'result', self.now)
        with self.assertRaises(ScaleError): self.task.decide('worker', True)
        with self.assertRaises(ScaleError): self.task.refund_expired(self.task.deadline)
        with self.assertRaises(ScaleError): self.task.decide('judge', 1)
        self.task.decide('judge', True)
        self.conserved()

    def test_creation_failure_keeps_balance(self):
        for amount in (0, -1, 1.5, True, 101):
            with self.assertRaises(ScaleError):
                Task.create(self.ledger, 'requester', 'worker', 'judge', amount,
                            self.task.deadline, self.now)
        self.assertEqual(self.ledger.balance('requester'), 75)
        with self.assertRaises(ScaleError): self.ledger.debit('requester', -1)
        with self.assertRaises(ScaleError): self.ledger.credit('worker', -1)
        with self.assertRaises(ScaleError):
            Task.create(self.ledger, 'requester', 'worker', 'judge', 1,
                        datetime(2026, 1, 2), self.now)
        self.conserved()


if __name__ == '__main__': unittest.main()
