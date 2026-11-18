"""Native SDK offline tests. Network is replaced with a synthetic adapter."""
import io
import json
import base64
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rich.console import Console
from cli import rialo_cli as cli

try:
    import rialo_cdk as sdk
except ImportError:
    sdk = None


@unittest.skipUnless(sdk is not None and getattr(sdk, '__version__', None) == '0.1.0', 'rialo-cdk 0.1.0 not installed')
class NativeSdkTests(unittest.TestCase):
    def test_wallet_sign_and_build_real_transaction_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            args = lambda *v: cli.create_parser().parse_args(['--wallet-dir', tmp, *v])
            with patch.object(cli, 'console', Console(file=output, force_terminal=False)):
                with patch.object(cli.getpass, 'getpass', side_effect=['local-test-password', 'local-test-password']):
                    self.assertEqual(cli.run(args('wallet', 'create'), sdk), 0)
                provider = sdk.FileWalletProvider(tmp)
                wallet = provider.load('default', 'local-test-password')
                pubkey = wallet.get_public_key()
                self.assertIn(wallet.get_public_key_string(), output.getvalue())
                saved = [p for p in Path(tmp).rglob('*') if p.is_file()]
                self.assertTrue(saved, 'SDK did not persist the wallet')
                self.assertTrue(all(b'local-test-password' not in p.read_bytes() for p in saved))
                output.seek(0); output.truncate()
                with patch.object(cli.getpass, 'getpass', return_value='local-test-password'):
                    cli.run(args('sign', 'synthetic message'), sdk)
                signature = sdk.Signature.from_string(output.getvalue().strip())
                self.assertTrue(sdk.verify(pubkey, b'synthetic message', signature))
                self.assertFalse(sdk.verify(pubkey, b'different message', signature))

                class OfflineRpc:
                    submitted = None
                    def __init__(self, url): self.url = url
                    def get_latest_blockhash(self): return sdk.Hash(bytes(32))
                    def send_transaction(self, data):
                        OfflineRpc.submitted = bytes(data)
                        return 'synthetic-signature'

                class SdkProxy:
                    HttpRpcClient = OfflineRpc
                    def __getattr__(self, key): return getattr(sdk, key)

                recipient = sdk.public_key_from_keypair(sdk.generate_keypair())
                with patch.object(cli.getpass, 'getpass', return_value='local-test-password'):
                    self.assertEqual(cli.run(args('--rpc', 'https://synthetic.example', 'send', '--to', str(recipient), '--amount', '1', '--yes'), SdkProxy()), 0)
                self.assertIsInstance(OfflineRpc.submitted, bytes)
                self.assertGreater(len(OfflineRpc.submitted), 64)


    def test_native_http_rpc_against_local_synthetic_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'requests.jsonl'
            server = subprocess.Popen([sys.executable, str(Path(__file__).with_name('fake_rpc_server.py')), str(log)],
                                      stdout=subprocess.PIPE, text=True)
            try:
                port = int(server.stdout.readline().strip())
                provider = sdk.FileWalletProvider(tmp)
                wallet = provider.create('default', 'local-test-password')
                address = wallet.get_public_key_string()
                endpoint = 'http://127.0.0.1:' + str(port)
                args = lambda *v: cli.create_parser().parse_args(['--wallet-dir', tmp, '--rpc', endpoint, *v])
                output = io.StringIO()
                with patch.object(cli, 'console', Console(file=output, force_terminal=False)):
                    self.assertEqual(cli.run(args('balance', '--address', address), sdk), 0)
                    self.assertIn('1.5 RLO', output.getvalue())
                    with patch.object(cli.getpass, 'getpass', return_value='local-test-password'):
                        self.assertEqual(cli.run(args('send', '--to', address, '--amount', '0.1', '--yes'), sdk), 0)
                requests = [json.loads(line) for line in log.read_text().splitlines()]
                self.assertEqual([r['method'] for r in requests], ['getBalance', 'getLatestBlockhash', 'sendTransaction'])
                self.assertEqual(requests[0]['params'][0]['address'], address)
                tx = requests[-1]['params'][0]['transaction']
                self.assertGreater(len(base64.b64decode(tx, validate=True)), 64)
            finally:
                server.terminate(); server.wait(timeout=5); server.stdout.close()


if __name__ == '__main__': unittest.main()
