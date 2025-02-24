from requests_oauthlib import OAuth1Session
import os
import json
import logging
import time
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Changed to INFO for cleaner output
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# X API credentials
consumer_key = "QtBcNOn6ZlZHnjonACvsu2gEH"
consumer_secret = "w9lyTzQxP4rTFj8VnUhWRwDZmxWUjKcTtVqZrNiWvlPXOnZp3F"

def get_oauth_session():
    """Initialize OAuth session and get tokens"""
    logger.info("Starting OAuth process...")
    
    # Get request token with PIN-based OAuth flow
    request_token_url = "https://api.twitter.com/oauth/request_token"
    oauth = OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        callback_uri='oob'
    )

    fetch_response = oauth.fetch_request_token(request_token_url)
    resource_owner_key = fetch_response.get("oauth_token")
    resource_owner_secret = fetch_response.get("oauth_token_secret")

    # Get authorization
    base_authorization_url = "https://api.twitter.com/oauth/authorize"
    authorization_url = oauth.authorization_url(base_authorization_url)
    logger.info("Please go here and authorize: %s" % authorization_url)
    logger.info("After authorizing, you'll see a PIN number. Copy it and paste it below.")
    verifier = input("Paste the PIN here: ")

    # Get the access token
    access_token_url = "https://api.twitter.com/oauth/access_token"
    oauth = OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret,
        verifier=verifier,
    )
    oauth_tokens = oauth.fetch_access_token(access_token_url)

    return oauth_tokens

def delete_tweets(oauth_tokens):
    """Delete tweets maximizing rate limits usage"""
    access_token = oauth_tokens["oauth_token"]
    access_token_secret = oauth_tokens["oauth_token_secret"]
    user_id = oauth_tokens["user_id"]
    
    # Create OAuth session with access tokens
    oauth = OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret
    )

    daily_deletion_limit = 17  # Free tier: 17 deletions per 24h
    deletions_today = 0
    total_deletions = 0
    
    while True:
        try:
            # Check if we've hit the daily limit
            if deletions_today >= daily_deletion_limit:
                wait_time = 24 * 60 * 60  # 24 hours in seconds
                next_time = datetime.now() + timedelta(seconds=wait_time)
                logger.info(f"Daily limit reached. Total deletions: {total_deletions}")
                logger.info(f"Waiting until {next_time.strftime('%Y-%m-%d %H:%M:%S')}...")
                time.sleep(wait_time)
                deletions_today = 0

            # Get tweets (1 request per 15 minutes limit)
            tweets_url = f"https://api.twitter.com/2/users/{user_id}/tweets?max_results=100"
            response = oauth.get(tweets_url)
            
            if response.status_code != 200:
                raise Exception(
                    "Request returned an error: {} {}".format(response.status_code, response.text)
                )

            tweets = response.json()
            
            if not tweets.get('data'):
                logger.info(f"No more tweets found! Total deleted: {total_deletions}")
                break

            logger.info(f"Found {len(tweets['data'])} tweets")
            
            # Process tweets
            for tweet in tweets['data']:
                if deletions_today >= daily_deletion_limit:
                    break
                    
                tweet_id = tweet['id']
                
                # Delete the tweet
                delete_url = f"https://api.twitter.com/2/tweets/{tweet_id}"
                response = oauth.delete(delete_url)
                
                if response.status_code != 200:
                    logger.error(f"Failed to delete tweet {tweet_id}: {response.text}")
                    continue
                    
                deletions_today += 1
                total_deletions += 1
                logger.info(f"Deleted tweet {tweet_id} ({deletions_today}/17 today, {total_deletions} total)")

            # Wait 15 minutes before next GET request
            next_fetch = datetime.now() + timedelta(minutes=15)
            logger.info(f"Waiting until {next_fetch.strftime('%H:%M:%S')} for next batch...")
            time.sleep(15 * 60)  # 15 minutes in seconds
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            logger.info("Waiting 5 minutes before retry...")
            time.sleep(5 * 60)

def main():
    try:
        # Get OAuth tokens
        oauth_tokens = get_oauth_session()
        
        # Start deletion
        logger.info("Starting tweet deletion...")
        delete_tweets(oauth_tokens)
            
    except KeyboardInterrupt:
        logger.info("\nProcess interrupted by user. Exiting...")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")

if __name__ == "__main__":
    main()