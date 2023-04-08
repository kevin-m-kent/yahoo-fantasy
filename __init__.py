import logging
import datetime
import azure.functions as func
import requests
import xml.etree.ElementTree as ET
import os

def main(mytimer: func.TimerRequest) -> None:
    logging.info('Starting Yahoo Fantasy Sports API update function.')

    # Define the Yahoo Fantasy Sports API base URL
    BASE_URL = "https://fantasysports.yahooapis.com/fantasy/v2"

    # Define the required parameters
    GAME_KEY = "mlb" # The Yahoo Fantasy Sports game key
    LEAGUE_ID = "21429" # The Yahoo Fantasy Sports league ID
    TEAM_ID = "7" # The Yahoo Fantasy Sports team ID

    client_id = os.getenv('YAHOO_CLIENT_ID')
    client_secret = os.getenv('YAHOO_CLIENT_SECRET')

    response = requests.post('https://api.login.yahoo.com/oauth2/get_token',
                             data={'grant_type': 'client_credentials',
                                   'client_id': client_id,
                                   'client_secret': client_secret})
    ACCESS_TOKEN = response.raise_for_status()

    # Define the API endpoint URL
    url = f"{BASE_URL}/game/{GAME_KEY}/league/{LEAGUE_ID}/team/{TEAM_ID}/roster"

    # Define the request headers
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    # Send a GET request to retrieve the current roster
    response = requests.get(url, headers=headers)

    # Parse the response XML and extract the player IDs and their status
    root = ET.fromstring(response.content)
    players = root.find(".//team-roster").findall(".//player")
    player_ids = []
    player_status = {}
    for player in players:
        player_id = player.get("player_id")
        player_position = player.find(".//eligible_positions").findtext(".//position")
        player_starting_status = player.find(".//selected_position").get("is_starting")
        player_ids.append(player_id)
        player_status[player_id] = {"position": player_position, "is_starting": player_starting_status}

    # Send a GET request to retrieve the starting lineup for the current day
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    response = requests.get(f"{url};date={date}", headers=headers)

    # Parse the response XML and extract the player IDs that are starting
    root = ET.fromstring(response.content)
    starting_players = root.find(".//team-roster").findall(".//player")
    starting_player_ids = [player.get("player_id") for player in starting_players]

    # Check which players are not starting for the current day
    for player_id in player_ids:
        if player_status[player_id]["is_starting"] == "false":
            logging.info(f"Player {player_id} is not starting at {player_status[player_id]['position']}.")
            # If the player is not starting, check if there are any available substitutes
            for starting_player_id in starting_player_ids:
                if player_status[starting_player_id]["is_starting"] == "true" and player_status[starting_player_id]["position"] == player_status[player_id]["position"]:
                    logging.info(f"Substituting in player {starting_player_id} for player {player_id} at position {player_status[player_id]['position']}.")
                    # If an available substitute is found, construct a new payload
                    roster = ET.Element("roster")
                    players = ET.SubElement(roster, "players")
                    player = ET.SubElement(players, "player", {"player_id": starting_player_id})
                    starting_position = ET.SubElement(player, "selected_position", {"position": player_status[player_id]["position"], "is_starting": "true"})
                    non_starting_position = ET.SubElement(player, "selected_position", {"position": player_status[starting_player_id]["position"], "is_starting": "false"})
                    xml_data = ET.tostring(roster, encoding="unicode")
                    payload = {
                    "team": {
                    "roster": xml_data
                    }
                    }
                    logging.info(f"Constructed payload: {payload}")
                    # Send a PUT request to update the starting lineup
                    response = requests.put(url, headers=headers, json=payload)
                    logging.info(f"PUT request status code: {response.status_code}")
                    logging.info(f"PUT request response: {response.content}")

logging.info('Yahoo Fantasy Sports API update function completed.')
