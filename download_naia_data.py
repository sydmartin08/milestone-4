"""
NAIA Women's Wrestling Data Extractor
Downloads all season tournaments, match results, programs, ratings, and placers.
"""

import subprocess
import re
import csv
import os
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.trackwrestling.com"

def get_tw_session(tourn_id, path='opentournaments'):
    url = f"{BASE_URL}/tw/{path}/VerifyPassword.jsp?tournamentId={tourn_id}"
    cookie_file = f"/tmp/tw_c_{tourn_id}.txt"
    html = subprocess.check_output(['curl', '-s', '-c', cookie_file, '-b', cookie_file, url]).decode('utf-8', errors='ignore')
    soup = BeautifulSoup(html, 'html.parser')
    form = soup.find('form')
    if not form:
        return None, None, cookie_file
    data_args = [arg for inp in form.find_all('input') if inp.get('name') for arg in ('-d', f"{inp['name']}={inp.get('value','')}")]
    m = re.search(r'action = "(/opentournaments/MainFrame\.jsp[^"]*)"', html)
    if not m:
        return None, None, cookie_file
    action_url = BASE_URL + m.group(1)
    post_html = subprocess.check_output(['curl', '-s', '-c', cookie_file, '-b', cookie_file] + data_args + [action_url]).decode('utf-8', errors='ignore')
    m_session = re.search(r'twSessionId=([a-z0-9]+)', post_html)
    m_tim = re.search(r'TIM=([0-9]+)', post_html)
    tw_session = m_session.group(1) if m_session else ''
    tim = m_tim.group(1) if m_tim else ''
    return tim, tw_session, cookie_file

def fetch_matches(tourn_id, tourn_name):
    tim, session, cookie_file = get_tw_session(tourn_id)
    if not tim or not session:
        print(f"Session failed for {tourn_name}")
        return []
    time.sleep(0.5)
    url_rr = f"{BASE_URL}/opentournaments/RoundResults.jsp?TIM={tim}&twSessionId={session}&displayResult=Y&roundId=&groupId=&displayFormatBox=2&includeByesBox=N"
    res_html = subprocess.check_output(['curl', '-s', '-c', cookie_file, '-b', cookie_file, url_rr]).decode('utf-8', errors='ignore')
    soup = BeautifulSoup(res_html, 'html.parser')
    lines = [l.strip() for l in soup.get_text().splitlines() if l.strip()]

    match_pat = re.compile(r'^(?:(?P<round>.+?)\s*-\s*)?(?P<winner>[^(]+)\s*\((?P<wteam>[^)]+)\)\s+won by\s+(?P<wintype>.+?)\s+over\s+(?P<loser>[^(]+)\s*\((?P<lteam>[^)]+)\)\s*(?P<score>.*)$')
    matches = []
    curr_wt = ''
    for line in lines:
        if any(line.startswith(p) for p in ['NAIA -', 'NAIA ', 'Women -', 'College Women -', 'Open -']):
            curr_wt = line.split('-')[-1].strip()
        elif 'won by' in line:
            m = match_pat.search(line)
            if m:
                d = m.groupdict()
                matches.append({
                    'event_name': tourn_name,
                    'event_id': tourn_id,
                    'weight_class': curr_wt,
                    'round': d['round'].strip() if d['round'] else '',
                    'winner': d['winner'].strip(),
                    'winner_team': d['wteam'].strip(),
                    'win_type': d['wintype'].strip(),
                    'loser': d['loser'].strip(),
                    'loser_team': d['lteam'].strip(),
                    'score_details': d['score'].strip() if d['score'] else '',
                    'raw_result': line
                })
    return matches

if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    events = [
        ('923487132', 'NAIA Women\'s National Championships 2025'),
        ('931032132', 'LWU Women\'s Blue Raider Open'),
        ('961817132', 'Women\'s Firestorm Open')
    ]
    all_m = []
    for eid, ename in events:
        ms = fetch_matches(eid, ename)
        print(f"{ename}: {len(ms)} matches")
        all_m.extend(ms)
        time.sleep(1)

    with open('data/match_results.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['event_name', 'event_id', 'weight_class', 'round', 'winner', 'winner_team', 'win_type', 'loser', 'loser_team', 'score_details', 'raw_result'])
        writer.writeheader()
        writer.writerows(all_m)
    print(f"Total: {len(all_m)} matches saved to data/match_results.csv")
