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

class TweetDeleter:
    def __init__(self):
        # Get credentials from environment variables
        self.consumer_key = os.getenv('CONSUMER_KEY')
        self.consumer_secret = os.getenv('CONSUMER_SECRET')
        self.access_token = os.getenv('ACCESS_TOKEN')
        self.access_token_secret = os.getenv('ACCESS_TOKEN_SECRET')
        
        if not all([self.consumer_key, self.consumer_secret, 
                   self.access_token, self.access_token_secret]):
            raise ValueError("Missing required environment variables. Check .env file.")
        
        # Initialize OAuth session with permanent tokens
        self.oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_token_secret
        )
        
        self.base_url = "https://api.twitter.com"
        self.daily_limit = 17
        self.deletions_today = 0
        self.total_deletions = 0
        
        # Get user ID once at initialization
        self.user_id = self._get_user_id()

    def _get_user_id(self):
        """Get user ID using OAuth tokens"""
        response = self.oauth.get(f"{self.base_url}/2/users/me")
        if response.status_code != 200:
            raise Exception(f"Failed to get user info: {response.text}")
        return response.json()['data']['id']

    def delete_tweets(self):
        """Delete tweets respecting rate limits"""
        next_token = None
        
        while True:
            try:
                if self.deletions_today >= self.daily_limit:
                    self._wait_for_next_day()
                    continue

                tweets = self._get_tweets(next_token)
                
                if not tweets.get('data'):
                    self._wait_for_next_day("No tweets found")
                    continue

                next_token = tweets.get('meta', {}).get('next_token')
                self._process_tweets(tweets['data'])
                
                if not next_token:
                    self._wait_for_next_day("No more pages")
                    continue

                self._wait_for_rate_limit()

            except Exception as e:
                logger.error("Error: %s", str(e))
                time.sleep(300)  # 5 minutes

    def _get_tweets(self, next_token=None):
        """Get tweets with pagination"""
        url = f"{self.base_url}/2/users/{self.user_id}/tweets"
        params = {'max_results': 100}
        if next_token:
            params['pagination_token'] = next_token
            
        response = self.oauth.get(url, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to get tweets: {response.text}")
        return response.json()

    def _process_tweets(self, tweets):
        """Process and delete tweets"""
        for tweet in tweets:
            if self.deletions_today >= self.daily_limit:
                break
                
            if self._delete_tweet(tweet['id']):
                self.deletions_today += 1
                self.total_deletions += 1
                logger.info(
                    "Deleted tweet %s (%d/%d today, %d total)",
                    tweet['id'], self.deletions_today, self.daily_limit, self.total_deletions
                )

    def _delete_tweet(self, tweet_id):
        """Delete a single tweet"""
        response = self.oauth.delete(f"{self.base_url}/2/tweets/{tweet_id}")
        return response.status_code == 200

    def _wait_for_rate_limit(self):
        """Wait for rate limit reset"""
        next_fetch = datetime.now() + timedelta(minutes=15)
        logger.info("Next fetch at: %s", next_fetch.strftime('%H:%M:%S'))
        time.sleep(900)  # 15 minutes

    def _wait_for_next_day(self, reason="Daily limit reached"):
        """Wait until next day"""
        next_time = datetime.now() + timedelta(days=1)
        logger.info("%s. Resuming at %s", reason, next_time.strftime('%Y-%m-%d %H:%M:%S'))
        self.deletions_today = 0
        time.sleep(86400)  # 24 hours

def main():
    try:
        deleter = TweetDeleter()
        logger.info("Starting tweet deletion process...")
        deleter.delete_tweets()
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error("Fatal error: %s", str(e))

if __name__ == "__main__":
    main()