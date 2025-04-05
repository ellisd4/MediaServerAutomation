import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

collection_name = "Romantic Comedies" ## Desired name of the collection -- Update this as necessary
required_genres = ["Comedy", "Romance"] ## Both of these genres are required
excluded_genres = ["Animation"] ## Exclude these genres
excluded_actors = ["Shirley Temple"] ## Fixed name - was incorrectly "Shirley Ellison"

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
    "IncludeItemTypes": "Movie",  # Only include movies
    "parentId": embyLibraryParentID
}

# Debug information
print(f"Base URL: {base_url}")
print(f"User ID: {user_id}")
print(f"Library Parent ID: {embyLibraryParentID}")

# Send the request to the Emby server to search for movies
try:
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
        users_endpoint = f"{base_url}/Users/{user_id}/Items/{collection_id}/Items"
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


# Creates a new collection if it doesn't exist, updates if it does (with complete replacement)
def create_or_update_collection(collection_name, item_ids_to_add, excluded_ids):
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
        else:
            # Create a new collection if it doesn't exist
            # Important: Need to include at least one movie ID when creating the collection
            if not item_ids_to_add:
                print("No movies found to create collection with. Cannot create empty collection.")
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
        
        # Now add all the movies to the collection (for both new and existing collections)
        if collection_id and item_ids_to_add:
            print(f"Adding {len(item_ids_to_add)} movies to collection in batches")
            
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
                                         "RomComs.jpg")
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

# Hard-coded exclusion list for specifically troublesome movies
hard_excluded_titles = ["Baby Take a Bow", "Elemental", "Hercules"]

# Function to check if a movie should be excluded based on path or metadata
def should_exclude(item_details, movie_id):
    # Get movie title, path, and overview
    movie_name = item_details.get('Name', '')
    path = item_details.get('Path', '')
    overview = item_details.get('Overview', '')
    
    # Hard exclusion check - explicitly exclude certain titles by name
    if movie_name in hard_excluded_titles:
        print(f"Excluding movie: {movie_name} | Reason: Hard-coded exclusion")
        return True
    
    # Check if any excluded genres are present
    genres = item_details.get('Genres', [])
    if any(genre in excluded_genres for genre in genres):
        print(f"Excluding movie: {movie_name} | Reason: Contains excluded genre")
        return True
        
    # Check if both required genres are missing
    if not all(genre in genres for genre in required_genres):
        print(f"Excluding movie: {movie_name} | Reason: Missing required genres")
        return True
    
    # Perform case-insensitive check for excluded actors in the path
    for actor in excluded_actors:
        if path and actor.lower() in path.lower():
            print(f"Excluding movie: {movie_name} | Reason: Excluded actor in path")
            return True
    
    # Check if excluded actor name is in the title or overview (case-insensitive)
    for actor in excluded_actors:
        if actor.lower() in movie_name.lower() or (overview and actor.lower() in overview.lower()):
            print(f"Excluding movie: {movie_name} | Reason: Excluded actor in title/overview")
            return True
    
    # Check People list for excluded actors
    people = item_details.get('People', [])
    for person in people:
        for actor in excluded_actors:
            if actor.lower() in person.get('Name', '').lower():
                print(f"Excluding movie: {movie_name} | Reason: Cast includes {actor}")
                return True
    
    return False  # Not excluded

# Main execution flow
print(f"Starting Romantic Comedies Collection update process...")

# Process all movies to determine what should be in the collection
romcom_item_ids = []
excluded_count = 0
excluded_actor_count = 0
processed_count = 0
total_movies = len(items)

# Lists to track exclusions for validation
excluded_ids = []
excluded_movies = []
excluded_actor_ids = []

print(f"Processing {total_movies} movies to check genre and exclusion criteria...")
for item in items:
    processed_count += 1
    if processed_count % 50 == 0:
        print(f"Processed {processed_count}/{total_movies} movies...")
        
    try:
        movie_id = item['Id']
        item_details = requests.get(f"{base_url}/users/{user_id}/items/{movie_id}", headers=headers).json()
        movie_name = item_details.get('Name', 'Unknown Title')
        genres = item_details.get('Genres', [])
        
        # Comprehensive exclusion check
        if should_exclude(item_details, movie_id):
            # Keep track of exclusions
            excluded_ids.append(movie_id)
            excluded_movies.append(movie_name)
            excluded_count += 1
            
            # Track actor-based exclusions separately
            people = item_details.get('People', [])
            for person in people:
                for actor in excluded_actors:
                    if actor.lower() in person.get('Name', '').lower():
                        excluded_actor_ids.append(movie_id)
                        excluded_actor_count += 1
                        break
            
            continue
            
        # If we get here, movie should be included
        print(f"Adding movie: {movie_name} | Genres: {', '.join(genres)}")
        romcom_item_ids.append(movie_id)
            
    except Exception as e:
        print(f"Error processing item {item.get('Id')}: {str(e)}")

print(f"Found {len(romcom_item_ids)} romantic comedy movies")
print(f"Excluded {excluded_count} movies due to exclusion criteria")
print(f"Excluded {excluded_actor_count} movies specifically due to excluded actors")

# Final validation to ensure all exclusions are properly applied
print("Performing final validation to ensure all exclusions are properly applied...")
final_romcom_list = []
exclusion_found_in_list = 0

for movie_id in romcom_item_ids:
    if movie_id in excluded_ids:
        exclusion_found_in_list += 1
        print(f"WARNING: Excluded movie with ID {movie_id} was still in the list - removing it")
        continue
    
    # Double-check that the movie should be included
    try:
        item_details = requests.get(f"{base_url}/users/{user_id}/items/{movie_id}", headers=headers).json()
        movie_name = item_details.get('Name', 'Unknown Title')
        
        if should_exclude(item_details, movie_id):
            exclusion_found_in_list += 1
            print(f"WARNING: Movie {movie_name} should be excluded but was in the list - removing it")
            continue
            
        final_romcom_list.append(movie_id)
    except Exception as e:
        print(f"Error in final validation for movie {movie_id}: {str(e)}")
        # Include the movie if there's an error checking it, to be safe
        final_romcom_list.append(movie_id)

if exclusion_found_in_list > 0:
    print(f"Found and removed {exclusion_found_in_list} excluded movies during final validation")
    print(f"Final romantic comedy movie count: {len(final_romcom_list)}")
else:
    print("Final validation complete - no excluded movies found in the list")
    final_romcom_list = romcom_item_ids

if final_romcom_list:
    collection_id = create_or_update_collection(collection_name, final_romcom_list, excluded_ids)
    if collection_id:
        print(f"Romantic Comedies collection updated successfully!")
        print(f"Collection now contains {len(final_romcom_list)} romantic comedy movies")
else:
    print("No romantic comedy movies found. Collection will not be created/updated.")