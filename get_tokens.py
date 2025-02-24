from requests_oauthlib import OAuth1Session
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

consumer_key = os.getenv('CONSUMER_KEY')
consumer_secret = os.getenv('CONSUMER_SECRET')

# Get request token
request_token_url = "https://api.twitter.com/oauth/request_token"
oauth = OAuth1Session(consumer_key, client_secret=consumer_secret)
fetch_response = oauth.fetch_request_token(request_token_url)

# Get authorization
base_authorization_url = "https://api.twitter.com/oauth/authorize"
authorization_url = oauth.authorization_url(base_authorization_url)
print('Please go here and authorize:', authorization_url)
verifier = input('Paste the PIN here: ')

# Get the access token
access_token_url = "https://api.twitter.com/oauth/access_token"
oauth = OAuth1Session(
    consumer_key,
    client_secret=consumer_secret,
    resource_owner_key=fetch_response.get('oauth_token'),
    resource_owner_secret=fetch_response.get('oauth_token_secret'),
    verifier=verifier
)
oauth_tokens = oauth.fetch_access_token(access_token_url)

print('\nAdd these to your .env file:')
print(f"ACCESS_TOKEN={oauth_tokens['oauth_token']}")
print(f"ACCESS_TOKEN_SECRET={oauth_tokens['oauth_token_secret']}") 