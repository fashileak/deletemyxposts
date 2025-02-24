"""
X (Twitter) Account Cleanup Tool

This script deletes tweets from your X account. Features:
- Async tweet deletion for better performance
- Dry-run mode to preview what will be deleted
- Configurable tweet deletion limit
- Detailed logging
"""

import tweepy
import logging
import asyncio
from tweepy.asynchronous import AsyncClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Twitter API credentials
# Get these from https://developer.twitter.com/
api_key = "JqCibVB17sv2I5XXT5dufYxPw"
api_secret = "TlOUEjbVIqBMq0I2hV1r9fVoYORg4HljACR4AXb0x8RPiXlzYk"
access_token = "524111137-yyJOAzTfD396xQ4gXXAIuOSW1iDNkvSoQ1VxL86C"  
access_token_secret = "5ngXsFzdmDXrMqSu2aynaXoftE7MY2dUcbF3ZJdS4cW1U"

# Initial auth check using legacy API
auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
api = tweepy.API(auth)

# Verify connection
try:
    api.verify_credentials()
    logger.info("Connected to your account!")
except Exception as e:
    logger.error("Error: %s", e)
    exit()

async def delete_tweets(limit=None, dry_run=False):
    """
    Asynchronously delete tweets from the authenticated user's timeline.

    Args:
        limit (int, optional): Maximum number of tweets to delete. 
            If None, will attempt to delete all available tweets.
        dry_run (bool, optional): If True, simulates deletion without actually
            deleting tweets. Defaults to False.

    Returns:
        int: Number of tweets processed (deleted in live mode, or would be deleted in dry-run mode)

    Note:
        The Twitter API limits the number of tweets that can be fetched to the
        most recent 3200 tweets. To delete older tweets, the script needs to
        be run multiple times as newer tweets are deleted.
    """
    deleted_count = 0
    client = AsyncClient(
        bearer_token=None,  # We're using OAuth 1.0a
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )
    
    action = "Would delete" if dry_run else "Deleting"
    logger.info("Starting tweet deletion in %s mode", "dry-run" if dry_run else "live")
    
    try:
        # Get user ID - updated to handle v2 response correctly
        user = await client.get_me()
        if not user.data:
            logger.error("Failed to get user information")
            return 0
            
        logger.info("Connected as user: %s", user.data.username)  # Changed from user.username to user.data.username
        
        # Fetch tweets using Twitter API v2
        response = await client.get_users_tweets(
            user.data.id,  # Changed from user.id to user.data.id
            max_results=100,
            tweet_fields=['text']
        )
        
        if not response or not response.data:
            logger.info("No tweets found to delete")
            return 0
            
        # Process tweets in parallel
        delete_tasks = []
        for tweet in response.data:
            if limit and deleted_count >= limit:
                logger.info("Reached deletion limit of %d tweets", limit)
                break
                
            deleted_count += 1
            logger.info("%s tweet (%d/%s): %s", 
                       action,
                       deleted_count, 
                       str(limit) if limit else "all", 
                       tweet.text)
                
            if not dry_run:
                delete_tasks.append(client.delete_tweet(tweet.id))
        
        if delete_tasks:
            # Execute all deletion tasks concurrently
            await asyncio.gather(*delete_tasks, return_exceptions=True)
        
        status = "Would have deleted" if dry_run else "Deleted"
        logger.info("Process complete. %s %d tweets.", status, deleted_count)
        return deleted_count
        
    except Exception as e:
        logger.error("Error during tweet deletion: %s", e)
        return deleted_count

async def main():
    """
    Main entry point for the script.
    Configure the limit and dry_run parameters here before running.
    """
    # Configuration
    limit = None  # Set to None to delete all available tweets
    dry_run = True  # Set to False to actually delete tweets
    
    await delete_tweets(limit, dry_run)

if __name__ == "__main__":
    asyncio.run(main()) 