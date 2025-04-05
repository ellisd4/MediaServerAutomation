import requests
import json

collection_name = "Disney Collection" ## Desired name of the collection -- Update this as necessary
desired_studios = ["Disney", "Marvel", "Lucasfilm"] ## Array of studios to search for -- Add or Remove as necessary
desired_rating = ["G", "PG"] ## Desired Content Rating to search for -- Updated as necessary

base_url = "http://localhost:8096" ## Emby server URL
api_key = "<api_key_here>" ## Emby API Key Generated in Server Settings
userID= "<userID_GUID_here>" ## Emby User ID GUID -- Obtained by going to your (admin user) Emby Profile in a web browser and looking at the URL. It will be the last number in the URL.
embyLibraryParentID = "<libraryParentID>" ## Emby Library Parent ID -- Obtained by going to your Emby Library in a web browser and looking at the URL. It will be the last number in the URL.

headers = {
    'X-MediaBrowser-Token': api_key,
    'Accept': 'application/json',
}

params = {
    "Recursive": True,
    "MediaTypes": "Video",
    "parentId": embyLibraryParentID
}

# Send the request to the Emby server to search for music
response = requests.get(base_url + "/Items", headers=headers, params=params)
items = response.json()["Items"]
#print(items)


# Check if the Collection already exists
def create_or_update_collection(collection_name, item_ids_to_add):
    collection_exists = False

    collection_response = requests.get(f"{base_url}/users/{userID}/items?Recursive=true&IncludeItemTypes=boxset", headers=headers)
    if collection_response.status_code == 200:
        collections = collection_response.json()["Items"]
        #print(collections)
        for collection in collections:
            if collection["Name"] == collection_name:
                print("Found existing collection")
                collection_exists = True
                collection_id = collection["Id"]
                break

    # If the collection doesn't exist, create it
    if not collection_exists:
        collection_params = {
            'Name': collection_name,
            'IsLocked': False,
            'ParentId': embyLibraryParentID,
            'Ids': item_ids_to_add
        }
        create_collection_response = requests.post(base_url + "/Collections", headers=headers, params=collection_params)
        print(create_collection_response)
    else:
        collection_update_params = {
            'Ids': item_ids_to_add
        }
        print(collection_update_params)
        collection_update_response = requests.post(base_url + "/Collections/" + collection_id + "/Items", headers=headers, params=collection_update_params)
        print(collection_update_response)

item_ids_to_add = []
for item in items:
    item_details_requrest = requests.get(f"{base_url}/users/{userID}/items/{item['Id']}", headers=headers)
    item_details = item_details_requrest.json()
    #print(item_details)
    if ('Studios' in item_details) and ('OfficialRating' in item_details):
        for studio in item_details['Studios']:
            if any(any(desired_studio in studio['Name'] for desired_studio in desired_studios) for studio in item_details['Studios']):
                if item_details['OfficialRating'] in desired_rating:
                    print(f"Adding item with Name: {item_details['Name']} and rating: {item_details['OfficialRating']}")
                    item_ids_to_add.append(item['Id'])
                    
# After the loop, deduplicate the list of IDs    
item_ids_to_add = list(set(item_ids_to_add))
print(item_ids_to_add)
create_or_update_collection(collection_name, item_ids_to_add)