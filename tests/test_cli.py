import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from cli import rialo_cli as cli


class FakeWallet:
    def get_public_key(self): return 'sender-key'
    def get_public_key_string(self): return 'sender-key'
    def sign_message(self, msg): return 'signed:' + msg.decode()


class FakeProvider:
    wallets = {}
    def __init__(self, directory): self.directory = directory
    def exists(self, name): return name in self.wallets
    def create(self, name, password):
        if not password: raise ValueError('password required')
        self.wallets[name] = FakeWallet()
        return self.wallets[name]
    def load(self, name, password):
        if password != 'password': raise ValueError('wrong password')
        return self.wallets[name]


class FakeKey:
    @classmethod
    def from_string(cls, value):
        if not value or 'invalid' in value: raise ValueError('invalid key')
        return value


class FakeBuilder:
    last = None
    def __init__(self, pubkey, blockhash, timestamp):
        self.blockhash = blockhash
        self.pubkey = pubkey
        self.timestamp = timestamp
        FakeBuilder.last = self
    def add_transfer_instruction(self, sender, recipient, amount):
        self.instruction = (sender, recipient, amount)
    def sign(self, wallet): return b'signed-transaction'


class FakeRpc:
    last = None
    def __init__(self, url): self.url = url; self.submitted = []; FakeRpc.last = self
    def get_latest_blockhash(self): return 'blockhash'
    def get_balance(self, key): self.key = key; return 1500000000
    def send_transaction(self, transaction): self.submitted.append(transaction); return 'signature'


class FakeSdk:
    FILE_STORAGE_AVAILABLE = True
    KELVIN_PER_RLO = 1000000000
    FileWalletProvider = FakeProvider
    PublicKey = FakeKey
    TransactionBuilder = FakeBuilder
    HttpRpcClient = FakeRpc
    @staticmethod
    def get_rpc_url_for_network(network): return 'https://rpc.example.test'


class CliTests(unittest.TestCase):
    def setUp(self):
        FakeProvider.wallets = {'default': FakeWallet()}
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = io.StringIO()
        self.output_patch = patch.object(cli, 'console', Console(file=self.output, force_terminal=False))
        self.output_patch.start()
        self.addCleanup(self.output_patch.stop)

    def args(self, *items):
        return cli.create_parser().parse_args(['--wallet-dir', self.temp.name, *items])

    def test_amount_precision_and_rejections(self):
        self.assertEqual(cli.amount_in_kelvin('1.000000001', 10**9), 1000000001)
        self.assertEqual(cli.amount_in_kelvin('18446744073.709551615', 10**9), 2**64 - 1)
        with self.assertRaises(cli.CliError): cli.amount_in_kelvin('18446744073.709551616', 10**9)
        for invalid in ('0', '-1', 'NaN', 'Infinity', '0.0000000001', '1e999999', 'bad'):
            with self.subTest(invalid=invalid), self.assertRaises(cli.CliError):
                cli.amount_in_kelvin(invalid, 10**9)

    def test_wallet_creation_and_duplicate(self):
        with patch.object(cli.getpass, 'getpass', side_effect=['password', 'password']):
            self.assertEqual(cli.run(self.args('--wallet', 'new', 'wallet', 'create'), FakeSdk), 0)
        self.assertIn('sender-key', self.output.getvalue())
        with self.assertRaises(cli.CliError): cli.run(self.args('wallet', 'create'), FakeSdk)

    def test_sign_and_balance(self):
        with patch.object(cli.getpass, 'getpass', return_value='password'):
            cli.run(self.args('sign', 'hello'), FakeSdk)
        self.assertIn('signed:hello', self.output.getvalue())
        cli.run(self.args('balance', '--address', 'recipient'), FakeSdk)
        self.assertEqual(FakeRpc.last.key, 'recipient')
        self.assertIn('1.5 RLO', self.output.getvalue())

    def test_send_requires_confirmation_and_exact_amount(self):
        with patch('builtins.input', return_value='no'):
            FakeBuilder.last = None
            cli.run(self.args('send', '--to', 'recipient', '--amount', '1.25'), FakeSdk)
            self.assertIsNone(FakeBuilder.last)
        with patch.object(cli.getpass, 'getpass', return_value='password'):
            cli.run(self.args('send', '--to', 'recipient', '--amount', '1.25', '--yes'), FakeSdk)
        self.assertEqual(FakeBuilder.last.instruction, ('sender-key', 'recipient', 1250000000))
        self.assertEqual(FakeBuilder.last.blockhash, 'blockhash')
        self.assertEqual(FakeRpc.last.submitted, [b'signed-transaction'])

    def test_rejects_bad_paths_and_rpc_credentials(self):
        for bad in ('../wallet', '', 'a/b'):
            with self.assertRaises(Exception): cli.wallet_name(bad)
        for bad in ('file:///tmp/rpc', 'https://secret@example.test', 'https://host:bad', 'not-a-url'):
            with self.assertRaises(Exception): cli.rpc_url(bad)

    def test_rpc_secrets_not_printed_but_transport_keeps_url(self):
        private_url = 'https://rpc.example.test/key-value?token=secret'
        cli.run(self.args('--rpc', private_url, 'network'), FakeSdk)
        self.assertIn('rpc.example.test', self.output.getvalue())
        self.assertNotIn('key-value', self.output.getvalue())
        self.assertNotIn('secret', self.output.getvalue())
        cli.run(self.args('--rpc', private_url, 'balance', '--address', 'recipient'), FakeSdk)
        self.assertEqual(FakeRpc.last.url, private_url)

    def test_sdk_absent_returns_actionable_error(self):
        errors = io.StringIO()
        with patch.object(cli, 'load_sdk', side_effect=cli.CliError('SDK not installed')):
            with patch.object(cli, 'error_console', Console(file=errors, force_terminal=False)):
                self.assertEqual(cli.main(['wallet', 'show']), 1)
        self.assertIn('SDK not installed', errors.getvalue())


if __name__ == '__main__': unittest.main()
