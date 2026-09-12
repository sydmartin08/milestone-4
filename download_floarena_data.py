"""
Download 2023 and 2024 NAIA Women's National Championships data from FloArena.
Extracts athletes, team scores, tournament placers, match records, and team points.
"""

import urllib.request
import json
import re
import csv
import os
from collections import defaultdict

EVENTS = [
    {
        'season': 2024,
        'event_id': 'a5e77281-e231-4ead-a5a8-1142233226d8',
        'event_name': "2024 NAIA Women's National Championships",
    },
    {
        'season': 2023,
        'event_id': 'e44c8f77-5a14-445c-8d0f-84acc7c44f33',
        'event_name': "2023 NAIA Women's National Championships",
    }
]

# Placement points scale in collegiate tournament
PLACEMENT_POINTS = {
    1: 16.0,
    2: 12.0,
    3: 10.0,
    4: 9.0,
    5: 7.0,
    6: 6.0,
    7: 4.0,
    8: 3.0
}

def clean_team_name(name):
    """Normalize FloArena school names to standard project names."""
    if not name:
        return ""
    name = re.sub(r'\s*\([A-Za-z\.\s]+\)', '', name).strip()
    name = re.sub(r'^University of\s+', '', name).strip()
    name = re.sub(r'\s+University$', '', name).strip()
    name = re.sub(r'\s+College$', '', name).strip()
    return name

def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def process_season(season_info):
    season = season_info['season']
    eid = season_info['event_id']
    ename = season_info['event_name']
    print(f"\nProcessing {ename} ({season})...")

    # 1. Fetch Division and Weight Classes
    div_url = f"https://arena.flowrestling.org/bracket/{eid}"
    div_data = fetch_json(div_url)
    div_obj = div_data['response']['divisions'][0]
    div_id = div_obj['guid']
    weight_classes = div_obj['weightClasses']
    print(f"Found {len(weight_classes)} weight classes.")

    # 2. Fetch all registered athletes
    ath_url = f"https://arena.flowrestling.org/bracket/{eid}/division/{div_id}/athletes"
    ath_data = fetch_json(ath_url)
    raw_athletes = ath_data.get('response', [])
    print(f"Found {len(raw_athletes)} registered athletes.")

    # Athlete mapping: guid -> info
    athletes = {}
    for a in raw_athletes:
        guid = a['guid']
        tname = clean_team_name(a.get('team', {}).get('name', ''))
        w_class = a.get('weightClass', {}).get('name', '')
        full_name = f"{a.get('firstName', '').strip()} {a.get('lastName', '').strip()}".strip()
        athletes[guid] = {
            'guid': guid,
            'name': full_name,
            'team': tname,
            'weight_class': w_class,
            'place': 'Did not place',
            'place_num': None,
            'wins': 0,
            'losses': 0,
            'advancement_pts': 0.0,
            'bye_pts': 0.0,
            'bonus_pts': 0.0,
            'placement_pts': 0.0,
            'season': season,
            'event_name': ename,
            'event_id': eid
        }

    # 3. Fetch bouts for each weight class & placements
    placers_list = []
    for wc in weight_classes:
        wc_id = wc['guid']
        wc_name = wc['name']
        b_url = f"https://arena.flowrestling.org/bracket/{eid}/bouts/{wc_id}"
        b_data = fetch_json(b_url)
        bouts = b_data.get('response', [])

        # Extract placements
        if bouts and 'weightClass' in bouts[0] and bouts[0]['weightClass'].get('boutPools'):
            placements = bouts[0]['weightClass']['boutPools'][0].get('bracketPlacements', [])
            for p in placements:
                pw = p.get('wrestler')
                rank = p.get('placement')
                if pw and rank:
                    w_guid = pw['guid']
                    w_name = f"{pw.get('firstName', '').strip()} {pw.get('lastName', '').strip()}".strip()
                    w_team = clean_team_name(pw.get('team', {}).get('name', ''))
                    place_str = f"{rank}th" if rank not in [1, 2, 3] else {1: '1st', 2: '2nd', 3: '3rd'}[rank]
                    
                    placers_list.append({
                        'year': season,
                        'weight_class': wc_name,
                        'place': f"{place_str} Place",
                        'wrestler': w_name,
                        'team': w_team,
                        'rank': rank
                    })

                    if w_guid in athletes:
                        athletes[w_guid]['place'] = place_str
                        athletes[w_guid]['place_num'] = rank
                        athletes[w_guid]['placement_pts'] = PLACEMENT_POINTS.get(rank, 0.0)

        # Process each bout for W-L records and scoring
        for b in bouts:
            w_guid = b.get('winnerWrestlerGuid')
            if not w_guid:
                continue
            tw = b.get('topWrestler')
            bw = b.get('bottomWrestler')
            is_bye = b.get('winType') == 'BYE' or b.get('isTopBye') or b.get('isBottomBye')
            pts = float(b.get('winnerPoints') or 0.0)

            if is_bye:
                if w_guid in athletes:
                    athletes[w_guid]['bye_pts'] += pts
            else:
                if tw and bw:
                    loser_guid = bw['guid'] if tw['guid'] == w_guid else tw['guid']
                    if w_guid in athletes:
                        athletes[w_guid]['wins'] += 1
                        athletes[w_guid]['advancement_pts'] += pts
                    if loser_guid in athletes:
                        athletes[loser_guid]['losses'] += 1

    # Apply bye advancement points only if wrestler won at least 1 match
    athlete_rows = []
    for a in athletes.values():
        total_pts = a['placement_pts'] + a['advancement_pts']
        if a['wins'] > 0:
            total_pts += a['bye_pts']
        a['points_scored'] = round(total_pts, 1)
        a['record'] = f"{a['wins']}-{a['losses']}"
        a['matches_wrestled'] = a['wins'] + a['losses']
        athlete_rows.append(a)

    # Sort placers by weight class then rank
    placers_list.sort(key=lambda x: (int(x['weight_class']) if x['weight_class'].isdigit() else 0, x['rank']))

    # 4. Fetch official team scores
    ts_url = f"https://arena.flowrestling.org/event/{eid}/team-scores"
    ts_data = fetch_json(ts_url)
    raw_team_scores = ts_data.get('response', [])
    team_scores_list = []
    for ts in raw_team_scores:
        tname = clean_team_name(ts.get('team', {}).get('name', ''))
        team_scores_list.append({
            'rank': ts.get('rank'),
            'team': tname,
            'score': ts.get('score'),
            'season': season
        })

    print(f"Completed {season}: {len(athlete_rows)} athletes, {len(placers_list)} placers, {len(team_scores_list)} teams.")
    return athlete_rows, placers_list, team_scores_list

if __name__ == '__main__':
    all_new_athletes = []
    all_new_placers = []
    all_new_team_scores = []

    for event in EVENTS:
        ath_rows, placers, team_scores = process_season(event)
        all_new_athletes.extend(ath_rows)
        all_new_placers.extend(placers)
        all_new_team_scores.extend(team_scores)

        # Save individual season rosters
        season = event['season']
        season_roster_file = f"data/naia_women_rosters_{season}.csv"
        with open(season_roster_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'season', 'event_name', 'event_id', 'school', 'wrestler_name',
                'weight_class', 'place', 'points_scored', 'wins', 'losses', 'matches_wrestled'
            ])
            writer.writeheader()
            for a in ath_rows:
                writer.writerow({
                    'season': a['season'],
                    'event_name': a['event_name'],
                    'event_id': a['event_id'],
                    'school': a['team'],
                    'wrestler_name': a['name'],
                    'weight_class': a['weight_class'],
                    'place': a['place'],
                    'points_scored': a['points_scored'],
                    'wins': a['wins'],
                    'losses': a['losses'],
                    'matches_wrestled': a['matches_wrestled']
                })
        print(f"Saved {season_roster_file}")

        # Save individual season placers
        season_placers_file = f"data/naia_women_placers_{season}.csv"
        with open(season_placers_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['year', 'weight_class', 'place', 'wrestler', 'team'])
            writer.writeheader()
            for p in placers:
                writer.writerow({
                    'year': p['year'],
                    'weight_class': p['weight_class'],
                    'place': p['place'],
                    'wrestler': p['wrestler'],
                    'team': p['team']
                })
        print(f"Saved {season_placers_file}")

    print("\nAll FloArena downloads complete!")
