import requests
import datetime
#from datetime import datetime
from datetime import timedelta, timezone

# Replace the URL and API key with your own values
url = "http://localhost:8096" ## Emby server URL
api_key = "<api_key_here>" ## Emby API Key Generated in Server Settings
userId = "<userID_GUID_here>" ## Emby User ID GUID -- Obtained by going to your (admin user) Emby Profile in a web browser and looking at the URL. It will be the last number in the URL.
musicLibraryPartentID = "<libraryParentID>" ## Emby Library Parent ID -- Obtained by going to your Emby Library in a web browser and looking at the URL. It will be the last number in the URL.
playlistName = "Recently Added"  ## Change to Desired Name
##List of items to exclude from the playlist.  Can be Partial Title Name or Artist Name
excludeItemNames = ["Candy Cane", "Mistletoe", "Rudolph", "Holly", "Nick", "Jingle", "Holiday", "Christmas", "Xmas", "Grinch", "X-mas", "Nutcracker", "Santa", "Snow", "Winter", "December", "Hanukkah", "Chanukah", "Kwanzaa", "New Year", "Noel", "Yule", "Yuletide", "Yule log", "Yul", "David Mendoza"]
numberOfDays = 90 ## Number of days from today to consider when adding music to the playlist

# Set up the request headers with the API key
headers = {
    'Accept': 'application/json',
    "X-Emby-Token": api_key
}

# Get the current date and time in UTC
now = datetime.datetime.now(timezone.utc)


# Set up the request parameters to search for music added in the last 62 days and released since the year 2000
params = {
    "Recursive": True,
    "MediaTypes": "Audio",
    "SortBy": "DateCreated",
    "SortOrder": "Descending",
    "Fields": "DateCreated",
    "parentId": musicLibraryPartentID
}

# Send the request to the Emby server to search for music
response = requests.get(url + "/Items", headers=headers, params=params)

# Check if the request was successful
if response.status_code == 200:
    # Parse the response JSON to get the list of music items
    music_items = response.json()["Items"]

    # Check if the playlist already exists
    playlist_exists = False
    playlist_params = {
    "Format": "json",
    "IncludeItemTypes": "Playlist",
    "Recursive": True
}
    playlists_response = requests.get(url + "/Items", headers=headers, params=playlist_params)
    if playlists_response.status_code == 200:
        playlists = playlists_response.json()["Items"]
        for playlist in playlists:
            if playlist["Name"] == playlistName:
                print("Found existing playlist")
                playlist_exists = True
                playlist_id = playlist["Id"]
                break

    # If the "Recently Added" playlist doesn't exist, create it
    if not playlist_exists:
        create_playlist_response = requests.post(url + "/Playlists", headers=headers, json={"Name": playlistName})
        if create_playlist_response.status_code == 200:
            playlist_id = create_playlist_response.json()["Id"]
        else:
            print("Error: Failed to create playlist")
            exit()

    # Get the existing items in the playlist
    playlist_items_response = requests.get(f"{url}/Playlists/{playlist_id}/Items", headers=headers)
    if playlist_items_response.status_code != 200:
        print("Error: Failed to retrieve playlist items")
        exit()

    # Extract the playlist items from the response
    playlist_items = playlist_items_response.json()["Items"]

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
                pass
            else:
                ## Check if music meets strict criteria
                if any(excludeItemName in music_item["Name"] or excludeItemName in music_item["Artists"] for excludeItemName in excludeItemNames):                    
                    continue
                else:
                    add_to_playlist_response = requests.post(f"{url}/Playlists/{playlist_id}/Items?UserId={userId}&Ids={music_item['Id']}", headers=headers)
                    if add_to_playlist_response.status_code != 200:
                        print(f"Error: Failed to add item {music_item['Name']} to playlist")
                    else:
                        pass
        ##Check for Old Music
        for item in playlist_items:
            if item["Id"] == music_item["Id"]:
                if difference.days >= 90:
                    remove_from_playlist_response = requests.delete(f"{url}/Playlists/{playlist_id}/Items?EntryIds={item['PlaylistItemId']}", headers=headers)
                    if remove_from_playlist_response.status_code not in [200, 204]:
                        print(f"Error: {remove_from_playlist_response.status_code} Failed to remove item {item['Name']} from playlist")
                    else:
                        print(f"Successfully removed item {item['Name']} from playlist")
                        pass
else:
    print("Error: Failed to retrieve music items from Emby server")