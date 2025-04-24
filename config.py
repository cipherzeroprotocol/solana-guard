"""
Configuration settings for the SolanaGuard project.
"""
import os

# Base directories
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
REPORTS_DIR = os.path.join(PROJECT_ROOT, 'reports')
VISUALIZATIONS_DIR = os.path.join(DATA_DIR, 'visualizations')
OUTPUT_DIR = os.path.join(DATA_DIR, 'output')

# Create necessary directories if they don't exist
for directory in [DATA_DIR, REPORTS_DIR, VISUALIZATIONS_DIR, OUTPUT_DIR]:
    os.makedirs(directory, exist_ok=True)

# API configuration settings
API_KEYS = {
    'helius': os.environ.get('HELIUS_API_KEY', ''),
    'range': os.environ.get('RANGE_API_KEY', ''),
    'vybe': os.environ.get('VYBE_API_KEY', ''),
    'rugcheck': os.environ.get('RUGCHECK_API_KEY', '')
}
