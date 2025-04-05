import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

collection_name = "Disney Collection" ## Desired name of the collection -- Update this as necessary
desired_studios = ["Disney", "Marvel", "Lucasfilm"] ## Array of studios to search for -- Add or Remove as necessary
desired_rating = ["G", "PG"] ## Desired Content Rating to search for -- Updated as necessary

# Get configuration from environment variables
base_url = os.getenv("EMBY_SERVER_URL") ## Emby server URL
api_key = os.getenv("EMBY_API_KEY") ## Emby API Key Generated in Server Settings
username = os.getenv("EMBY_USER_ID") ## Emby username
embyLibraryParentID = os.getenv("EMBY_LIBRARY_PARENT_ID") ## Emby Library Parent ID

headers = {
    'X-MediaBrowser-Token': api_key,
    'Accept': 'application/json',
}

# First, get the user ID GUID from the username
user_id = None
try:
    users_response = requests.get(f"{base_url}/Users", headers=headers)
    users = users_response.json()
    for user in users:
        if user.get("Name", "").lower() == username.lower():
            user_id = user.get("Id")
            print(f"Found user ID: {user_id} for username: {username}")
            break
    
    if not user_id:
        print(f"Error: Could not find user ID for username: {username}")
        exit(1)
except Exception as e:
    print(f"Error getting user ID: {str(e)}")
    exit(1)

params = {
    "Recursive": True,
    "MediaTypes": "Video",
    "parentId": embyLibraryParentID
}

# Debug information
print(f"Base URL: {base_url}")
print(f"User ID: {user_id}")
print(f"Library Parent ID: {embyLibraryParentID}")

# Send the request to the Emby server to search for videos
try:
    response = requests.get(f"{base_url}/Items", headers=headers, params=params)
    if response.status_code != 200:
        print(f"Error getting items: {response.status_code} - {response.text}")
        exit(1)
    items = response.json().get("Items", [])
    print(f"Found {len(items)} items in the library")
except Exception as e:
    print(f"Error getting items: {str(e)}")
    exit(1)


# Creates a new collection if it doesn't exist, updates if it does
def create_or_update_collection(collection_name, item_ids_to_add):
    collection_exists = False
    collection_id = None

    try:
        # Check if collection exists
        collection_response = requests.get(f"{base_url}/users/{user_id}/items?Recursive=true&IncludeItemTypes=boxset", headers=headers)
        if collection_response.status_code == 200:
            collections = collection_response.json().get("Items", [])
            print(f"Found {len(collections)} collections")
            for collection in collections:
                if collection.get("Name") == collection_name:
                    print(f"Found existing collection: {collection_name}")
                    collection_exists = True
                    collection_id = collection.get("Id")
                    break

        if collection_exists:
            # Update the existing collection
            collection_update_params = {
                'Ids': ','.join(item_ids_to_add)  # Join IDs with commas
            }
            print(f"Updating collection {collection_id} with {len(item_ids_to_add)} items")
            collection_update_response = requests.post(f"{base_url}/Collections/{collection_id}/Items", headers=headers, params=collection_update_params)
            print(f"Update collection response: {collection_update_response.status_code} - {collection_update_response.text}")
        else:
            # Create a new collection
            print(f"Collection '{collection_name}' does not exist. Creating it now...")
            collection_params = {
                'Name': collection_name,
                'IsLocked': False,
                'ParentId': embyLibraryParentID,
                'Ids': ','.join(item_ids_to_add)  # Join IDs with commas
            }
            create_collection_response = requests.post(f"{base_url}/Collections", headers=headers, params=collection_params)
            print(f"Create collection response: {create_collection_response.status_code} - {create_collection_response.text}")
            
            if create_collection_response.status_code == 200:
                collection_id = create_collection_response.json().get("Id")
                print(f"Successfully created new collection with ID: {collection_id}")
        
        return collection_id
    except Exception as e:
        print(f"Error in create_or_update_collection: {str(e)}")
        return None

item_ids_to_add = []
for item in items:
    try:
        item_details_request = requests.get(f"{base_url}/users/{user_id}/items/{item['Id']}", headers=headers)
        item_details = item_details_request.json()
        
        if ('Studios' in item_details) and ('OfficialRating' in item_details):
            # Simplified studio filtering logic
            for studio in item_details['Studios']:
                if any(desired_studio in studio['Name'] for desired_studio in desired_studios):
                    if item_details['OfficialRating'] in desired_rating:
                        print(f"Adding item with Name: {item_details['Name']} and rating: {item_details['OfficialRating']}")
                        item_ids_to_add.append(item['Id'])
                        break  # Once added, no need to check other studios
    except Exception as e:
        print(f"Error processing item {item.get('Id')}: {str(e)}")
                    
# After the loop, deduplicate the list of IDs    
item_ids_to_add = list(set(item_ids_to_add))
print(f"Found {len(item_ids_to_add)} items to add to collection")
if item_ids_to_add:
    collection_id = create_or_update_collection(collection_name, item_ids_to_add)
    if collection_id:
        print(f"Collection created/updated successfully with ID: {collection_id}")
else:
    print("No items found matching the criteria. Collection will not be created/updated.")