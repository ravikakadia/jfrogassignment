import os

# Configuration with environment variable fallbacks
JFROG_URL = os.getenv('JFROG_URL', 'https://trialvq0712.jfrog.io')
USERNAME = os.getenv('JFROG_USERNAME', 'perftest')
PASSWORD = os.getenv('JFROG_PASSWORD', 'PerfTest123$')
REPO_NAME = os.getenv('JFROG_REPO_NAME', 'docker-local')
IMAGE_NAME = os.getenv('JFROG_IMAGE_NAME', 'alpine:3.9')

# Optional: Add validation
def validate_config():
    """Validate that all required configuration is present"""
    required_vars = {
        'JFROG_URL': JFROG_URL,
        'USERNAME': USERNAME,
        'PASSWORD': PASSWORD,
        'REPO_NAME': REPO_NAME,
        'IMAGE_NAME': IMAGE_NAME
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    return True

# Optional: Add a function to print current config (without sensitive data)
def print_config():
    """Print current configuration (without sensitive data)"""
    print(f"JFROG_URL: {JFROG_URL}")
    print(f"USERNAME: {USERNAME}")
    print(f"REPO_NAME: {REPO_NAME}")
    print(f"IMAGE_NAME: {IMAGE_NAME}")
    print(f"PASSWORD: {'*' * len(PASSWORD) if PASSWORD else 'Not set'}")

# Validate config on import
try:
    validate_config()
except ValueError as e:
    print(f"Configuration Error: {e}")
    print("Please set the required environment variables.")
