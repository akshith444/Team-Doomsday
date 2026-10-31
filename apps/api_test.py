from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Verify the key is loaded
api_key = os.getenv("GOOGLE_API_KEY")

if api_key:
    print("SUCCESS: Environment variables loaded successfully!")
    print(f"API Key starts with: {api_key[:5]}...")
else:
    print("ERROR: GOOGLE_API_KEY not found. Check your .env file.")