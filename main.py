import hashlib
import json

import requests
import pprint as pp
from datetime import datetime, timedelta


headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36",
    "accept": "application/json",
    "accept-language": "da-DK",
    # "cloudfront-viewer-country:": "DK",
    "content-type": "application/json",
    "cookie": "_gcl_au=1.1.1526468032.1593265615; AffCookie=Missing AffCode; TrafficType=Other Traffic; Orientation=0; _ga=GA1.2.1395112461.1593265615; _gid=GA1.2.1054331353.1593265615; OBG-MARKET=da; _gcl_aw=GCL.1593265618.Cj0KCQjw3Nv3BRC8ARIsAPh8hgLM-UiWHtUc64SjgmOl5l8xdg4nJRpjZsEYETt3Pn_oMxtCXsR_E2IaAuygEALw_wcB; _gcl_dc=GCL.1593265618.Cj0KCQjw3Nv3BRC8ARIsAPh8hgLM-UiWHtUc64SjgmOl5l8xdg4nJRpjZsEYETt3Pn_oMxtCXsR_E2IaAuygEALw_wcB; Acquisition_Status_Current=Prospect; Start_Acquisition=Prospect; Client_Status_Current=Prospect; Start_Client_Status=Prospect; Initdone=1; LoadAll=0; _gac_UA-49622648-4=1.1593265623.Cj0KCQjw3Nv3BRC8ARIsAPh8hgLM-UiWHtUc64SjgmOl5l8xdg4nJRpjZsEYETt3Pn_oMxtCXsR_E2IaAuygEALw_wcB; OBG-LOBBY=sportsbook; token=undefined; affcode=undefined; PartnerId=undefined",
    "marketcode": "da",
    "referer": "https://www.nordicbet.dk/betting/esports/league-of-legends/lol-na-lcs",
    "x-obg-channel": "Web",
    "x-obg-country-code": "DK",
    "x-obg-device": "Desktop",
    "x-obg-experiments": "ssrClientConfiguration",
    "brandid": "e6488c0f-e06e-41d7-8a59-5eda020b59ca"
}


sports_params = {
    "configurationKey": "sportsbook.category",
    "slug": "change_me!",
    "timezoneOffsetMinutes": "120",
    "excludedWidgetKeys": "sportsbook.tournament.carousel"
}
sports_api_url = "https://www.nordicbet.dk/api/sb/v1/widgets/view/v1"

competition_params = {
    "pageNumber": 1,
    "eventPhase": "Prematch",
    "maxMarketCount": 2,
    "eventSortBy": "StartDate",
    "categoryIds": 119
}
competition_api_url = "https://www.nordicbet.dk/api/sb/v1/widgets/events-table/v2?"  # Til API


def create_unique_bet_entry(_date, home_team, away_team):
    message = (_date + home_team + away_team).strip().lower()
    return hashlib.md5(message.encode('utf-8')).hexdigest()


def scrape_all_the_bets():
    """
    categoryIds = katergori såsom "esports"
    competitionIds = Liga såsom "LEC", "LCS"
    """

    historical_bets = json.loads(open("all_the_bets.json", encoding='utf-8').read())

    # For hvert sportsgren
    # Nedenstående er testet og virker
    #categories = ["esports", "badminton", "fodbold", "ishockey", "tennis", "handbold", "amerikansk-fodbold", "baseball", "basketball", "boksning", "cykling", "skak"]

    # Benytter kun denne da det ellers er for meget data..
    categories = ["esports"]
    for category in categories:
        sports_params["slug"] = category  # slug er nordicbets måde at angive category på

        if debug:
            sport_response = json.loads(open("category.json").read())
        else:
            response = requests.get(sports_api_url, headers=headers, params=sports_params)
            sport_response = json.loads(response.content)

        # For hvert liga
        competitions = sport_response["data"]["widgets"][1]["data"]["data"]["items"]
        for competition in competitions:
            competition_name = competition["label"]
            competitionId = competition["widgetRequest"]["competitionIds"][0]

            competition_params["competitionIds"] = competitionId
            competition_params["startsOnOrAfter"] = datetime.today().isoformat().replace(".", ":") + "Z"
            competition_params["startsBefore"] = (datetime.today() + timedelta(days=1, hours=1)).isoformat().replace(".", ":") + "Z"  # Kigger 1 dag og 1 time frem, og ved 1 kørsel hver 24 time vil jeg finde alle odds.

            if debug:
                competition_response = json.loads(open("competition.json").read())
            else:
                result = requests.get(competition_api_url, headers=headers, params=competition_params)
                competition_response = json.loads(result.text)

            # For hvert kamp
            game_ids = competition_response["skeleton"]["eventIds"]
            for game_id in game_ids:
                match_params = {
                    "configurationKey": "sportsbook.event",
                    "eventId": game_id
                }
                if debug:
                    game_id_response = json.loads(open("game_id.json").read())
                else:
                    result = requests.get("https://www.nordicbet.dk/api/sb/v1/widgets/view/v1", headers=headers, params=match_params,)
                    game_id_response = json.loads(result.text)

                bets = parse_nordic_bet_body(game_id_response, game_id)

                _date = bets["date"].split("T")[0]
                home_team = bets["home_team"]
                away_team = bets["away_team"]

                print(f'Processing {game_id=} for game "{home_team} vs {away_team}"')

                unique_id = create_unique_bet_entry(_date, home_team, away_team)

                # Opret evt entry for nye categories
                if category not in historical_bets:
                    historical_bets[category] = {}

                # Opret evt entry for nye ligaer
                if competition_name not in historical_bets[category]:
                    historical_bets[category][competition_name] = {}

                # Hvis der ikke er en key for _date, har vi ingen bets fra den givne dato
                if _date in historical_bets[category][competition_name]:
                    # TODO: Tjek skal være baseret på antallet af bets der er hentet. Hvis der er hentet flere end lagret, overskrives alle lagret bets.
                    if unique_id in [match["id"] for match in historical_bets[category][competition_name][_date]]:
                        print(f"Bets already scraped for entry '{unique_id}', skipping...")
                        continue

                if _date not in historical_bets[category][competition_name]:
                    historical_bets[category][competition_name][_date] = []

                # Omskriver bets fra dict med ID som ikke længere er nødvendigt, til at være list. TODO: Burde nok fjerne det ID når bet fås fra parse_nordic_bet_body()
                list_of_bets = [bet for bet in bets["bets"].values()]

                entry = {
                    "home_team": home_team,
                    "away_team": away_team,
                    "bets": list_of_bets,
                    "id": unique_id,
                }

                # Store historical bets including new ones
                historical_bets[category][competition_name][_date].append(entry)

    open("all_the_bets.json", "w", encoding='utf-8').write(json.dumps(historical_bets, indent=4))


def parse_nordic_bet_body(body, game_id):
    """ Det er MEGET vigtigt at pointere, at:
    <home_team> angiver multiplier for holdet til VENSTRE i oddsfelterne.
    <away_team> er derfor multipliers for felterne til HØJRE i oddsfelterne.

    TODO: Should handle "draw" cases (and the other ones..)
    """

    if "error" in body["data"]["widgets"][0]["data"]:
        open("tmp_error.json", "w", encoding='utf-8').write(json.dumps(body))
        raise ValueError(f"JSON body for game with ID: {game_id}: contained no data/errors occured.")

    home_team = body["data"]["widgets"][0]["data"]["data"]["event"]["participants"][0]["label"]
    away_team = body["data"]["widgets"][0]["data"]["data"]["event"]["participants"][1]["label"]

    # Vigtigt at dette tjek sker efter ovenstående, da dataen der tjekkes på ellers ikke er tilgængelig
    body_gameId = body["data"]["widgets"][1]["data"]["data"]["markets"][0]["eventId"]
    if game_id != body_gameId:
        open("debug.json", "w", encoding='utf-8').write(json.dumps(body, indent=4))
        raise ValueError(f"JSON body for game with ID: {game_id}: contains data for game with ID: {body_gameId}.")

    bets_type = body["data"]["widgets"][1]["data"]["data"]["markets"]
    bets_data = body["data"]["widgets"][1]["data"]["data"]["selections"]
    bets_date = body["data"]["widgets"][0]["data"]["data"]["event"]["startDate"]
    bets_date = bets_date.replace("Z", "")  # Mærkeligt python ikke godtager Z, da det er en del af standarden.

    bets = {
        "date": bets_date,
        "home_team": home_team,
        "away_team": away_team,
        "bets": {}
    }

    # Opretter entry for alle typer af bets ud fra ID
    for idx, bet_type in enumerate(bets_type):
        bet_id = bet_type["id"]

        bets["bets"][bet_id] = {
            "type": bet_type["label"],
            "multipliers": {},
        }

    # Udfylder det oprettede entry
    for bet_data in bets_data:
        bet_id = bet_data["marketId"]

        if bet_id not in bets["bets"]:
            raise LookupError(f"Found no bets for the multiplier with id {bet_id}")

        multiplier = bet_data["odds"]
        if bet_data["selectionTemplateId"].lower() == "home":
            bets["bets"][bet_id]["multipliers"]["home_team"] = multiplier
        elif bet_data["selectionTemplateId"].lower() == "away":
            bets["bets"][bet_id]["multipliers"]["away_team"] = multiplier
        else:
            bets["bets"][bet_id]["multipliers"][bet_data["label"]] = multiplier
    return bets


def pexit(s):
    pp.pprint(s)
    exit()


debug = False
if __name__ == "__main__":
    scrape_all_the_bets()
