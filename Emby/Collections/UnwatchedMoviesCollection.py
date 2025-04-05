import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

collection_name = "Unwatched Movies" ## Desired name of the collection
watch_status_user = "Dusty & Lara" ## User whose watch status to check

# Get configuration from environment variables
base_url = os.getenv("EMBY_SERVER_URL") ## Emby server URL
api_key = os.getenv("EMBY_API_KEY") ## Emby API Key Generated in Server Settings
username = os.getenv("EMBY_USER_ID") ## Emby username
embyLibraryParentID = os.getenv("EMBY_LIBRARY_PARENT_ID") ## Emby Library Parent ID

headers = {
    'X-MediaBrowser-Token': api_key,
    'Accept': 'application/json',
}

# First, get user IDs we need - admin user for API access and watch status user
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
    
    if not admin_user_id:
        print(f"Error: Could not find admin user ID for username: {username}")
        exit(1)
        
    if not watch_status_user_id:
        print(f"Error: Could not find user ID for watch status username: {watch_status_user}")
        exit(1)
except Exception as e:
    print(f"Error getting user IDs: {str(e)}")
    exit(1)

params = {
    "Recursive": True,
    "MediaTypes": "Video",
    "IncludeItemTypes": "Movie",  # Only include movies
    "parentId": embyLibraryParentID
}

# Debug information
print(f"Base URL: {base_url}")
print(f"Admin User ID: {admin_user_id}")
print(f"Watch Status User ID: {watch_status_user_id}")
print(f"Library Parent ID: {embyLibraryParentID}")

# Send the request to the Emby server to search for movies
try:
    print("Retrieving all movies from library...")
    response = requests.get(f"{base_url}/Items", headers=headers, params=params)
    if response.status_code != 200:
        print(f"Error getting items: {response.status_code} - {response.text}")
        exit(1)
    items = response.json().get("Items", [])
    print(f"Found {len(items)} movies in the library")
except Exception as e:
    print(f"Error getting items: {str(e)}")
    exit(1)


# Function to get current items in a collection
def get_collection_items(collection_id):
    try:
        # Try multiple approaches to get collection items
        # Approach 1: Using Collections endpoint
        collection_items_response = requests.get(f"{base_url}/Collections/{collection_id}/Items", headers=headers)
        if collection_items_response.status_code == 200:
            items = collection_items_response.json().get("Items", [])
            print(f"DEBUG: Retrieved {len(items)} items from collection using Collections endpoint")
            return [item.get('Id') for item in items]
        else:
            print(f"DEBUG: Failed to get collection items from Collections endpoint, status code: {collection_items_response.status_code}")
            
        # Approach 2: Using Users endpoint
        users_endpoint = f"{base_url}/Users/{admin_user_id}/Items/{collection_id}/Items"
        print(f"DEBUG: Trying Users endpoint: {users_endpoint}")
        alt_response = requests.get(users_endpoint, headers=headers)
        if alt_response.status_code == 200:
            items = alt_response.json().get("Items", [])
            print(f"DEBUG: Retrieved {len(items)} items from collection using Users endpoint")
            return [item.get('Id') for item in items]
        else:
            print(f"DEBUG: Users endpoint also failed, status code: {alt_response.status_code}")
        
        # Approach 3: Using direct Items endpoint with parent filter
        items_endpoint = f"{base_url}/Items"
        params = {
            "ParentId": collection_id,
            "Recursive": True
        }
        print(f"DEBUG: Trying Items endpoint with ParentId filter")
        items_response = requests.get(items_endpoint, headers=headers, params=params)
        if items_response.status_code == 200:
            items = items_response.json().get("Items", [])
            print(f"DEBUG: Retrieved {len(items)} items from collection using Items endpoint")
            return [item.get('Id') for item in items]
        else:
            print(f"DEBUG: Items endpoint also failed, status code: {items_response.status_code}")
            
        # If we get here, we couldn't retrieve the items
        print("WARNING: Could not retrieve collection items using any method")
        return []
    except Exception as e:
        print(f"Error getting collection items: {str(e)}")
        return []


# Function to check if a movie is watched or not by the specified user
def is_watched(item_id):
    try:
        # First try the individual item UserData endpoint
        user_data_url = f"{base_url}/Users/{watch_status_user_id}/Items/{item_id}/UserData"
        user_data_response = requests.get(user_data_url, headers=headers)
        
        if user_data_response.status_code == 200:
            user_data = user_data_response.json()
            # Played is True if the movie has been watched
            return user_data.get('Played', False)
        else:
            # If the first method fails, try the alternative approach using Items API with fields
            print(f"DEBUG: First method failed with status code: {user_data_response.status_code}, trying alternative method")
            
            # Alternative method: Get the item with UserData included in fields
            item_url = f"{base_url}/Users/{watch_status_user_id}/Items/{item_id}"
            item_params = {
                "Fields": "UserData"
            }
            item_response = requests.get(item_url, headers=headers, params=item_params)
            
            if item_response.status_code == 200:
                item_data = item_response.json()
                user_data = item_data.get('UserData', {})
                is_played = user_data.get('Played', False)
                
                # Also check for play progress
                play_percentage = user_data.get('PlayedPercentage', 0)
                if play_percentage > 90:  # Consider as watched if more than 90% played
                    is_played = True
                    
                return is_played
            else:
                print(f"ERROR: Both watch status methods failed for item {item_id}")
                return False  # Default to "not watched" if both methods fail
                
    except Exception as e:
        print(f"Error checking if movie {item_id} is watched: {str(e)}")
        return False  # Assume not watched in case of error


# Function to check if a movie should be excluded based on path or metadata
def should_exclude(item_details, movie_id):
    # Get movie title, path, and overview
    movie_name = item_details.get('Name', '')
    path = item_details.get('Path', '')
    overview = item_details.get('Overview', '')
    
    # Perform case-insensitive check for "Shirley Temple" in the path
    if path and "shirley temple" in path.lower():
        return True
    
    # Check additional path fields that might contain the file location
    if item_details.get('Path', '').lower().find("shirley temple") != -1:
        return True
    
    # Check if "Shirley Temple" is in the title or overview (case-insensitive)
    if "shirley temple" in movie_name.lower() or (overview and "shirley temple" in overview.lower()):
        return True
    
    # Check People list for Shirley Temple
    people = item_details.get('People', [])
    for person in people:
        if person.get('Name', '').lower() == "shirley temple":
            return True
    
    # Directly check for UserData in the item details
    user_data = item_details.get('UserData', {})
    if user_data.get('Played', False):
        print(f"Excluding movie: {movie_name} | Reason: Marked as watched in item details")
        return True
        
    # Additional check for PlayedPercentage
    if user_data.get('PlayedPercentage', 0) > 90:
        print(f"Excluding movie: {movie_name} | Reason: Watched more than 90% ({user_data.get('PlayedPercentage')}%)")
        return True
        
    # Extra check to directly get user data
    try:
        # Try getting the item with UserData fields explicitly
        item_url = f"{base_url}/Users/{watch_status_user_id}/Items/{movie_id}"
        item_params = {
            "Fields": "UserData"
        }
        item_response = requests.get(item_url, headers=headers, params=item_params)
        
        if item_response.status_code == 200:
            item_data = item_response.json()
            user_data = item_data.get('UserData', {})
            
            # Check both Played flag and PlayedPercentage
            is_played = user_data.get('Played', False)
            play_percentage = user_data.get('PlayedPercentage', 0)
            play_count = user_data.get('PlayCount', 0)
            
            if is_played:
                print(f"Excluding movie: {movie_name} | Reason: Marked as played (direct check)")
                return True
                
            if play_percentage > 90:
                print(f"Excluding movie: {movie_name} | Reason: Watched {play_percentage}% (direct check)")
                return True
                
            if play_count > 0:
                print(f"Excluding movie: {movie_name} | Reason: Play count is {play_count} (direct check)")
                return True
    except Exception as e:
        print(f"Error in detailed watch status check for {movie_name}: {str(e)}")
    
    return False  # Not excluded


# Creates a new collection if it doesn't exist, updates if it does (with complete replacement)
def create_or_update_collection(collection_name, item_ids_to_add):
    collection_exists = False
    collection_id = None

    try:
        # Check if collection exists
        collection_response = requests.get(f"{base_url}/users/{admin_user_id}/items?Recursive=true&IncludeItemTypes=boxset", headers=headers)
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
            # For an existing collection, we'll update it by first clearing items, then adding new ones
            print(f"Updating existing collection with ID: {collection_id}")
            
            # Get existing items in the collection
            existing_items = get_collection_items(collection_id)
            print(f"Collection currently has {len(existing_items)} items")
            
            # Remove all existing items (if any)
            if existing_items:
                print(f"Removing all existing items from collection")
                success = False
                
                # Approach 1: Try using DELETE with query parameter
                try:
                    remove_params = {
                        'Ids': ','.join(existing_items)
                    }
                    remove_response = requests.delete(f"{base_url}/Collections/{collection_id}/Items", 
                                                      headers=headers,
                                                      params=remove_params)
                    
                    if remove_response.status_code in [200, 204]:
                        print(f"Successfully removed all existing items from collection using DELETE method")
                        success = True
                    else:
                        print(f"Failed to remove items using DELETE method: {remove_response.status_code} - {remove_response.text}")
                except Exception as e:
                    print(f"Error removing items using DELETE method: {str(e)}")
                
                # Approach 2: If first approach failed, try POST with IdsToRemove
                if not success:
                    try:
                        remove_body = {
                            'Ids': existing_items
                        }
                        remove_headers = headers.copy()
                        remove_headers['Content-Type'] = 'application/json'
                        
                        remove_response = requests.post(f"{base_url}/Collections/{collection_id}/Items/Delete", 
                                                       headers=remove_headers,
                                                       json=remove_body)
                        
                        if remove_response.status_code in [200, 204]:
                            print(f"Successfully removed all existing items from collection using POST method")
                            success = True
                        else:
                            print(f"Failed to remove items using POST method: {remove_response.status_code} - {remove_response.text}")
                    except Exception as e:
                        print(f"Error removing items using POST method: {str(e)}")
                
                # Approach 3: If all else fails, try removing items one by one
                if not success and len(existing_items) > 0:
                    print("Attempting to remove items one by one...")
                    removed_count = 0
                    
                    for item_id in existing_items:
                        try:
                            single_remove_params = {
                                'Ids': item_id
                            }
                            single_remove_response = requests.delete(f"{base_url}/Collections/{collection_id}/Items", 
                                                         headers=headers,
                                                         params=single_remove_params)
                            
                            if single_remove_response.status_code in [200, 204]:
                                removed_count += 1
                            else:
                                print(f"Failed to remove item {item_id}: {single_remove_response.status_code}")
                        except Exception as e:
                            print(f"Error removing item {item_id}: {str(e)}")
                    
                    print(f"Removed {removed_count}/{len(existing_items)} items individually")
                    
                    if removed_count > 0:
                        success = True
                
                if not success:
                    print("WARNING: Failed to remove existing items from collection. Will try to update with new items anyway.")
                    print("This may result in previously watched movies remaining in the collection.")
        else:
            # Create a new collection if it doesn't exist
            # Important: Need to include at least one movie ID when creating the collection
            if not item_ids_to_add:
                print("No unwatched movies found to create collection with. Cannot create empty collection.")
                return None
                
            print(f"Creating new collection '{collection_name}' with {len(item_ids_to_add)} movies...")
            
            collection_params = {
                'Name': collection_name,
                'IsLocked': False,
                'ParentId': embyLibraryParentID,
                'Ids': ','.join(item_ids_to_add[:1])  # Use first movie ID to create the collection
            }
            
            create_collection_response = requests.post(f"{base_url}/Collections", headers=headers, params=collection_params)
            print(f"Create collection response: {create_collection_response.status_code}")
            
            if create_collection_response.status_code == 200:
                collection_id = create_collection_response.json().get("Id")
                print(f"Successfully created new collection with ID: {collection_id}")
                
                # Remove first ID from the list since it was already added during creation
                item_ids_to_add = item_ids_to_add[1:]
        
        # Now add all the unwatched movies to the collection (for both new and existing collections)
        if collection_id and item_ids_to_add:
            print(f"Adding {len(item_ids_to_add)} unwatched movies to collection in batches")
            
            # Add movies in smaller batches of 20 to avoid request size limitations
            batch_size = 20
            total_added = 0
            
            for i in range(0, len(item_ids_to_add), batch_size):
                batch = item_ids_to_add[i:i+batch_size]
                total_added += len(batch)
                print(f"Adding batch {i//batch_size + 1} ({len(batch)} movies, {total_added}/{len(item_ids_to_add)} total)")
                
                collection_update_params = {
                    'Ids': ','.join(batch)
                }
                collection_update_response = requests.post(
                    f"{base_url}/Collections/{collection_id}/Items", 
                    headers=headers, 
                    params=collection_update_params
                )
                print(f"Batch update response: {collection_update_response.status_code}")
                
                # Add a small delay between batches to prevent overwhelming the server
                if i + batch_size < len(item_ids_to_add):
                    import time
                    time.sleep(1)
                    
            print(f"Finished adding all {total_added} movies to collection")
            
            # Set collection image if available
            try:
                poster_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                         "Custom Posters", 
                                         "UnwatchedMovies.png")
                if os.path.exists(poster_path):
                    print(f"Setting custom poster image for collection")
                    with open(poster_path, 'rb') as image_file:
                        image_data = image_file.read()
                        image_response = requests.post(
                            f"{base_url}/Items/{collection_id}/Images/Primary", 
                            headers={'X-MediaBrowser-Token': api_key},
                            data=image_data
                        )
                        print(f"Set collection image response: {image_response.status_code}")
            except Exception as img_error:
                print(f"Error setting collection image: {str(img_error)}")
        
        return collection_id
    except Exception as e:
        print(f"Error in create_or_update_collection: {str(e)}")
        return None


# Main execution flow
print(f"Starting Unwatched Movies Collection update process...")

# Process all movies to determine watched status
unwatched_item_ids = []
watched_count = 0
excluded_count = 0
shirley_temple_excluded = 0
processed_count = 0
total_movies = len(items)

# Collect the IDs of all Shirley Temple movies for extra validation
shirley_temple_ids = []

print(f"Processing {total_movies} movies to check watch status...")
for item in items:
    processed_count += 1
    if processed_count % 50 == 0:
        print(f"Processed {processed_count}/{total_movies} movies...")
        
    try:
        movie_id = item['Id']
        item_details = requests.get(f"{base_url}/users/{admin_user_id}/items/{movie_id}", headers=headers).json()
        movie_name = item_details.get('Name', 'Unknown Title')
        path = item_details.get('Path', '')
        
        # Explicit check for Shirley Temple in path (case-insensitive)
        if path and "shirley temple" in path.lower():
            print(f"Excluding movie: {movie_name} | Reason: Shirley Temple in path")
            shirley_temple_excluded += 1
            shirley_temple_ids.append(movie_id)
            excluded_count += 1
            continue

        # Check people for Shirley Temple
        is_shirley_temple_movie = False
        people = item_details.get('People', [])
        for person in people:
            if person.get('Name', '').lower() == "shirley temple":
                print(f"Excluding movie: {movie_name} | Reason: Stars Shirley Temple")
                shirley_temple_excluded += 1
                shirley_temple_ids.append(movie_id)
                is_shirley_temple_movie = True
                excluded_count += 1
                break
                
        if is_shirley_temple_movie:
            continue
            
        # Additional checks for other exclusion criteria
        if should_exclude(item_details, movie_id):
            excluded_count += 1
            continue
        
        # Check if the movie has been watched by user
        watched = is_watched(movie_id)
        
        if watched:
            print(f"Excluding movie: {movie_name} | Status: Watched")
            watched_count += 1
        else:
            print(f"Adding movie: {movie_name} | Status: Unwatched")
            unwatched_item_ids.append(movie_id)
            
    except Exception as e:
        print(f"Error processing item {item.get('Id')}: {str(e)}")

print(f"Found {len(unwatched_item_ids)} unwatched movies")
print(f"Found {watched_count} watched movies")
print(f"Excluded {excluded_count} movies due to other criteria")
print(f"Excluded {shirley_temple_excluded} Shirley Temple movies specifically")

# Double-check for any Shirley Temple movies that might have been missed
print("Performing final validation to ensure all Shirley Temple movies are excluded...")
final_unwatched_list = []
shirley_found_in_list = 0

for movie_id in unwatched_item_ids:
    if movie_id in shirley_temple_ids:
        shirley_found_in_list += 1
        print(f"WARNING: Shirley Temple movie with ID {movie_id} was still in the unwatched list - removing it")
        continue
    
    # Double-check the path one more time
    try:
        item_details = requests.get(f"{base_url}/users/{admin_user_id}/items/{movie_id}", headers=headers).json()
        path = item_details.get('Path', '')
        
        if path and "shirley temple" in path.lower():
            shirley_found_in_list += 1
            print(f"WARNING: Shirley Temple movie {item_details.get('Name', 'Unknown')} was still in the unwatched list - removing it")
            continue
            
        final_unwatched_list.append(movie_id)
    except Exception as e:
        print(f"Error in final validation for movie {movie_id}: {str(e)}")
        # Include the movie if there's an error checking it, to be safe
        final_unwatched_list.append(movie_id)

if shirley_found_in_list > 0:
    print(f"Found and removed {shirley_found_in_list} Shirley Temple movies during final validation")
    print(f"Final unwatched movie count: {len(final_unwatched_list)}")
else:
    print("Final validation complete - no Shirley Temple movies found in the list")
    final_unwatched_list = unwatched_item_ids

if final_unwatched_list:
    collection_id = create_or_update_collection(collection_name, final_unwatched_list)
    if collection_id:
        print(f"Unwatched Movies collection updated successfully!")
        print(f"Collection now contains {len(final_unwatched_list)} unwatched movies")
else:
    print("No unwatched movies found. Collection will not be created/updated.")