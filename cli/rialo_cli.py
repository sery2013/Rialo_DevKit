"""Small, explicit command-line interface around the Rialo Python CDK."""
from __future__ import annotations

import argparse
from decimal import Decimal, DecimalException, localcontext
import getpass
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlparse

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
error_console = Console(stderr=True)


class CliError(Exception):
    """An actionable user-facing error."""


def load_sdk():
    try:
        import rialo_cdk
    except ImportError as exc:
        raise CliError(
            "Rialo SDK is unavailable. Install it with: pip install '.[sdk]'. "
            "Check the available wheel for your Python and platform; see README."
        ) from exc
    if getattr(rialo_cdk, "__version__", None) != "0.1.0":
        raise CliError("This CLI requires rialo-cdk 0.1.0. Install it with: pip install '.[sdk]'.")
    return rialo_cdk


def wallet_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise argparse.ArgumentTypeError("Use 1–64 letters, numbers, underscores or hyphens.")
    return value


def rpc_url(value: str) -> str:
    try:
        url = urlparse(value)
        _ = url.port
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use a valid http(s) RPC URL.") from exc
    if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
        raise argparse.ArgumentTypeError("Use an http(s) URL without embedded credentials.")
    return value


def display_rpc(value: str) -> str:
    """Display the host without disclosing API keys in paths or query strings."""
    parsed = urlparse(value)
    host = parsed.hostname or ''
    if ':' in host:
        host = '[' + host + ']'
    if parsed.port is not None:
        host += ':' + str(parsed.port)
    return f"{parsed.scheme}://{host}" + ('/…' if parsed.path not in ('', '/') or parsed.query or parsed.fragment else '')


def amount_in_kelvin(value: str, units: int) -> int:
    try:
        if len(value) > 100:
            raise CliError("Amount is too long.")
        amount = Decimal(value)
        if not amount.is_finite() or amount <= 0:
            raise CliError("Amount must be positive and finite.")
        with localcontext() as ctx:
            ctx.prec = max(32, len(amount.as_tuple().digits) + len(str(units)) + 2)
            scaled = amount * Decimal(units)
            if scaled != scaled.to_integral_value():
                raise CliError("Amount must contain no fractional kelvin.")
            if scaled > 2**64 - 1:
                raise CliError("Amount is too large.")
            return int(scaled)
    except (DecimalException, ValueError, OverflowError) as exc:
        raise CliError("Enter a valid positive RLO amount.") from exc


def provider_for(sdk, directory: Path):
    if not getattr(sdk, "FILE_STORAGE_AVAILABLE", False):
        raise CliError("This SDK build does not provide encrypted file-wallet storage.")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix":
        directory.chmod(0o700)
    return sdk.FileWalletProvider(str(directory))


def password_for_create() -> str:
    first = getpass.getpass("Wallet password: ")
    if not first:
        raise CliError("A non-empty wallet password is required.")
    if first != getpass.getpass("Confirm password: "):
        raise CliError("Passwords do not match.")
    return first


def load_wallet(sdk, args):
    provider = provider_for(sdk, args.wallet_dir)
    return provider.load(args.wallet, getpass.getpass("Wallet password: "))


def resolve_rpc(sdk, args):
    try:
        url = args.rpc or sdk.get_rpc_url_for_network(args.network)
    except Exception as exc:
        raise CliError("No RPC URL is configured for this network. Supply --rpc explicitly.") from exc
    if not url:
        raise CliError("The SDK returned no RPC URL. Supply --rpc explicitly.")
    rpc_url(str(url))
    return str(url)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rialo", description="Rialo DevKit — tools for working with the Rialo CDK.")
    parser.add_argument("--version", action="version", version="Rialo DevKit 0.1.0")
    parser.add_argument("--wallet-dir", type=Path, default=Path.home() / ".rialo-devkit" / "wallets", help="Encrypted wallet directory")
    parser.add_argument("--wallet", type=wallet_name, default="default", help="Wallet name (default: default)")
    parser.add_argument("--network", choices=("testnet", "devnet", "localnet"), default="testnet", help="SDK network selector")
    parser.add_argument("--rpc", type=rpc_url, help="Override the SDK network RPC URL")
    commands = parser.add_subparsers(dest="command", required=True)
    wallet = commands.add_parser("wallet", help="Create or inspect an encrypted wallet")
    wallet_commands = wallet.add_subparsers(dest="wallet_command", required=True)
    wallet_commands.add_parser("create", help="Create an encrypted wallet")
    wallet_commands.add_parser("show", help="Show a wallet's public address")
    balance = commands.add_parser("balance", help="Get account balance")
    balance.add_argument("--address", help="Public address (otherwise open the selected wallet)")
    sign = commands.add_parser("sign", help="Sign a UTF-8 message using the selected wallet")
    sign.add_argument("message", help="Message to sign")
    send = commands.add_parser("send", help="Sign and send an RLO transfer")
    send.add_argument("--to", required=True, help="Recipient public address")
    send.add_argument("--amount", required=True, help="Amount in RLO")
    send.add_argument("--yes", action="store_true", help="Confirm without prompting")
    commands.add_parser("network", help="Show configured network and RPC URL")
    return parser


def run(args, sdk) -> int:
    if args.command == "wallet":
        if args.wallet_command == "create":
            provider = provider_for(sdk, args.wallet_dir)
            if provider.exists(args.wallet):
                raise CliError("A wallet with that name already exists.")
            wallet = provider.create(args.wallet, password_for_create())
            console.print(Panel.fit(f"Wallet: {args.wallet}\nPublic key: {wallet.get_public_key_string()}", title="Wallet created", border_style="cyan"))
        else:
            wallet = load_wallet(sdk, args)
            console.print(wallet.get_public_key_string(), markup=False, soft_wrap=True)
        return 0
    if args.command == "sign":
        wallet = load_wallet(sdk, args)
        signature = wallet.sign_message(args.message.encode("utf-8"))
        console.print(str(signature), markup=False, soft_wrap=True)
        return 0
    if args.command == "network":
        url = resolve_rpc(sdk, args)
        table = Table(title="Rialo network", show_header=False)
        table.add_row("Network", args.network)
        table.add_row("RPC", display_rpc(url))
        console.print(table)
        return 0
    if args.command == "balance":
        key = sdk.PublicKey.from_string(args.address) if args.address else load_wallet(sdk, args).get_public_key()
        kelvin = sdk.HttpRpcClient(resolve_rpc(sdk, args)).get_balance(key)
        units = int(sdk.KELVIN_PER_RLO)
        console.print(f"Balance: {Decimal(kelvin) / Decimal(units)} RLO ({kelvin} kelvin)")
        return 0
    if args.command == "send":
        kelvin = amount_in_kelvin(args.amount, int(sdk.KELVIN_PER_RLO))
        recipient = sdk.PublicKey.from_string(args.to)
        url = resolve_rpc(sdk, args)
        if not args.yes:
            answer = input(f"Send {args.amount} RLO to {args.to} via {display_rpc(url)}? [y/N] ")
            if answer.strip().lower() not in {"y", "yes"}:
                console.print("Transfer cancelled.")
                return 0
        wallet = load_wallet(sdk, args)
        public_key = wallet.get_public_key()
        client = sdk.HttpRpcClient(url)
        blockhash = client.get_latest_blockhash()
        builder = sdk.TransactionBuilder(public_key, blockhash, int(time.time() * 1000))
        builder.add_transfer_instruction(public_key, recipient, kelvin)
        transaction = builder.sign(wallet)
        signature = client.send_transaction(transaction)
        console.print(f"Submitted transaction: {signature}", markup=False, soft_wrap=True)
        return 0
    raise CliError("Unknown command.")


def main(argv=None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    try:
        return run(args, load_sdk())
    except (CliError, ValueError, OSError) as exc:
        error_console.print(f"Error: {exc}", markup=False)
        return 1
    except KeyboardInterrupt:
        error_console.print("Cancelled.")
        return 130
    except Exception as exc:
        # The SDK supplies its own exception types. Do not dump secrets or arguments.
        error_console.print(f"Rialo SDK error ({type(exc).__name__}). Check your wallet, network and SDK installation.", markup=False)
        return 1


if __name__ == "__main__":
    sys.exit(main())
