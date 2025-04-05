import requests
import datetime
import os
import json
import time
from datetime import timedelta, timezone

# Get the script directory for finding the .env file
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')

# Try to import dotenv, provide helpful error message if not available
try:
    from dotenv import load_dotenv
    # Load environment variables from .env file in the same directory as this script
    load_dotenv(dotenv_path=env_path)
    print(f"Loaded environment from: {env_path}")
except ImportError:
    print("Error: The 'python-dotenv' module is not installed.")
    print("Please install it with: pip install python-dotenv")
    print("Alternatively, you can set environment variables manually.")
    # Continue without dotenv, using fallback values
    load_dotenv = lambda *args, **kwargs: None  # Create a dummy function to avoid errors

# Get configuration from environment variables with fallbacks for non-sensitive values
url = os.getenv("EMBY_SERVER_URL")  # Emby server URL
api_key = os.getenv("EMBY_API_KEY")  # Emby API Key Generated in Server Settings
user_name = os.getenv("EMBY_USER_ID")  # Emby User ID or username
musicLibraryPartentID = os.getenv("EMBY_MUSIC_LIBRARY_ID")  # Emby Library Parent ID
playlistName = os.getenv("PLAYLIST_NAME", "Recently Added")  # Default name if not specified in .env
numberOfDays = int(os.getenv("NUMBER_OF_DAYS"))  # Number of days from today
verbose_logging = os.getenv("VERBOSE_LOGGING", "false").lower() == "true"
max_retries = int(os.getenv("MAX_RETRIES", "3"))

# Check if required environment variables are set
required_vars = ["EMBY_API_KEY", "EMBY_USER_ID", "EMBY_MUSIC_LIBRARY_ID"]
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please add them to your .env file or set them as environment variables")
    exit(1)

# Load exclude list from environment variable or use default
exclude_items_str = os.getenv("EXCLUDE_ITEMS", "Candy Cane,Mistletoe,Rudolph,Holly,Nick,Jingle,Holiday,Christmas,Xmas,Grinch,X-mas,Nutcracker,Santa,Snow,Winter,December,Hanukkah,Chanukah,Kwanzaa,New Year,Noel,Yule,Yuletide,Yule log,Yul,David Mendoza")
excludeItemNames = [item.strip() for item in exclude_items_str.split(",")]

# Check if we should delete all playlists for cleanup
delete_all_playlists = os.getenv("DELETE_ALL_PLAYLISTS", "false").lower() == "true"

# Set up the request headers with the API key
headers = {
    'Accept': 'application/json',
    "X-Emby-Token": api_key
}

# Get the current date and time in UTC
now = datetime.datetime.now(timezone.utc)

# Helper function for logging with verbosity control
def log(message, always=False):
    if always or verbose_logging:
        print(message)

# Helper function to make requests with retries
def make_request(method, endpoint, expected_codes=None, **kwargs):
    if expected_codes is None:
        expected_codes = [200, 204]
    
    url_with_endpoint = f"{url}{endpoint}"
    retries = 0
    
    while retries < max_retries:
        try:
            if verbose_logging:
                log(f"Making {method} request to: {url_with_endpoint}")
                if kwargs.get('params'):
                    log(f"  Parameters: {kwargs.get('params')}")
                if kwargs.get('json'):
                    log(f"  JSON body: {kwargs.get('json')}")
            
            response = requests.request(method, url_with_endpoint, headers=headers, **kwargs)
            
            if response.status_code in expected_codes:
                return response
            else:
                log(f"Error: Request failed with status code {response.status_code}", True)
                log(f"  URL: {url_with_endpoint}", True)
                log(f"  Method: {method}", True)
                log(f"  Response: {response.text}", True)
                
                # If we've exhausted our retries, return the failed response
                if retries >= max_retries - 1:
                    return response
                
                # Otherwise, retry after a short delay
                retries += 1
                time.sleep(1)  # Wait a second before retrying
        except Exception as e:
            log(f"Exception occurred: {str(e)}", True)
            retries += 1
            if retries >= max_retries:
                raise
            time.sleep(1)  # Wait a second before retrying

# Function to delete a playlist by ID
def delete_playlist(playlist_id):
    response = make_request("DELETE", f"/Items/{playlist_id}")
    return response.status_code in [200, 204]

# Get the actual user ID (GUID) from the username
def get_user_id(username):
    user_response = make_request("GET", "/Users")
    if user_response.status_code == 200:
        users = user_response.json()
        for user in users:
            if user["Name"].lower() == username.lower():
                return user["Id"]
    
    log(f"Warning: Could not find user ID for username '{username}'. Will use the provided value.", True)
    return username

# Print Server connection details first
log(f"Connecting to Emby server at: {url}", True)

# Get the user ID (GUID) from the username if needed
userId = get_user_id(user_name)
log(f"Using user ID: {userId}", True)

# Set up the request parameters to search for music added in the last N days
params = {
    "Recursive": True,
    "MediaTypes": "Audio",
    "SortBy": "DateCreated",
    "SortOrder": "Descending",
    "Fields": "DateCreated",
    "parentId": musicLibraryPartentID
}

# Send the request to the Emby server to search for music
response = make_request("GET", "/Items", params=params)

# Check if the request was successful
if response.status_code == 200:
    # Parse the response JSON to get the list of music items
    music_items = response.json()["Items"]
    log(f"Found {len(music_items)} music items in library", True)

    # Check if we need to delete all playlists first (for cleanup)
    if delete_all_playlists:
        log("Deleting all existing playlists for cleanup...", True)
        # Get all playlists
        playlist_params = {
            "Format": "json",
            "IncludeItemTypes": "Playlist",
            "Recursive": True
        }
        playlists_response = make_request("GET", "/Items", params=playlist_params)
        if playlists_response.status_code == 200:
            playlists = playlists_response.json()["Items"]
            deleted_count = 0
            for playlist in playlists:
                if delete_playlist(playlist["Id"]):
                    log(f"Deleted playlist: {playlist['Name']} (ID: {playlist['Id']})")
                    deleted_count += 1
                else:
                    log(f"Failed to delete playlist: {playlist['Name']} (ID: {playlist['Id']})", True)
            log(f"Deleted {deleted_count} playlists", True)
            # Reset playlist_exists since we've just deleted everything
            playlist_exists = False
            
    # Check if the playlist already exists
    playlist_exists = False
    playlist_id = None
    playlist_params = {
        "Format": "json",
        "IncludeItemTypes": "Playlist",
        "Recursive": True
    }
    playlists_response = make_request("GET", "/Items", params=playlist_params)
    if playlists_response.status_code == 200:
        playlists = playlists_response.json()["Items"]
        for playlist in playlists:
            if playlist["Name"] == playlistName:
                log("Found existing playlist", True)
                playlist_exists = True
                playlist_id = playlist["Id"]
                break

    # If the "Recently Added" playlist doesn't exist, create it
    if not playlist_exists:
        log(f"Creating new playlist: {playlistName}", True)
        create_playlist_response = make_request("POST", "/Playlists", json={"Name": playlistName, "UserId": userId})
        if create_playlist_response.status_code == 200:
            playlist_id = create_playlist_response.json()["Id"]
            log(f"Successfully created playlist with ID: {playlist_id}", True)
        else:
            log("Error: Failed to create playlist", True)
            exit()

    # Get the existing items in the playlist
    playlist_items_response = make_request("GET", f"/Playlists/{playlist_id}/Items")
    if playlist_items_response.status_code != 200:
        log("Error: Failed to retrieve playlist items", True)
        exit()

    # Extract the playlist items from the response
    playlist_items = playlist_items_response.json()["Items"]
    log(f"Found {len(playlist_items)} existing items in playlist", True)

    # Track stats for a summary
    items_added = 0
    items_skipped = 0
    items_excluded = 0
    items_removed = 0
    items_failed = 0

    # Add the music items to the "Recently Added" playlist
    for music_item in music_items:
        music_item_date = datetime.datetime.strptime(music_item["DateCreated"][:-2] + '+00:00', '%Y-%m-%dT%H:%M:%S.%f%z')

        difference = now - music_item_date
        if difference.days < numberOfDays:
            # Check if the item is already in the playlist
            item_in_playlist = False
            for item in playlist_items:
                if item["Id"] == music_item["Id"]:
                    item_in_playlist = True
                    break

            if item_in_playlist:
                log(f"Skipping {music_item['Name']} - already in playlist")
                items_skipped += 1
            else:
                # Check if music meets strict criteria
                if any(excludeItemName.lower() in music_item["Name"].lower() for excludeItemName in excludeItemNames):
                    log(f"Excluding {music_item['Name']} - matches exclusion criteria")
                    items_excluded += 1
                    continue
                # Check if any artist in the Artists array matches exclusion criteria
                elif "Artists" in music_item and any(any(excludeItemName.lower() in artist.lower() for excludeItemName in excludeItemNames) for artist in music_item["Artists"]):
                    log(f"Excluding {music_item['Name']} - artist matches exclusion criteria")
                    items_excluded += 1
                    continue
                else:
                    log(f"Adding {music_item['Name']} to playlist")
                    
                    # Using the API endpoint with properly formatted parameters
                    add_url = f"/Playlists/{playlist_id}/Items"
                    add_params = {
                        "UserId": userId,
                        "Ids": music_item['Id']
                    }
                    
                    add_to_playlist_response = make_request("POST", add_url, params=add_params)
                    
                    if add_to_playlist_response.status_code != 200:
                        # Try a different approach with a comma-separated list to ensure proper format
                        log(f"First attempt failed, trying alternative approach...", True)
                        # Try with a JSON body instead
                        add_to_playlist_response = make_request(
                            "POST", 
                            f"/Items/{playlist_id}/PlaylistItems",
                            json={"Ids": [music_item['Id']], "UserId": userId}
                        )
                        
                    if add_to_playlist_response.status_code not in [200, 204]:
                        log(f"Error: Failed to add item {music_item['Name']} to playlist", True)
                        log(f"  Status code: {add_to_playlist_response.status_code}", True)
                        log(f"  Response: {add_to_playlist_response.text}", True)
                        items_failed += 1
                    else:
                        log(f"Successfully added {music_item['Name']} to playlist")
                        items_added += 1
        
        # Check for Old Music
        for item in playlist_items:
            if item["Id"] == music_item["Id"]:
                if difference.days >= numberOfDays:
                    log(f"Removing {item['Name']} - older than {numberOfDays} days")
                    
                    # Use the proper endpoint for playlist item removal
                    remove_from_playlist_response = make_request(
                        "DELETE", 
                        f"/Playlists/{playlist_id}/Items",
                        params={"EntryIds": item['PlaylistItemId']}
                    )
                    
                    if remove_from_playlist_response.status_code not in [200, 204]:
                        log(f"Error: {remove_from_playlist_response.status_code} Failed to remove item {item['Name']} from playlist", True)
                        items_failed += 1
                    else:
                        log(f"Successfully removed item {item['Name']} from playlist")
                        items_removed += 1
    
    # Print summary
    log("\nPlaylist Update Summary:", True)
    log(f"Items added: {items_added}", True)
    log(f"Items removed: {items_removed}", True)
    log(f"Items skipped (already in playlist): {items_skipped}", True)
    log(f"Items excluded (matched exclusion criteria): {items_excluded}", True)
    if items_failed > 0:
        log(f"Items failed: {items_failed}", True)
else:
    log(f"Error: Failed to retrieve music items from Emby server. Status code: {response.status_code}", True)
    log(f"Response: {response.text}", True)