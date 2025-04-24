"""
Script to fix imports in SolanaGuard collector modules
"""
import os
import re

def patch_collector_module(filepath):
    """Patch a collector module to use correct import paths"""
    print(f"Patching {filepath}...")
    
    with open(filepath, 'r') as file:
        content = file.read()
    
    # Replace direct 'config' imports with the proper package path
    patched_content = re.sub(
        r'from config import',
        'from data_collection.config import',
        content
    )
    
    # Only write if changes were made
    if content != patched_content:
        with open(filepath, 'w') as file:
            file.write(patched_content)
        print(f"  - Fixed imports in {filepath}")
    else:
        print(f"  - No changes needed in {filepath}")

def main():
    """Find and patch all collector modules"""
    collectors_dir = os.path.join('data_collection', 'collectors')
    
    if not os.path.exists(collectors_dir):
        print(f"Directory not found: {collectors_dir}")
        return
    
    for filename in os.listdir(collectors_dir):
        if filename.endswith('_collector.py'):
            filepath = os.path.join(collectors_dir, filename)
            patch_collector_module(filepath)
    
    print("\nImports patched successfully!")
    print("You can now run: python run_solana_guard.py")

if __name__ == "__main__":
    main()
