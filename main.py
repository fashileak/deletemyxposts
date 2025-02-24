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

# Exit codes
EXIT_SUCCESS = 0
EXIT_AUTH_ERROR = 401
EXIT_RATE_LIMIT = 429
EXIT_MONTHLY_CAP = 2
EXIT_DAILY_LIMIT = 3
EXIT_UNKNOWN_ERROR = 1

class APIError(Exception):
    def __init__(self, message, error_type=None, status_code=None):
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        super().__init__(self.message)

class TweetDeleter:
    def __init__(self):
        # Get credentials from environment variables
        self.consumer_key = os.getenv('CONSUMER_KEY')
        self.consumer_secret = os.getenv('CONSUMER_SECRET')
        self.access_token = os.getenv('ACCESS_TOKEN')
        self.access_token_secret = os.getenv('ACCESS_TOKEN_SECRET')
        
        # Validate environment variables
        if not all([self.consumer_key, self.consumer_secret, 
                   self.access_token, self.access_token_secret]):
            logger.error("Missing required environment variables")
            sys.exit(EXIT_UNKNOWN_ERROR)
        
        # Initialize OAuth session
        self.oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_token_secret
        )
        
        # API configuration
        self.base_url = "https://api.twitter.com"
        
        # Rate limit configuration for Free tier
        self.daily_delete_limit = 17        # DELETE tweets per 24h
        self.user_request_limit = 1         # GET user info per 24h
        self.timeline_request_limit = 1     # GET tweets per 15m
        self.monthly_write_limit = 500      # Total writes per month
        
        # Rate limit tracking
        self.deletions_today = 0
        self.total_deletions = 0
        self.timeline_requests = 0
        self.timeline_reset_time = datetime.now()
        
        # User ID (initialized in run())
        self.user_id = None

    def _make_request(self, method, endpoint, params=None, data=None):
        """Make an API request with consistent error handling"""
        url = f"{self.base_url}{endpoint}"
        
        if method.lower() == 'get':
            response = self.oauth.get(url, params=params)
        elif method.lower() == 'post':
            response = self.oauth.post(url, json=data)
        elif method.lower() == 'delete':
            response = self.oauth.delete(url)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
            
        if response.status_code != 200:
            self._handle_api_error(response)
            
        return response.json()

    def _handle_api_error(self, response):
        """Parse API error response and raise appropriate exception"""
        status_code = response.status_code
        
        try:
            error_data = response.json()
        except json.JSONDecodeError:
            error_data = {"error": response.text}
            
        error_msg = json.dumps(error_data)
            
        if status_code == 401:
            logger.error(f"Authentication failed: {error_msg}")
            raise APIError(error_msg, "auth_error", status_code)
            
        elif status_code == 429:
            # Check if reset time is in headers
            reset_time = None
            if 'x-rate-limit-reset' in response.headers:
                reset_timestamp = int(response.headers['x-rate-limit-reset'])
                reset_time = datetime.fromtimestamp(reset_timestamp)
                logger.warning(f"Rate limit reset at: {reset_time}")
                
            logger.error(f"Rate limit exceeded: {error_msg}")
            raise APIError(error_msg, "rate_limit", status_code)
            
        elif "usage-capped" in str(error_data):
            logger.error(f"Monthly usage cap reached: {error_msg}")
            raise APIError(error_msg, "monthly_cap", status_code)
            
        else:
            logger.error(f"API error ({status_code}): {error_msg}")
            raise APIError(error_msg, "unknown", status_code)

    def _get_user_id(self):
        """Get the authenticated user's ID"""
        try:
            data = self._make_request('get', '/2/users/me')
            return data['data']['id']
        except APIError as e:
            logger.error(f"Failed to get user ID: {e.message}")
            if e.status_code == 401:
                sys.exit(EXIT_AUTH_ERROR)
            elif e.status_code == 429:
                sys.exit(EXIT_RATE_LIMIT)
            else:
                sys.exit(EXIT_UNKNOWN_ERROR)

    def _get_tweets(self, next_token=None):
        """Get user tweets"""
        # Check if we've exceeded the timeline request limit
        now = datetime.now()
        elapsed = (now - self.timeline_reset_time).total_seconds()
        
        # Reset counter if 15 minutes have passed
        if elapsed >= 900:  # 15 minutes in seconds
            self.timeline_requests = 0
            self.timeline_reset_time = now
            
        # Check if we've reached the limit
        if self.timeline_requests >= self.timeline_request_limit:
            wait_time = 900 - elapsed
            if wait_time > 0:
                logger.info(f"Timeline request limit reached. Waiting {wait_time} seconds.")
                time.sleep(wait_time)
                self.timeline_requests = 0
                self.timeline_reset_time = datetime.now()
        
        # Increment request counter
        self.timeline_requests += 1
        
        # Make the request
        params = {'max_results': 100}
        if next_token:
            params['pagination_token'] = next_token
            
        try:
            return self._make_request('get', f'/2/users/{self.user_id}/tweets', params)
        except APIError as e:
            if e.status_code == 429:
                sys.exit(EXIT_RATE_LIMIT)
            elif e.error_type == "monthly_cap":
                sys.exit(EXIT_MONTHLY_CAP)
            else:
                raise

    def _delete_tweet(self, tweet_id):
        """Delete a single tweet"""
        try:
            self._make_request('delete', f'/2/tweets/{tweet_id}')
            return True
        except APIError as e:
            if e.status_code == 429:
                sys.exit(EXIT_RATE_LIMIT)
            elif e.error_type == "monthly_cap":
                sys.exit(EXIT_MONTHLY_CAP)
            else:
                logger.error(f"Failed to delete tweet {tweet_id}: {e.message}")
                return False

    def run(self):
        """Main execution method"""
        try:
            # Get user ID first
            self.user_id = self._get_user_id()
            logger.info(f"User ID: {self.user_id}")
            
            next_token = None
            
            while True:
                # Check daily limit
                if self.deletions_today >= self.daily_delete_limit:
                    logger.info(f"Daily deletion limit reached ({self.daily_delete_limit}). Exiting.")
                    return EXIT_DAILY_LIMIT
                
                # Get tweets
                tweets_data = self._get_tweets(next_token)
                
                # Check if we have tweets
                if not tweets_data.get('data'):
                    logger.info("No more tweets found. Process complete.")
                    return EXIT_SUCCESS
                
                tweets = tweets_data['data']
                logger.info(f"Found {len(tweets)} tweets")
                
                # Update pagination token
                next_token = tweets_data.get('meta', {}).get('next_token')
                
                # Process tweets
                for tweet in tweets:
                    # Check daily limit again
                    if self.deletions_today >= self.daily_delete_limit:
                        logger.info(f"Daily deletion limit reached ({self.daily_delete_limit}). Exiting.")
                        return EXIT_DAILY_LIMIT
                    
                    # Delete tweet
                    tweet_id = tweet['id']
                    if self._delete_tweet(tweet_id):
                        self.deletions_today += 1
                        self.total_deletions += 1
                        logger.info(f"Deleted tweet {tweet_id} ({self.deletions_today}/{self.daily_delete_limit} today)")
                    
                    # Respect rate limits with a delay
                    time.sleep(5)
                
                # If no pagination token, we're done
                if not next_token:
                    logger.info("No more pages of tweets. Process complete.")
                    return EXIT_SUCCESS
                
                # Add delay between pages
                time.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("Process interrupted by user.")
            return EXIT_SUCCESS
        except APIError as e:
            if e.status_code == 429:
                return EXIT_RATE_LIMIT
            elif e.error_type == "monthly_cap":
                return EXIT_MONTHLY_CAP
            elif e.status_code == 401:
                return EXIT_AUTH_ERROR
            else:
                return EXIT_UNKNOWN_ERROR
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return EXIT_UNKNOWN_ERROR

def main():
    deleter = TweetDeleter()
    logger.info("Starting tweet deletion process...")
    exit_code = deleter.run()
    logger.info(f"Process completed with exit code: {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()