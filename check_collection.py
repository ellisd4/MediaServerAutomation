import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

collection_name = "Unwatched Movies"  # Collection to check

# Get configuration from environment variables
base_url = os.getenv("EMBY_SERVER_URL")
api_key = os.getenv("EMBY_API_KEY")
username = os.getenv("EMBY_USER_ID")

headers = {
    'X-MediaBrowser-Token': api_key,
    'Accept': 'application/json',
}

# Get admin user ID
admin_user_id = None
try:
    users_response = requests.get(f"{base_url}/Users", headers=headers)
    users = users_response.json()
    
    for user in users:
        if user.get("Name", "").lower() == username.lower():
            admin_user_id = user.get("Id")

            print(f"Found admin user ID: {admin_user_id}")
            break
    
    if not admin_user_id:
        print(f"Error: Could not find admin user ID")
        exit(1)
except Exception as e:
    print(f"Error getting user IDs: {str(e)}")
    exit(1)

# Find collection ID
collection_id = None
try:
    collection_response = requests.get(f"{base_url}/users/{admin_user_id}/items?Recursive=true&IncludeItemTypes=boxset", headers=headers)
    if collection_response.status_code == 200:
        collections = collection_response.json().get("Items", [])
        print(f"Found {len(collections)} collections")
        for collection in collections:
            if collection.get("Name") == collection_name:
                collection_id = collection.get("Id")
                print(f"Found collection: {collection_name} with ID: {collection_id}")
                break
except Exception as e:
    print(f"Error finding collection: {str(e)}")
    exit(1)

if not collection_id:
    print(f"Collection '{collection_name}' not found")
    exit(1)

# Get all movies in the collection using different API endpoint
try:
    # Try using the Items endpoint first
    movies_response = requests.get(
        f"{base_url}/Users/{admin_user_id}/Items",
        headers=headers,
        params={
            "ParentId": collection_id,
            "Recursive": True,
            "IncludeItemTypes": "Movie",
            "Fields": "Path,Overview,People",
            "Limit": 2000  # Large limit to get all items
        }
    )
    
    if movies_response.status_code == 200:
        movies = movies_response.json().get("Items", [])
        print(f"Found {len(movies)} movies in collection")
        
        # Create a list of movies that contain "Shirley Temple" in their path or metadata
        shirley_temple_movies = []
        
        for movie in movies:
            movie_name = movie.get('Name', '')
            path = movie.get('Path', '')
            overview = movie.get('Overview', '')
            
            has_shirley = False
            reason = []
            
            # Check path
            if path and "shirley temple" in path.lower():
                has_shirley = True
                reason.append("path contains 'Shirley Temple'")
            
            # Check title and overview
            if "shirley temple" in movie_name.lower():
                has_shirley = True
                reason.append("title contains 'Shirley Temple'")
                
            if overview and "shirley temple" in overview.lower():
                has_shirley = True
                reason.append("overview contains 'Shirley Temple'")
            
            # Check people
            people = movie.get('People', [])
            for person in people:
                if person.get('Name', '').lower() == "shirley temple":
                    has_shirley = True
                    reason.append("stars Shirley Temple")
                    break
            
            if has_shirley:
                shirley_temple_movies.append({
                    "name": movie_name,
                    "id": movie.get("Id"),
                    "path": path,
                    "reason": reason
                })
        
        # Print movies with Shirley Temple
        if shirley_temple_movies:
            print("\n=== SHIRLEY TEMPLE MOVIES FOUND IN COLLECTION ===")
            for i, movie in enumerate(shirley_temple_movies, 1):
                print(f"{i}. {movie['name']}")
                print(f"   Path: {movie['path']}")
                print(f"   Reason: {', '.join(movie['reason'])}")
                print(f"   ID: {movie['id']}")
                print()
            print(f"Found {len(shirley_temple_movies)} Shirley Temple movies that should be excluded")
        else:
            print("No Shirley Temple movies found in the collection!")
            
    else:
        print(f"Error getting movies: {movies_response.status_code} - {movies_response.text}")
except Exception as e:
    print(f"Error getting movies: {str(e)}")
