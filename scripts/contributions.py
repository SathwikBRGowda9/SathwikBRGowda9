"""Generate contribution totals from GitHub calendar data, failing on API errors."""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.request


def query(document, variables):
    request = urllib.request.Request('https://api.github.com/graphql',
        data=json.dumps({'query': document, 'variables': variables}).encode(),
        headers={'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
                 'Content-Type': 'application/json', 'User-Agent': 'profile-contributions'})
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
    if result.get('errors'):
        raise RuntimeError(result['errors'])
    return result['data']['user']


def main():
    user = os.environ['PROFILE_USER']
    now = dt.datetime.now(dt.timezone.utc)
    profile = query('query($user:String!){user(login:$user){createdAt}}', {'user': user})
    first = int(profile['createdAt'][:4])
    years, days = {}, {}
    for year in range(first, now.year + 1):
        end = min(now, dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc))
        result = query('''query($user:String!,$from:DateTime!,$to:DateTime!){
          user(login:$user){contributionsCollection(from:$from,to:$to){
            contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}
          }}}
        ''', {'user': user, 'from': f'{year}-01-01T00:00:00Z', 'to': end.isoformat()})
        calendar = result['contributionsCollection']['contributionCalendar']
        year_days = {day['date']: day['contributionCount']
            for week in calendar['weeks'] for day in week['contributionDays']
            if day['date'].startswith(str(year)) and day['date'] <= now.date().isoformat()}
        total = sum(year_days.values())
        if total != calendar['totalContributions']:
            raise ValueError(f'Calendar total mismatch for {year}')
        years[str(year)] = total
        days.update(year_days)
    cutoff = (now.date() - dt.timedelta(days=364)).isoformat()
    recent = sum(count for date, count in days.items() if date >= cutoff)
    total = sum(years.values())
    updated = now.strftime('%Y-%m-%d %H:%M UTC')
    cards = [('ALL-TIME CONTRIBUTIONS', total),
             (f'{now.year} CONTRIBUTIONS', years[str(now.year)]), ('LAST 365 DAYS', recent)]
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="250" viewBox="0 0 1000 250" role="img">',
        '<title>GitHub contribution totals</title>',
        '<rect x="1" y="1" width="998" height="248" rx="18" fill="#0d1117" stroke="#303b50"/>',
        '<g font-family="Segoe UI,Arial,sans-serif">',
        '<text x="32" y="40" fill="#f8fafc" font-size="20" font-weight="700">GitHub contributions</text>']
    for index, (label, value) in enumerate(cards):
        x = 32 + index * 325
        svg += [f'<text x="{x}" y="82" fill="#94a3b8" font-size="13">{label}</text>',
                f'<text x="{x}" y="137" fill="#38bdf8" font-size="42" font-weight="700">{value:,}</text>']
    svg += [f'<text x="32" y="181" fill="#a5b4fc" font-size="13">Since {first} · GitHub calendar counts visible to this workflow</text>',
            f'<text x="32" y="210" fill="#94a3b8" font-size="12">Updated {updated} · Refreshed daily</text>', '</g></svg>']
    output = Path('dist')
    output.mkdir(exist_ok=True)
    (output / 'contribution-stats.svg').write_text('\n'.join(svg), encoding='utf-8')
    stats = {'user': user, 'updated_at': updated, 'scope': 'GitHub calendar counts visible to workflow token',
             'all_time': total, 'current_year': years[str(now.year)], 'last_365_days': recent, 'by_year': years}
    (output / 'contribution-stats.json').write_text(json.dumps(stats, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(stats))


if __name__ == '__main__':
    main()
