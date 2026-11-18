<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:96f15af59cc91bd71b57f40418e0cd37ac93d1dd9ece7f0f162e653a00e8755a -->

# Rialo DevKit

[![Tests](https://github.com/sery2013/Rialo_DevKit/actions/workflows/test.yml/badge.svg)](https://github.com/sery2013/Rialo_DevKit/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Discord](https://img.shields.io/badge/Discord-RialoProtocol-5865F2.svg)](https://discord.gg/RialoProtocol)

A small set of open-source tools for developers exploring Rialo: a Python CLI, an optional playground userscript, and an offline SCALE-inspired simulation. The landing page is in `docs/`.

## What works

- **CLI** (`cli/rialo_cli.py`): create/load an encrypted SDK wallet, sign a message, inspect balance, and build/sign/submit a transfer through the SDK. RPC operations require a real, explicitly configured endpoint. Transferring funds is an actual network action; inspect the destination, amount, and endpoint before confirming.
- **Userscript** (`userscript/rialo-enhanced.user.js`): on `playground.rialo.io`, manually collect recognized visible Rialo transaction links and export them to CSV. It does not access keys or inputs, make background network requests, or keep records across page reloads. It is **not a full wallet transaction history**; it depends on visible `/tx/`, `/transaction/`, or `/transactions/` links and may need updates if the playground changes.
- **SCALE demo** (`examples/scale_demo.py`): a local in-memory state machine demonstrating escrow, submission deadlines, authorization, verdicts and refunds. It does not create a SCALE contract, send A2A messages, issue webcalls, move real tokens or contact Rialo.

## Installation

The CLI package itself uses Python 3.10+ and Rich. Wallet and network commands also need `rialo-cdk==0.1.0`; it is pinned because its `TransactionBuilder` interface differs from 0.1.10. The SDK is an optional extra so that the help and local tests work without native dependencies.

```bash
git clone https://github.com/sery2013/Rialo_DevKit
cd Rialo_DevKit
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .                # CLI package and Rich
pip install -e '.[sdk]'         # SDK, required for wallet and network commands
rialo --help
```

The published `rialo-cdk` 0.1.0 distribution includes a macOS ARM Python 3.14 wheel and a source distribution. Linux source builds require Rust/Cargo, a C compiler and network access to Rust dependencies. Version 0.1.10 currently publishes a macOS ARM Python 3.14 wheel only; this project targets 0.1.0 rather than assuming the newer API is compatible. Actual availability may change; check [PyPI files](https://pypi.org/project/rialo-cdk/0.1.0/#files). Linux/Python 3.14 source build, wallet creation, reload and message signing were verified locally. Testnet RPC, transfer submission and other platforms were not verified.

## CLI quick start

```bash
# Password is requested interactively; wallet files are stored under ~/.rialo-devkit/wallets.
rialo wallet create
rialo wallet show
rialo sign "hello rialo"

# Use the correct RPC endpoint for the intended network.
rialo --network testnet --rpc https://YOUR_TESTNET_RPC balance
rialo --network testnet --rpc https://YOUR_TESTNET_RPC send --to YOUR_PUBLIC_KEY --amount 1.0
```

Replace both examples with values from your environment. SDK 0.1.0 does not configure a testnet or devnet URL by default; obtain an endpoint from the network operator. Global options (`--wallet`, `--wallet-dir`, `--network`, `--rpc`) go **before** the command. The send command asks for confirmation; `--yes` skips it for deliberate automation. The CLI does not print a recovery phrase or implement wallet recovery; back up the encrypted wallet files safely. `rialo-cdk` handles the wallet format and encryption.

## Userscript

1. Install Tampermonkey.
2. Open [`rialo-enhanced.user.js`](https://github.com/sery2013/Rialo_DevKit/raw/main/userscript/rialo-enhanced.user.js) after the repository is published and choose **Install**.
3. Open [Rialo Playground](https://playground.rialo.io/), select **Rialo tools**, then **Scan visible links**. Export or clear the in-memory list when needed.

Only public links visible in the page are considered. URL query strings and fragments are removed. Playground interfaces and route formats can change; authenticated transaction views have not been tested.

## Run the SCALE example

```bash
python examples/scale_demo.py
```

It prints pass, fail and expired-task examples using synthetic balances. No dependencies or wallet required. The flow is inspired by [Rialo's SCALE article](https://www.rialo.io/posts/making-the-agent-economy-simple-and-safe-with-rialo); it is a teaching model, not an implementation of a deployed protocol.

## Tests and CI

```bash
pip install -e .
python -m unittest discover -s tests -v
node --check userscript/rialo-enhanced.user.js
node --test tests/userscript.test.cjs
python examples/scale_demo.py
```

The standard CI matrix runs offline unit tests on Linux. A separate native SDK job builds version 0.1.0 from source and tests local wallet signing and transaction construction against a synthetic local JSON-RPC server. Unit mocks and local tests do not establish live testnet compatibility. No provider credentials are needed.

## GitHub Pages

The standalone landing page is `docs/index.html`. In repository **Settings → Pages**, choose **Deploy from a branch**, branch `main`, folder `/docs`. GitHub must receive the project files before the userscript link works. Pages hosts the landing only; it does not run the Python CLI.

## License

[MIT](LICENSE). The Rialo SDK and third-party dependencies have their own licenses.


<!-- /coderabbit-ai-generated:v1 -->