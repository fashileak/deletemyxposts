# X Account Tweet Cleanup Tool

Automatically deletes tweets from your X (Twitter) account while respecting API rate limits.

## Features
- Respects X API rate limits (Free tier)
- Scheduled tweet retrieval (monthly) and deletion (daily)
- Detailed API call logging
- Pagination support for retrieving more tweets
- GitHub Actions integration for automated operation
- Secure credential handling

## How It Works
1. **Monthly Tweet Retrieval** - On the 1st of each month, the tool retrieves up to 100 tweets and adds them to the deletion queue
2. **Daily Tweet Deletion** - Every day, the tool deletes up to 17 tweets (API rate limit)
3. **One-time Setup** - On March 24, 2025, the tool will perform an initial setup to populate the tweet deletion queue

## Setup

### Local Development
1. Clone the repository
2. Create a `.env` file with your API credentials:
   ```
   CONSUMER_KEY=your_api_key
   CONSUMER_SECRET=your_api_secret
   ACCESS_TOKEN=your_access_token
   ACCESS_TOKEN_SECRET=your_access_token_secret
   TWITTER_USER_ID=your_twitter_user_id
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the script:
   ```bash
   python main.py
   ```

### GitHub Actions Deployment
1. Fork this repository
2. Add your X API credentials as GitHub secrets:
   - CONSUMER_KEY
   - CONSUMER_SECRET
   - ACCESS_TOKEN
   - ACCESS_TOKEN_SECRET
   - TWITTER_USER_ID
3. The workflows will automatically run on schedule

## Rate Limits (Free Tier)
- 17 tweet deletions per 24 hours
- 1 timeline request per 15 minutes
- Maximum 100 tweets per request

## Detailed Logging
This tool provides comprehensive logging:

1. **General Application Log** (`tweet_deletion.log`)
   - Main application flow
   - High-level operation summaries
   - Rate limit management

2. **API Communication Log** (`api_calls.log`)
   - Detailed request parameters
   - Complete response data
   - HTTP status codes and headers
   - Raw JSON responses

3. **GitHub Action Logs**
   - All logs are saved as GitHub Action artifacts
   - Summary information displayed in the workflow run summary
   - API responses and rate limit information highlighted

## Operation Modes
The tool can operate in several modes:

- **auto** - Default mode, determines action based on the day of month
- **retrieve** - Only retrieves tweets (used by monthly workflow)
- **delete** - Only deletes tweets (used by daily workflow)
- **initialize** - Initial setup mode to populate the queue (used by setup workflow)

## Security
- API credentials stored in `.env` file (not in code)
- `.env` file excluded from git
- When using GitHub Actions, credentials are stored as secrets

## License
MIT License
