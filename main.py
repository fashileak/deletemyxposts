from requests_oauthlib import OAuth1Session
import os
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# X API credentials
consumer_key = "QtBcNOn6ZlZHnjonACvsu2gEH"
consumer_secret = "w9lyTzQxP4rTFj8VnUhWRwDZmxWUjKcTtVqZrNiWvlPXOnZp3F"

logger.info("Starting OAuth process...")
logger.info(f"Consumer key length: {len(consumer_key)}")

# Get request token with PIN-based OAuth flow
request_token_url = "https://api.twitter.com/oauth/request_token"
oauth = OAuth1Session(
    consumer_key,
    client_secret=consumer_secret,
    callback_uri='oob'  # This specifies PIN-based auth
)

try:
    fetch_response = oauth.fetch_request_token(request_token_url)
    resource_owner_key = fetch_response.get("oauth_token")
    resource_owner_secret = fetch_response.get("oauth_token_secret")
    logger.info("Got OAuth token: %s" % resource_owner_key)

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

    access_token = oauth_tokens["oauth_token"]
    access_token_secret = oauth_tokens["oauth_token_secret"]
    user_id = oauth_tokens["user_id"]
    
    logger.info("Successfully obtained access tokens!")

    # Create new OAuth session with the access tokens
    oauth = OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret
    )

    # First, get user's tweets
    tweets_url = f"https://api.twitter.com/2/users/{user_id}/tweets"
    response = oauth.get(tweets_url)
    
    if response.status_code != 200:
        raise Exception(
            "Request returned an error: {} {}".format(response.status_code, response.text)
        )

    tweets = response.json()
    logger.info("Found tweets: %s" % json.dumps(tweets, indent=4))

    # Now we can delete a specific tweet
    if tweets.get('data'):
        tweet_id = tweets['data'][0]['id']  # Get the first tweet's ID
        logger.info(f"Attempting to delete tweet ID: {tweet_id}")
        
        # Delete the tweet
        delete_url = f"https://api.twitter.com/2/tweets/{tweet_id}"
        response = oauth.delete(delete_url)
        
        if response.status_code != 200:
            raise Exception(
                "Request returned an error: {} {}".format(response.status_code, response.text)
            )
            
        logger.info("Successfully deleted tweet!")
        logger.info(response.json())

except ValueError as e:
    logger.error("Error with credentials: %s" % str(e))
    logger.error("Please verify your API Key and Secret are correct.")
except Exception as e:
    logger.error("Unexpected error: %s" % str(e))