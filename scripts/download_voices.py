import os
import sys
from pathlib import Path

# Add project root to path so we can import the SSL patch
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Force disable SSL verification via the project's tool
try:
    import tools.disable_ssl_verify
    print("SSL verification disabled via project tools.")
except ImportError:
    print("⚠️ Could not find tools.disable_ssl_verify, attempting manual bypass...")
    import requests
    from urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    
    # Monkey patch requests
    old_merge_environment_settings = requests.Session.merge_environment_settings
    def merge_environment_settings(self, url, proxies, stream, verify, cert):
        settings = old_merge_environment_settings(self, url, proxies, stream, verify, cert)
        settings['verify'] = False
        return settings
    requests.Session.merge_environment_settings = merge_environment_settings

# New: Also patch httpx which is used by huggingface_hub for listing files
try:
    import httpx
    # Store the original init
    original_client_init = httpx.Client.__init__
    def patched_client_init(self, *args, **kwargs):
        kwargs['verify'] = False
        original_client_init(self, *args, **kwargs)
    httpx.Client.__init__ = patched_client_init
    
    original_async_client_init = httpx.AsyncClient.__init__
    def patched_async_client_init(self, *args, **kwargs):
        kwargs['verify'] = False
        original_async_client_init(self, *args, **kwargs)
    httpx.AsyncClient.__init__ = patched_async_client_init
except ImportError:
    pass

from huggingface_hub import HfApi, hf_hub_download

def download():
    # Correct Repo for voices!
    REPO_ID = "kyutai/tts-voices" 
    print(f"🚀 Starting download from Hugging Face ({REPO_ID})...")
    try:
        api = HfApi()
        # Get all files in the repo
        files = api.list_repo_files(repo_id=REPO_ID)
        
        # Filter for the ones we need: wav, safetensors, AND model files (like tokenizer.model)
        target_extensions = (".wav", ".safetensors", ".model", ".yaml", ".json")
        voice_files = [f for f in files if f.endswith(target_extensions)]
        # Exclude internal git files
        voice_files = [f for f in voice_files if not f.startswith(".git")]
        
        print(f"📦 Found {len(voice_files)} important files to check.")
        
        for file_path in voice_files:
            local_path = project_root / "tts-voices" / file_path
            
            # If it's too small, it's likely an LFS pointer
            should_download = True
            if local_path.exists():
                size = local_path.stat().st_size
                if size > 1000: # Over 1KB is likely real data
                    should_download = False
            
            if should_download:
                print(f"📥 Downloading {file_path}...")
                try:
                    # Ensure directory exists
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    hf_hub_download(
                        repo_id=REPO_ID,
                        filename=file_path,
                        local_dir=str(project_root / "tts-voices"),
                        force_download=True
                    )
                except Exception as file_error:
                    print(f"⚠️  Failed to download {file_path}: {file_error}")
            else:
                # print(f"✅ {file_path} already exists and is not a pointer.")
                pass
        
        print(f"✅ Process complete! Actual files checked in: {project_root / 'tts-voices'}")
    except Exception as e:
        print(f"❌ Download failed: {e}")
        print(f"\nTIP: If it says 'Access Restricted', you must:")
        print(f"1. Visit https://huggingface.co/{REPO_ID}")
        print("2. Accept the terms of use while logged in.")
        print("3. Run: HF_HUB_DISABLE_SSL_VERIFY=1 huggingface-cli login")

if __name__ == "__main__":
    download()
