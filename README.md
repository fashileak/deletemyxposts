# X Account Tweet Cleanup Tool

Automatically deletes tweets from your X (Twitter) account while respecting API rate limits.

## Features
- Respects X API rate limits (Free tier)
- Continuous operation with automatic retries
- Secure credential handling
- Detailed logging

## Setup
1. Clone the repository
2. Create a `.env` file with your API credentials:
   ```
   CONSUMER_KEY=your_api_key
   CONSUMER_SECRET=your_api_secret
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the script:
   ```bash
   python main.py
   ```

## Rate Limits (Free Tier)
- 17 tweet deletions per 24 hours
- 1 GET request per 15 minutes
- Maximum 100 tweets per request

## Security
- API credentials stored in `.env` file (not in code)
- `.env` file excluded from git
- Logging with sensitive data redaction

## Deployment
Instructions for deployment coming soon...

## License
MIT License
