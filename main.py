"""
X (Twitter) Account Cleanup Tool
Continuously deletes tweets while respecting API rate limits.
"""

from requests_oauthlib import OAuth1Session
import os
import json
import logging
import time
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename='tweet_deletion.log'
)
logger = logging.getLogger(__name__)

# Add console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Create API-specific logger
api_logger = logging.getLogger('api_logger')
api_logger.setLevel(logging.INFO)
api_logger.propagate = False  # Don't propagate to parent logger

# Add file handler for API logs
api_file_handler = logging.FileHandler('api_calls.log')
api_file_handler.setLevel(logging.INFO)
api_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
api_file_handler.setFormatter(api_formatter)
api_logger.addHandler(api_file_handler)

# Add console handler for API logs if needed
api_console_handler = logging.StreamHandler()
api_console_handler.setLevel(logging.INFO)
api_console_handler.setFormatter(api_formatter)
api_logger.addHandler(api_console_handler)

class TweetDeleter:
    def __init__(self):
        # Get credentials from environment variables
        self.consumer_key = os.getenv('CONSUMER_KEY')
        self.consumer_secret = os.getenv('CONSUMER_SECRET')
        self.access_token = os.getenv('ACCESS_TOKEN')
        self.access_token_secret = os.getenv('ACCESS_TOKEN_SECRET')
        
        # Load user ID directly from environment variable
        self.user_id = os.getenv('TWITTER_USER_ID')
        if not self.user_id:
            logger.warning("TWITTER_USER_ID not found in environment variables. Using fallback method.")
            self.user_id = None
        else:
            logger.info(f"Using user ID from environment: {self.user_id}")
        
        # Initialize OAuth session
        self.oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_token_secret
        )
        
        # API configuration
        self.base_url = "https://api.twitter.com"
        
        # Rate limit configuration for Free tier (updated based on X API documentation)
        self.DELETE_TWEET_LIMIT = 17        # DELETE /2/tweets/:id - 17 requests / 24 hours PER USER
        self.USER_ME_LIMIT = 25             # GET /2/users/me - 25 requests / 24 hours PER USER
        self.TIMELINE_LIMIT = 1             # GET /2/users/:id/tweets - 1 request / 15 mins PER USER
        self.MONTHLY_WRITE_LIMIT = 500      # Total writes per month (safety limit)
        
        # Next rate limit reset times (March 24, 2025 at 00:00 UTC)
        self.next_deletion_reset = datetime(2025, 3, 24, 0, 0, 0)    # 24-hour reset for tweet deletion
        self.next_timeline_reset = datetime.now() + timedelta(minutes=15)   # 15-minute reset for timeline requests
        
        # Rate limit tracking
        self.deletions_today = 0
        self.total_deletions = 0
        self.timeline_requests = 0
        self.user_me_requests = 0
        
        # Reusable constants for wait durations
        self.TIMELINE_WAIT_SECONDS = 900    # 15 minutes
        self.TWEET_SLEEP_SECONDS = 5
        self.PAGE_SLEEP_SECONDS = 60
        
        # Keep track of our first page of tweets to avoid hitting rate limits
        self.first_page_retrieved = False

    def _make_request(self, method, endpoint, params=None, data=None):
        """Make an API request without error handling and log the exact response"""
        url = f"{self.base_url}{endpoint}"
        
        # Log request details to API log
        api_logger.info(f"REQUEST: {method.upper()} {url}")
        api_logger.info(f"REQUEST PARAMS: {params}")
        api_logger.info(f"REQUEST DATA: {data}")
        
        if method.lower() == 'get':
            response = self.oauth.get(url, params=params)
        elif method.lower() == 'post':
            response = self.oauth.post(url, json=data)
        elif method.lower() == 'delete':
            response = self.oauth.delete(url)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
            
        # Get response data and status code
        response_data = response.json()
        
        # Log the full response to the API log
        api_logger.info(f"RESPONSE STATUS: {response.status_code}")
        api_logger.info(f"RESPONSE HEADERS: {dict(response.headers)}")
        api_logger.info(f"RESPONSE DATA: {json.dumps(response_data, indent=2)}")
        
        # Log a summary to the main log
        logger.info(f"API call {method.upper()} {url} with params={params} data={data} returned: {response_data}")
        
        return response_data

    def _apply_timeline_rate_limit(self):
        """Check if we've hit the timeline rate limit and wait if needed"""
        now = datetime.now()
        
        # If we've already made our allowed requests and we're before the reset time
        if self.timeline_requests >= self.TIMELINE_LIMIT and now < self.next_timeline_reset:
            wait_seconds = (self.next_timeline_reset - now).total_seconds()
            logger.info(f"Timeline request limit reached. Waiting until next reset at {self.next_timeline_reset} UTC ({wait_seconds:.1f} seconds).")
            time.sleep(wait_seconds)
            
            # After waiting, reset the counter and update next reset time
            self.timeline_requests = 0
            self.next_timeline_reset = datetime.now() + timedelta(minutes=15)
        # If we're past the reset time
        elif now >= self.next_timeline_reset:
            # Reset counter and update next reset time
            logger.info(f"Timeline rate limit reset window passed. Resetting counter.")
            self.timeline_requests = 0
            self.next_timeline_reset = datetime.now() + timedelta(minutes=15)

    def _get_tweets(self, next_token=None):
        """Get user tweets without error handling"""
        # Check if we've already retrieved one page and aren't ready for the next one
        if self.first_page_retrieved and self.timeline_requests >= self.TIMELINE_LIMIT:
            logger.info("Already retrieved first page of tweets and timeline rate limit reached.")
            logger.info(f"Next timeline request can be made after {self.next_timeline_reset} UTC.")
            return {"data": []}  # Return empty data to end processing
            
        # Apply rate limit waiting if needed
        self._apply_timeline_rate_limit()

        # Increment counter before making request
        self.timeline_requests += 1  
        self.first_page_retrieved = True
        
        logger.info(f"Making timeline request {self.timeline_requests}/{self.TIMELINE_LIMIT} before next reset at {self.next_timeline_reset} UTC")
        
        params = {'max_results': 100}
        if next_token:
            params['pagination_token'] = next_token

        return self._make_request('get', f'/2/users/{self.user_id}/tweets', params)

    def _delete_tweet(self, tweet_id):
        """Delete a single tweet without error handling"""
        # Check deletion limits
        if self.deletions_today >= self.DELETE_TWEET_LIMIT:
            current_time = datetime.now()
            if current_time < self.next_deletion_reset:
                logger.warning(f"Daily tweet deletion limit reached ({self.DELETE_TWEET_LIMIT}). Next reset at {self.next_deletion_reset} UTC.")
                return False
        
        # Make the deletion request
        self._make_request('delete', f'/2/tweets/{tweet_id}')
        return True

    def _pull_tweets(self):
        """Pull tweets once per month and return IDs"""
        logger.info(f"Next timeline rate limit reset: {self.next_timeline_reset} UTC ({self.TIMELINE_LIMIT} requests per 15m)")
        
        # Check if we've already pulled tweets this month
        current_month = datetime.now().strftime('%Y-%m')
        last_pull_month = self._get_last_pull_month()
        
        if last_pull_month == current_month:
            logger.info(f"Already pulled tweets this month ({current_month}). Skipping.")
            return []
        
        # Start collecting tweets
        collected_ids = []
        next_token = None
        
        # Just make one request to get up to 100 tweets - respect monthly limit
        tweets_data = self._get_tweets(next_token)
        
        if not tweets_data.get('data'):
            logger.info("No tweet data returned in the API response.")
            return collected_ids
        
        # Extract IDs
        tweets = tweets_data['data']
        logger.info(f"Found {len(tweets)} tweets")
        
        for tweet in tweets:
            collected_ids.append(tweet['id'])
        
        # Save the date of this pull
        self._set_last_pull_month(current_month)
        
        return collected_ids

    def _delete_tweets(self, tweet_ids):
        """Delete tweets (up to daily limit) and return remaining IDs"""
        if not tweet_ids:
            logger.info("No tweets to delete.")
            return []
        
        logger.info(f"Next tweet deletion rate limit reset: {self.next_deletion_reset} UTC ({self.DELETE_TWEET_LIMIT} deletions per 24h)")
        
        # Track how many we've deleted today
        deleted_count = 0
        remaining_ids = tweet_ids.copy()
        
        # Process tweet IDs (up to daily limit)
        for tweet_id in tweet_ids[:self.DELETE_TWEET_LIMIT]:
            if deleted_count >= self.DELETE_TWEET_LIMIT:
                logger.info(f"Daily deletion limit reached ({self.DELETE_TWEET_LIMIT}). Stopping.")
                break
            
            result = self._delete_tweet(tweet_id)
            if result:
                deleted_count += 1
                logger.info(f"Deleted tweet {tweet_id} ({deleted_count}/{self.DELETE_TWEET_LIMIT} today)")
                # Remove from our list of pending tweets
                remaining_ids.remove(tweet_id)
            
            # Respect rate limits with a delay
            time.sleep(self.TWEET_SLEEP_SECONDS)
        
        return remaining_ids

    def _get_last_pull_month(self):
        """Get the last month we pulled tweets"""
        try:
            with open('.github/last_pull.txt', 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""
        
    def _set_last_pull_month(self, month_string):
        """Save the month we pulled tweets"""
        with open('.github/last_pull.txt', 'w') as f:
            f.write(month_string)

    def run(self):
        """Main execution method that determines what operation to perform"""
        logger.info(f"User ID: {self.user_id}")
        
        # Get operation mode from environment variable
        operation_mode = os.getenv('OPERATION_MODE', 'auto').lower()
        logger.info(f"Operation mode: {operation_mode}")
        
        # Load existing tweet IDs
        pending_tweet_ids = load_tweet_ids()
        today = datetime.now()
        
        # Force specific operation based on mode, or auto-detect if not specified
        if operation_mode == 'retrieve' or operation_mode == 'initialize':
            # Force retrieval mode
            logger.info("Forced tweet retrieval mode")
            new_ids = self._pull_tweets()
            pending_tweet_ids.extend(new_ids)
            save_tweet_ids(pending_tweet_ids)
            logger.info(f"Saved {len(new_ids)} new tweet IDs. Total pending: {len(pending_tweet_ids)}")
        elif operation_mode == 'delete':
            # Force deletion mode
            logger.info(f"Forced tweet deletion mode. {len(pending_tweet_ids)} tweets pending")
            remaining_ids = self._delete_tweets(pending_tweet_ids)
            save_tweet_ids(remaining_ids)
            logger.info(f"Deletion complete. {len(remaining_ids)} tweets still pending")
        else:
            # Auto mode - determine based on day of month or if list is empty
            if today.day == 1 or len(pending_tweet_ids) == 0:  # First day of month or empty list
                # Pull operation - Only once a month
                logger.info("Performing monthly tweet pull operation")
                new_ids = self._pull_tweets()
                pending_tweet_ids.extend(new_ids)
                save_tweet_ids(pending_tweet_ids)
                logger.info(f"Saved {len(new_ids)} new tweet IDs. Total pending: {len(pending_tweet_ids)}")
            else:
                # Delete operation - Run daily
                logger.info(f"Performing daily tweet deletion operation. {len(pending_tweet_ids)} tweets pending")
                remaining_ids = self._delete_tweets(pending_tweet_ids)
                save_tweet_ids(remaining_ids)
                logger.info(f"Deletion complete. {len(remaining_ids)} tweets still pending")

def main():
    deleter = TweetDeleter()
    logger.info("Starting tweet deletion process...")
    deleter.run()

def load_tweet_ids():
    """Load saved tweet IDs from file"""
    try:
        with open('.github/tweet_ids.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_tweet_ids(tweet_ids):
    """Save tweet IDs to file"""
    # Create .github directory if it doesn't exist
    os.makedirs('.github', exist_ok=True)
    with open('.github/tweet_ids.json', 'w') as f:
        json.dump(tweet_ids, f, indent=2)

if __name__ == "__main__":
    main()