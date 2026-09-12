"""
Download public NAIA Women's Wrestling team rosters from Trackwrestling.
Extracts wrestler names, schools, weight classes, placements, points scored,
and tournament records for the 2025 and 2026 NAIA National Championships.
"""

import subprocess
import re
import csv
import os
import time
from bs4 import BeautifulSoup
from download_naia_data import get_tw_session

def fetch_team_rosters(event_id, event_name, season):
    print(f"Connecting to Trackwrestling session for {event_name}...")
    tim, session, cookie_file = get_tw_session(event_id)
    if not tim or not session:
        print(f"Failed to create session for {event_name}")
        return []

    url = f"https://www.trackwrestling.com/opentournaments/TeamResults.jsp?TIM={tim}&twSessionId={session}"
    res = subprocess.check_output(['curl', '-s', '-c', cookie_file, '-b', cookie_file, url]).decode('utf-8', errors='ignore')
    soup = BeautifulSoup(res, 'html.parser')
    select = soup.find('select')
    if not select:
        print(f"No team dropdown found for {event_name}")
        return []

    teams = [(opt.get('value'), opt.text.strip()) for opt in select.find_all('option') if opt.get('value')]
    print(f"Found {len(teams)} teams for {event_name}. Extracting rosters...")

    roster_records = []
    for tid, tname in teams:
        turl = f"{url}&teamBox={tid}"
        tres = subprocess.check_output(['curl', '-s', '-c', cookie_file, '-b', cookie_file, turl]).decode('utf-8', errors='ignore')
        tsoup = BeautifulSoup(tres, 'html.parser')
        text = tsoup.get_text()

        sections = re.split(r'NAIA\s+(\d+)\s*\n', text)
        for i in range(1, len(sections), 2):
            wc = sections[i].strip()
            body = sections[i+1]
            head_m = re.match(r'\s*(.+?)\'s place is (.*?) and has scored ([\d\.]+) team points', body)
            if head_m:
                w_name = head_m.group(1).strip()
                place_raw = head_m.group(2).strip()
                place = "Did not place" if place_raw == "unknown" else place_raw
                points = float(head_m.group(3).strip())

                wins = len(re.findall(re.escape(w_name) + r'\s*\([^)]*\)\s*won by', body))
                losses = len(re.findall(r'won by\s+.*?over\s+' + re.escape(w_name), body))

                roster_records.append({
                    'season': season,
                    'event_name': event_name,
                    'event_id': event_id,
                    'school': tname,
                    'wrestler_name': w_name,
                    'weight_class': wc,
                    'place': place,
                    'points_scored': points,
                    'wins': wins,
                    'losses': losses,
                    'matches_wrestled': wins + losses
                })
        time.sleep(0.15)

    print(f"Completed {event_name}: {len(roster_records)} wrestlers across {len(teams)} teams.")
    return roster_records

def main():
    os.makedirs('data', exist_ok=True)
    events = [
        ('954958132', "2026 NAIA Women's National Championships", 2026),
        ('923487132', "2025 NAIA Women's National Championships", 2025),
    ]

    all_rosters = []
    for eid, ename, season in events:
        rosters = fetch_team_rosters(eid, ename, season)
        all_rosters.extend(rosters)

        season_file = f"data/naia_women_rosters_{season}.csv"
        with open(season_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'season', 'event_name', 'event_id', 'school', 'wrestler_name',
                'weight_class', 'place', 'points_scored', 'wins', 'losses', 'matches_wrestled'
            ])
            writer.writeheader()
            writer.writerows(rosters)
        print(f"Saved {len(rosters)} rows to {season_file}")

    combined_file = "data/naia_women_team_rosters.csv"
    with open(combined_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'season', 'event_name', 'event_id', 'school', 'wrestler_name',
            'weight_class', 'place', 'points_scored', 'wins', 'losses', 'matches_wrestled'
        ])
        writer.writeheader()
        writer.writerows(all_rosters)
    print(f"Saved total {len(all_rosters)} rows to {combined_file}")

if __name__ == '__main__':
    main()
