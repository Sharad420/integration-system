# slack.py

from typing import Any, Dict
import base64
from integrations.integration_item import IntegrationItem
import httpx
import json
import secrets
import asyncio
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv(".env")

import urllib
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

CLIENT_ID = os.getenv('HUBSPOT_CLIENT_ID', 'XXX')
CLIENT_SECRET = os.getenv('HUBSPOT_CLIENT_SECRET', 'XXX')
REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'

DISPLAY_NAME_KEYS = [
    # These are the keys that will be used to display the name of the property.
    "name", "firstname", "lastname", "title", "subject", "email", "domain", "company",
]

encoded_client_id_secret = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()
authorization_url = f'https://app-na2.hubspot.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri=http://localhost:8000/integrations/hubspot/oauth2callback'
scope = 'crm.objects.contacts.read oauth'

async def authorize_hubspot(user_id, org_id):
    # Save the state in Redis to prevent CSRF attacks and return the authorization URL.
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = json.dumps(state_data)
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', encoded_state, expire=600)

    url_encoded_state = urllib.parse.quote(encoded_state)
    return f'{authorization_url}&state={url_encoded_state}&scope={scope}'


async def oauth2callback_hubspot(request: Request):
    # TODO
    # Handle the OAuth2 call from hubspot and exchange the code for an access token. Check the state to prvent CSRF attacks. No need of PKCE.
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error'))
    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    decoded_state_json = urllib.parse.unquote(encoded_state)
    state_data = json.loads(decoded_state_json)

    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')

    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')
    
    async with httpx.AsyncClient() as client:   
        response, _ = await asyncio.gather(
            client.post(
                'https://api.hubapi.com/oauth/v1/token',
                data = {
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': REDIRECT_URI,
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                }, 
                headers = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            ),
            delete_key_redis(f'hubspot_state:{org_id}:{user_id}'),
        )
    
    await add_key_value_redis(
        f'hubspot_credentials:{org_id}:{user_id}',
        json.dumps(response.json()),
        expire=600
    )
    
    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """

    return HTMLResponse(content=close_window_script)


async def get_hubspot_credentials(user_id, org_id):
    # TODO
    # Retrieve Hubspot credentials from Redis and delete them.
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')

    return credentials

def _first_non_empty(props: Dict[str, Any], *keys):
    """Returns the first non-empty value from the properties dictionary."""
    for key in keys:
        v = props.get(key)
        if v:
            return v
    return None
    

async def create_integration_item_metadata_object(response_json):
    # TODO
    """Creates an Integration metadata object from the response."""
    props = response_json.get('properties', {})

    name = _first_non_empty(props, *DISPLAY_NAME_KEYS)
    if not name:
        name = f"{response_json.get('id','')}"

    # Parsing the dates
    def iso(ts):
        return datetime.fromisoformat(ts.replace('Z', '+00:00')) if ts else None
    
    created = iso(response_json.get('createdAt')) or iso(props.get('createdate'))
    updated = iso(response_json.get('updatedAt')) or iso(props.get('lastmodifieddate'))


    integration_item_metadata = IntegrationItem(
        id=response_json.get('id', None),
        name=name,
        creation_time=created,
        last_modified_time=updated,
        visibility=not response_json.get('archived', False),
    )

    return integration_item_metadata

async def get_items_hubspot(credentials):
    # TODO
    """Aggregates all metadata relevant for a Hubspot Integration"""
    credentials = json.loads(credentials)
    
    # Recommended to use async HTTP client instead of requests.
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.hubapi.com/crm/v3/objects/contacts",
            params={
                "archived": "false",
            },
            headers={
                "Authorization": f"Bearer {credentials.get('access_token')}",
            },
        )

    if response.status_code == 200:
        results = response.json()['results']
        list_of_integration_item_metadata = []
        for result in results:
            item = await create_integration_item_metadata_object(result)
            list_of_integration_item_metadata.append(
                item
            )

        print(list_of_integration_item_metadata)

        # Convert the list of integration items to a list of dictionaries.
        return [item.name for item in list_of_integration_item_metadata]
    else:
        print("HubSpot error", response.status_code, response.text)
        return []
