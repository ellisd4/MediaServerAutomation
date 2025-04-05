import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Get configuration from environment variables
base_url = os.getenv("EMBY_SERVER_URL")
api_key = os.getenv("EMBY_API_KEY")
username = os.getenv("EMBY_USER_ID")
watch_status_user = "Dusty & Lara"  # The user whose watch status we want to check

headers = {
    'X-MediaBrowser-Token': api_key,
    'Accept': 'application/json',
}

movie_name_to_check = "Casper"  # The movie to check

# Get user IDs
admin_user_id = None
watch_status_user_id = None

try:
    users_response = requests.get(f"{base_url}/Users", headers=headers)
    users = users_response.json()
    
    for user in users:
        user_name = user.get("Name", "")
        if user_name.lower() == username.lower():
            admin_user_id = user.get("Id")
            print(f"Found admin user ID: {admin_user_id} for username: {username}")
        
        if user_name.lower() == watch_status_user.lower():
            watch_status_user_id = user.get("Id")
            print(f"Found watch status user ID: {watch_status_user_id} for username: {watch_status_user}")
    
    if not admin_user_id or not watch_status_user_id:
        print(f"Error: Could not find required user IDs")
        exit(1)
except Exception as e:
    print(f"Error getting user IDs: {str(e)}")
    exit(1)

# Find the movie ID
movie_id = None
try:
    params = {
        "SearchTerm": movie_name_to_check,
        "IncludeItemTypes": "Movie",
        "Recursive": True,
        "SearchFields": "Name",
        "Limit": 10
    }
    
    search_response = requests.get(f"{base_url}/Items", headers=headers, params=params)
    if search_response.status_code == 200:
        results = search_response.json().get("Items", [])
        if results:
            for item in results:
                if item.get("Name") == movie_name_to_check:
                    movie_id = item.get("Id")
                    path = item.get("Path", "")
                    print(f"Found movie: {item.get('Name')} | ID: {movie_id} | Path: {path}")
                    break
            
            if not movie_id:
                # If exact match not found, take the first result
                movie_id = results[0].get("Id")
                print(f"Exact match not found, using first result: {results[0].get('Name')} | ID: {movie_id}")
        else:
            print(f"No movies found with name: {movie_name_to_check}")
            exit(1)
    else:
        print(f"Error searching for movie: {search_response.status_code} - {search_response.text}")
        exit(1)
except Exception as e:
    print(f"Error searching for movie: {str(e)}")
    exit(1)

if not movie_id:
    print(f"Could not find movie: {movie_name_to_check}")
    exit(1)

# Check watch status for both users
for user_id, user_name in [(admin_user_id, username), (watch_status_user_id, watch_status_user)]:
    try:
        # Get user data for the specific item to check play state
        user_data_url = f"{base_url}/Users/{user_id}/Items/{movie_id}/UserData"
        user_data_response = requests.get(user_data_url, headers=headers)
        
        if user_data_response.status_code == 200:
            user_data = user_data_response.json()
            watched = user_data.get('Played', False)
            played_percentage = user_data.get('PlayedPercentage', 0)
            last_played = user_data.get('LastPlayedDate', 'Never')
            play_count = user_data.get('PlayCount', 0)
            
            print(f"\nWatch status for user '{user_name}':")
            print(f"  Marked as watched (Played): {watched}")
            print(f"  Play percentage: {played_percentage}%")
            print(f"  Play count: {play_count}")
            print(f"  Last played: {last_played}")
            
            # Debug - show full user data
            print("\nFull user data:")
            print(json.dumps(user_data, indent=2))
        else:
            print(f"\nError getting watch status for user '{user_name}': {user_data_response.status_code} - {user_data_response.text}")
    except Exception as e:
        print(f"\nError checking watch status for user '{user_name}': {str(e)}")

print("\nFinished checking watch status.")
