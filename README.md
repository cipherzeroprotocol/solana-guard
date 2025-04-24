<div align="center">
  <img src="https://via.placeholder.com/200x200?text=SolanaGuard" alt="SolanaGuard Logo" width="200"/>
  <h1>SolanaGuard</h1>
  <p><strong>Unified Blockchain Analysis Platform</strong></p>
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Solana](https://img.shields.io/badge/Solana-Blockchain-14F195)](https://solana.com/)
  [![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
  [![GitHub Issues](https://img.shields.io/github/issues/cipherzeroprotocol/solana-guard)](https://github.com/cipherzeroprotocol/solana-guard/issues)
</div>

---

## 📋 Table of Contents
- [Overview](#-overview)
- [Features](#-features)
- [Project Structure](#️-project-structure)
- [Getting Started](#-getting-started)
- [Analysis Capabilities](#-analysis-capabilities)
- [Usage Examples](#-usage-examples)
- [API Documentation](#-api-documentation)
- [Advanced Configuration](#-advanced-configuration)
- [Contributing](#-contributing)
- [License](#-license)
- [Disclaimer](#️-disclaimer)

## 📝 Overview

SolanaGuard is a comprehensive analysis platform for the Solana blockchain, designed to detect suspicious activities, money laundering patterns, token insider trading, and various attack vectors. It provides analytical tools for both researchers and end-users to understand and identify risks in the Solana ecosystem.

## 🌟 Features

- **Address Analysis** - Analyze wallet addresses for risk factors and suspicious behavior
- **Token Analysis** - Evaluate tokens for rug pull potential and insider trading patterns
- **Money Laundering Detection** - Identify potential money laundering routes and patterns
- **Attack Pattern Detection** - Detect dusting attacks, address poisoning attempts, and other security threats
- **Risk Scoring** - Calculate comprehensive risk scores for addresses and tokens
- **Interactive Dashboards** - Visualize blockchain data through interactive Streamlit dashboards and Dune Analytics queries

## 🛠️ Project Structure

```
solana-guard/
├── data_collection/            # Data gathering scripts
│   ├── collectors/             # API client implementations
│   │   ├── helius_collector.py # Collect data from Helius API
│   │   ├── range_collector.py  # Collect data from Range API
│   │   ├── rugcheck_collector.py # Collect data from RugCheck API
│   │   └── vybe_collector.py   # Collect data from Vybe API
│   ├── config.py               # API credentials and configuration
│   ├── main.py                 # Main collection orchestration
│   └── requirements.txt        # Python dependencies
│
├── analysis/                   # Analytical notebooks
│   ├── notebooks/              # Jupyter notebooks
│   │   ├── money_laundering.ipynb # Money laundering route analysis
│   │   ├── token_insider.ipynb # Token creator/insider analysis
│   │   └── dusting_analysis.ipynb # Dusting attack analysis
│   └── utils/                  # Shared analysis utilities
│       ├── address_utils.py    # Address analysis helpers
│       ├── graph_utils.py      # Network graph helpers
│       ├── risk_scoring.py     # Risk scoring utilities
│       └── visualization.py    # Common visualization code
│
├── dashboards/                 # Dashboard implementations
│   ├── dune/                   # Dune Analytics SQL queries
│   │   ├── solana_transactions.sql # General transaction analysis
│   │   ├── token_insider_analysis.sql # Token insider analysis
│   │   └── money_laundering_routes.sql # Money laundering analysis
│   └── custom/                 # Custom dashboard implementations
│       ├── app.py              # Streamlit dashboard app
│       └── requirements.txt    # Dashboard dependencies
│
├── reports/                    # Generated analysis reports
│
└── README.md                   # Project overview
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- API keys for:
  - Helius API
  - Range API
  - RugCheck API
  - Vybe API

### Installation

<details>
<summary>Click to expand installation steps</summary>

1. Clone the repository:
   ```bash
   git clone https://github.com/cipherzeroprotocol/solana-guard.git
   cd solana-guard
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your API keys:
   ```
   HELIUS_API_KEY=your_helius_api_key
   RANGE_API_KEY=your_range_api_key
   RUGCHECK_JWT_TOKEN=your_rugcheck_token
   VYBE_API_KEY=your_vybe_api_key
   ```

4. Run the main data collection:
   ```bash
   python main.py --address your_solana_address
   ```
</details>

### Using the Dashboard

<details>
<summary>Click to expand dashboard instructions</summary>

1. Navigate to the dashboard directory:
   ```bash
   cd dashboards/custom
   ```

2. Start the Streamlit app:
   ```bash
   streamlit run app.py
   ```

3. Open your browser at `http://localhost:8501` to access the dashboard.
</details>

## 📊 Analysis Capabilities

### Address Analysis

| Feature | Description |
|---------|-------------|
| Risk Scoring | Evaluate risk based on transaction patterns |
| Money Laundering Detection | Identify potential laundering routes |
| Attack Identification | Detect dusting attacks and address poisoning |
| Flow Visualization | Visualize transaction flows graphically |

### Token Analysis

| Feature | Description |
|---------|-------------|
| Rug Pull Assessment | Evaluate risk of token abandonment |
| Insider Trading Detection | Identify suspicious trading patterns |
| Creator Analysis | Analyze token creator behavior |
| Liquidity Analysis | Assess concentration of liquidity |
| Wash Trading Detection | Identify artificial volume creation |

### Blockchain Security

- Cross-chain fund flow analysis
- High-risk entity identification
- Suspicious transaction pattern detection
- Temporal analysis of fund movements

## 🔍 Usage Examples

### Analyzing an Address

```python
from collectors.helius_collector import HeliusCollector
from collectors.range_collector import RangeCollector
from utils.address_utils import classify_address

# Initialize collectors
helius = HeliusCollector()
range_api = RangeCollector()

# Get address data
address = "VinesRG7K3ubzKLbxXz197c1RHV3cACkvGr9Zca7BSw"
tx_history = helius.fetch_transaction_history(address)
token_transfers = helius.analyze_token_transfers(address)
risk_info = range_api.get_address_risk_score(address)

# Classify address
classification = classify_address(address, tx_history, token_transfers, risk_info)
print(f"Address type: {classification['type']}")
print(f"Risk level: {classification['risk_level']}")
```

### Analyzing a Token

```python
from collectors.rugcheck_collector import RugCheckCollector
from utils.risk_scoring import calculate_token_risk

# Initialize collector
rugcheck = RugCheckCollector()

# Get token data
token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
token_report = rugcheck.get_token_report(token_mint)
token_insider_graph = rugcheck.get_token_insider_graph(token_mint)

# Calculate risk score
risk_score = calculate_token_risk(token_mint, token_report)
print(f"Token risk score: {risk_score['risk_score']}")
print(f"Risk level: {risk_score['risk_level']}")
```

## 📚 API Documentation

SolanaGuard integrates with several external APIs to gather data for analysis:

<details>
<summary><strong>Helius API</strong> - Transaction data and account information</summary>

Used for fetching Solana transaction data, account information, and token transfers.

- Key methods:
  - `get_account_info`: Get account information
  - `get_transaction`: Get detailed transaction data
  - `get_token_accounts_by_owner`: Get token accounts owned by an address
</details>

<details>
<summary><strong>Range API</strong> - Risk scoring and cross-chain analysis</summary>

Used for risk scoring, cross-chain analysis, and money laundering detection.

- Key methods:
  - `get_address_risk_score`: Get risk score for an address
  - `analyze_money_laundering_routes`: Identify money laundering patterns
  - `detect_cross_chain_flows`: Detect cross-chain fund flows
</details>

<details>
<summary><strong>RugCheck API</strong> - Token analysis and rug pull assessment</summary>

Used for token analysis, insider detection, and rug pull assessment.

- Key methods:
  - `get_token_report`: Get detailed token report
  - `get_token_insider_graph`: Get insider network for a token
  - `check_token_eligibility`: Check if a token is eligible for verification
</details>

<details>
<summary><strong>Vybe API</strong> - Token activity and holder distribution</summary>

Used for token activity analysis, holder distribution, and program interaction.

- Key methods:
  - `get_token_details`: Get token details and 24h activity
  - `get_token_top_holders`: Get top token holders
  - `get_token_transfers`: Get token transfer transactions
</details>

## 🔧 Advanced Configuration

You can customize the behavior of SolanaGuard by modifying the configuration in `config.py`:

| Setting | Description |
|---------|-------------|
| `DATA_DIR` | Location for storing data and outputs |
| `CACHE_DIR` | Location for caching API responses |
| `RATE_LIMIT` | API rate limiting settings |
| `LOG_LEVEL` | Logging verbosity |

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

> **Note**: SolanaGuard is an analytical tool designed for research purposes. The risk scores and pattern detections should not be considered as definitive proof of illicit activity. Always exercise caution and perform your own due diligence when dealing with blockchain transactions.