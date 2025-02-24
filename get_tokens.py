from requests_oauthlib import OAuth1Session
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

consumer_key = os.getenv('CONSUMER_KEY')
consumer_secret = os.getenv('CONSUMER_SECRET')

# Get request token with PIN-based OAuth flow
request_token_url = "https://api.twitter.com/oauth/request_token?oauth_callback=oob"
oauth = OAuth1Session(consumer_key, client_secret=consumer_secret)

try:
    fetch_response = oauth.fetch_request_token(request_token_url)
    resource_owner_key = fetch_response.get('oauth_token')
    resource_owner_secret = fetch_response.get('oauth_token_secret')

    # Get authorization
    base_authorization_url = "https://api.twitter.com/oauth/authorize"
    authorization_url = oauth.authorization_url(base_authorization_url)
    print('\n1. Go to this URL:\n', authorization_url)
    print('\n2. Authorize the app and copy the PIN\n')
    verifier = input('3. Enter the PIN here: ')

    # Get the access token
    access_token_url = "https://api.twitter.com/oauth/access_token"
    oauth = OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret,
        verifier=verifier
    )
    oauth_tokens = oauth.fetch_access_token(access_token_url)

    print('\nAdd these to your .env file:')
    print('------------------------')
    print(f"CONSUMER_KEY={consumer_key}")
    print(f"CONSUMER_SECRET={consumer_secret}")
    print(f"ACCESS_TOKEN={oauth_tokens['oauth_token']}")
    print(f"ACCESS_TOKEN_SECRET={oauth_tokens['oauth_token_secret']}")
    print('------------------------')

except Exception as e:
    print(f'Error: {str(e)}') 