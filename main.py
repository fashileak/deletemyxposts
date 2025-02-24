"""
X (Twitter) Account Cleanup Tool
Continuously deletes tweets while respecting API rate limits.
"""

from requests_oauthlib import OAuth1Session
import os
import json
import logging
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import sys

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
        
        if not all([self.consumer_key, self.consumer_secret, 
                   self.access_token, self.access_token_secret]):
            logger.error("Missing required environment variables")
            sys.exit(1)
        
        # Initialize OAuth session
        self.oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_token_secret
        )
        
        self.base_url = "https://api.twitter.com"
        self.daily_tweet_limit = 17  # DELETE tweets per 24h
        self.get_tweets_limit = 1    # GET tweets per 15m
        self.get_user_limit = 25     # GET user info per 24h
        self.monthly_post_limit = 500  # Total writes per month
        
        self.deletions_today = 0
        self.get_requests_15min = 0
        self.last_get_reset = datetime.now()
        self.total_deletions = 0
        
        # Get user ID once at initialization
        try:
            self.user_id = self._get_user_id()
        except APIError as e:
            if e.status_code == 429:
                logger.error(f"Rate limit exceeded while getting user info: {e.message}")
                sys.exit(429)
            else:
                logger.error(f"Failed to get user info: {e.message}")
                sys.exit(1)

        # Add these debug lines
        logger.debug(f"Consumer key length: {len(self.consumer_key)}")
        logger.debug(f"Consumer secret length: {len(self.consumer_secret)}")
        logger.debug(f"Access token length: {len(self.access_token)}")
        logger.debug(f"Access token secret length: {len(self.access_token_secret)}")

    def _get_user_id(self):
        """Get user ID from the API"""
        url = f"{self.base_url}/2/users/me"
        response = self.oauth.get(url)
        
        if response.status_code != 200:
            error_data = response.json()
            raise APIError(
                f"Failed to get user info: {error_data}",
                error_type="user_info_error",
                status_code=response.status_code
            )
        
        return response.json()['data']['id']

    def _check_rate_limits(self, action_type):
        """Check rate limits before making requests"""
        now = datetime.now()
        
        if action_type == 'delete':
            if self.deletions_today >= self.daily_tweet_limit:
                next_reset = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
                raise APIError(
                    "Daily deletion limit reached",
                    error_type='daily-limit',
                    status_code=403
                )
                
        elif action_type == 'get':
            # Reset counter if 15 minutes have passed
            if (now - self.last_get_reset).total_seconds() >= 900:  # 15 minutes
                self.get_requests_15min = 0
                self.last_get_reset = now
                
            if self.get_requests_15min >= self.get_tweets_limit:
                next_reset = self.last_get_reset + timedelta(minutes=15)
                raise APIError(
                    "GET request limit reached",
                    error_type='rate-limit',
                    status_code=429
                )

    def _get_tweets(self, next_token=None):
        """Get tweets with pagination"""
        self._check_rate_limits('get')
        
        url = f"{self.base_url}/2/users/{self.user_id}/tweets"
        params = {'max_results': 100}  # Maximum allowed per request
        if next_token:
            params['pagination_token'] = next_token
            
        response = self.oauth.get(url, params=params)
        self.get_requests_15min += 1
        
        if response.status_code != 200:
            self._handle_api_error(response)
        return response.json()

    def delete_tweets(self):
        """Delete tweets respecting rate limits"""
        try:
            while True:
                try:
                    self._check_rate_limits('delete')
                    
                    tweets = self._get_tweets()
                    if not tweets.get('data'):
                        logger.info("No more tweets found")
                        return 0

                    for tweet in tweets['data']:
                        self._check_rate_limits('delete')
                        
                        if self._delete_tweet(tweet['id']):
                            self.deletions_today += 1
                            self.total_deletions += 1
                            logger.info(
                                f"Deleted tweet {tweet['id']} "
                                f"({self.deletions_today}/{self.daily_tweet_limit} today, "
                                f"{self.total_deletions} total)"
                            )
                        
                        # Wait between deletions
                        time.sleep(60)  # 1 minute between deletions

                except APIError as e:
                    if e.status_code == 429:
                        logger.info(f"Rate limit exceeded. Waiting for rate limit reset.")
                        time.sleep(900)  # Wait for 15 minutes
                        continue
                    elif e.error_type == 'daily-limit':
                        logger.info(f"Daily limit reached. Next attempt scheduled for: {e.retry_after}")
                        time.sleep((e.retry_after - datetime.now()).total_seconds())
                        continue
                    elif e.error_type == 'rate-limit':
                        logger.info(f"Rate limit reached. Next attempt at: {e.retry_after}")
                        time.sleep((e.retry_after - datetime.now()).total_seconds())
                        continue
                    else:
                        raise

        except Exception as e:
            logger.error(f"Fatal error: {str(e)}")
            return 1

    def _handle_api_error(self, response):
        """Handle API errors and raise appropriate exceptions"""
        try:
            error_data = response.json()
            status_code = response.status_code
            
            if status_code == 429:
                logger.error(f"Rate limit exceeded: {error_data}")
                raise APIError(
                    str(error_data),
                    error_type="rate_limit",
                    status_code=429
                )
            elif "usage-capped" in str(error_data):
                logger.error(f"Monthly cap reached: {error_data}")
                raise APIError(
                    str(error_data),
                    error_type="monthly_cap",
                    status_code=403
                )
            else:
                logger.error(f"API error: {error_data}")
                raise APIError(
                    str(error_data),
                    error_type="unknown",
                    status_code=status_code
                )
        except json.JSONDecodeError:
            raise APIError(
                response.text,
                error_type="unknown",
                status_code=response.status_code
            )

    def _process_tweets(self, tweets):
        """Process and delete tweets"""
        for tweet in tweets:
            if self.deletions_today >= self.daily_tweet_limit:
                break
                
            if self._delete_tweet(tweet['id']):
                self.deletions_today += 1
                self.total_deletions += 1
                logger.info(
                    "Deleted tweet %s (%d/%d today, %d total)",
                    tweet['id'], self.deletions_today, self.daily_tweet_limit, self.total_deletions
                )

    def _delete_tweet(self, tweet_id):
        """Delete a single tweet"""
        response = self.oauth.delete(f"{self.base_url}/2/tweets/{tweet_id}")
        return response.status_code == 200

def main():
    try:
        deleter = TweetDeleter()
        logger.info("Starting tweet deletion process...")
        exit_code = deleter.delete_tweets()
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()