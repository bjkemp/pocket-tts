import os
import sys
from pathlib import Path

# Add project root to path so we can import the SSL patch
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Force disable SSL verification
import tools.disable_ssl_verify

from huggingface_hub import login

def run_login():
    token = input("Paste your Hugging Face token: ").strip()
    if token:
        login(token=token, add_to_git_credential=True)
        print("✅ Logged in successfully!")
    else:
        print("❌ No token provided.")

if __name__ == "__main__":
    run_login()
