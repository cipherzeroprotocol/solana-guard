"""
Entry point for SolanaGuard
This script runs the data_collection package as a module
"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the main function directly
from data_collection.main import main

if __name__ == "__main__":
    sys.exit(main())
