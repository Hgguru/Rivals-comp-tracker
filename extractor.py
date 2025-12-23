import cloudscraper
import re
import math
import time
import random

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "desktop": True}
)

team_comp_stats = {}

def get_all_match_ids():
    ign = input("Enter IGN: ").strip()

    base_url = (
        "https://api.tracker.gg/api/v2/marvel-rivals/standard/matches/ign/"
        f"{ign}?mode=competitive"
    )

    all_match_ids = []
    url = base_url

    match_id_regex = re.compile(
        r'"attributes"\s*:\s*{\s*"id"\s*:\s*"([^"]+)"\s*,\s*"mode"\s*:\s*"competitive"',
        re.DOTALL
    )

    next_regex = re.compile(
        r'"metadata"\s*:\s*{\s*"next"\s*:\s*(null|\d+)',
        re.DOTALL
    )

    while True:
        print(f"Fetching: {url}")
        response = scraper.get(url)

        if response.status_code != 200:
            print("Request failed:", response.status_code)
            break

        text = response.text

        all_match_ids.extend(match_id_regex.findall(text))

        next_match = next_regex.search(text)
        if not next_match or next_match.group(1) == "null":
            break

        url = base_url + f"&next={next_match.group(1)}"

    return all_match_ids

def role_times_to_continuous_counts(role_times):
    total = sum(role_times.values())
    if total == 0:
        return (0, 0, 0)

    return (
        6 * role_times["Vanguard"] / total,
        6 * role_times["Duelist"] / total,
        6 * role_times["Strategist"] / total
    )

def weighted_compositions(continuous_counts):
    v_c, d_c, s_c = continuous_counts

    base_v = math.floor(v_c)
    base_d = math.floor(d_c)
    base_s = math.floor(s_c)

    candidates = []

    # Generate only neighboring lattice points
    for dv in (0, 1):
        for dd in (0, 1):
            for ds in (0, 1):
                v = base_v + dv
                d = base_d + dd
                s = base_s + ds

                if v >= 0 and d >= 0 and s >= 0 and v + d + s == 6:
                    candidates.append((v, d, s))

    weights = {}
    total_weight = 0.0

    for v, d, s in candidates:
        dist = abs(v - v_c) + abs(d - d_c) + abs(s - s_c)
        weight = 1.0 / (dist + 1e-6)

        key = f"{v}-{d}-{s}"
        weights[key] = weight
        total_weight += weight

    # Normalize
    for k in weights:
        weights[k] /= total_weight

    return weights


def update_stats_weighted(weighted_comps, won):
    for comp, weight in weighted_comps.items():
        if comp not in team_comp_stats:
            team_comp_stats[comp] = {
                "weighted_matches": 0.0,
                "weighted_wins": 0.0
            }

        team_comp_stats[comp]["weighted_matches"] += weight
        if won:
            team_comp_stats[comp]["weighted_wins"] += weight

def snap_to_team_comp(role_times):
    """
    role_times = {"Vanguard": seconds, "Duelist": seconds, "Strategist": seconds}
    Converts time ratios to closest 6-player composition.
    """
    print(role_times)
    total_time = sum(role_times.values())
    if total_time == 0:
        return "0-0-0"

    # Initial proportional allocation
    raw_counts = {
        role: (role_times[role] / total_time) * 6
        for role in role_times
    }

    # Round and fix to sum exactly to 6
    counts = {r: int(round(v)) for r, v in raw_counts.items()}

    while sum(counts.values()) != 6:
        diff = 6 - sum(counts.values())
        # Adjust role with largest fractional error
        role = max(
            raw_counts,
            key=lambda r: raw_counts[r] - counts[r]
            if diff > 0 else counts[r] - raw_counts[r]
        )
        counts[role] += 1 if diff > 0 else -1

    return f"{counts['Vanguard']}-{counts['Duelist']}-{counts['Strategist']}"


def update_stats(comp, won):
    if comp not in team_comp_stats:
        team_comp_stats[comp] = {"matches": 0, "wins": 0}

    team_comp_stats[comp]["matches"] += 1
    if won:
        team_comp_stats[comp]["wins"] += 1

from concurrent.futures import ThreadPoolExecutor, as_completed

def process_all_matches_parallel(match_ids, max_workers=20):
    """
    Process all match_ids in parallel using threads.
    
    Args:
        match_ids: list of match IDs
        max_workers: number of threads (tune based on your network/API limits)
    """
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all match processing jobs
        futures = [executor.submit(process_match, mid) for mid in match_ids]

        # Optional: track progress
        for future in as_completed(futures):
            try:
                future.result()  # raises exception if process_match failed
            except Exception as e:
                print("Error processing match:", e)

def print_tc():
    rows = []

    for comp, stats in team_comp_stats.items():
        matches = stats.get("weighted_matches", 0.0)
        wins = stats.get("weighted_wins", 0.0)

        win_rate = wins / matches if matches > 0 else 0.0

        rows.append((
            comp,
            f"{matches:.2f}",
            f"{wins:.2f}",
            f"{win_rate*100:.2f}%"
        ))

    # Sort by matches played (descending, numeric)
    rows.sort(key=lambda x: float(x[1]), reverse=True)

    headers = ("Team Comp", "Matches", "Wins", "Win Rate")
    col_widths = [
        max(len(str(row[i])) for row in ([headers] + rows))
        for i in range(4)
    ]

    header_line = " | ".join(
        headers[i].ljust(col_widths[i]) for i in range(4)
    )
    separator = "-+-".join("-" * col_widths[i] for i in range(4))

    print(header_line)
    print(separator)

    for row in rows:
        print(" | ".join(
            str(row[i]).ljust(col_widths[i]) for i in range(4)
        ))

def process_match(match_id):
    url = f"https://api.tracker.gg/api/v2/marvel-rivals/standard/matches/{match_id}"
    print(url)
    response = scraper.get(url)

    if response.status_code != 200:
        print(f"Failed to fetch match {match_id}")
        return

    data = response.json()
    segments = data["data"]["segments"]

    teams = {
        "win": {"Vanguard": 0, "Duelist": 0, "Strategist": 0},
        "loss": {"Vanguard": 0, "Duelist": 0, "Strategist": 0},
    }

    i = 0
    while i < len(segments):
        seg = segments[i]

        if seg.get("type") == "player":
            result = seg["metadata"].get("result")
            team_key = "win" if result == "win" else "loss"

            i += 1
            while i < len(segments) and segments[i].get("type") == "hero":
                hero_seg = segments[i]
                role = hero_seg["metadata"].get("roleName")

                time_played = (
                    hero_seg.get("stats", {})
                    .get("timePlayed", {})
                    .get("value", 0)
                )

                if role in teams[team_key]:
                    teams[team_key][role] += time_played

                i += 1
        else:
            i += 1
    """ snap to team comp, not used
    win_comp = snap_to_team_comp(teams["win"])
    loss_comp = snap_to_team_comp(teams["loss"])

    print(f"Match {match_id}")
    print("Winning team comp:", win_comp)
    print("Losing team comp:", loss_comp)
    print("-" * 40)

    update_stats(win_comp, True)
    update_stats(loss_comp, False)
    """
    win_cont = role_times_to_continuous_counts(teams["win"])
    loss_cont = role_times_to_continuous_counts(teams["loss"])

    win_weighted = weighted_compositions(win_cont)
    loss_weighted = weighted_compositions(loss_cont)

    update_stats_weighted(win_weighted, True)
    update_stats_weighted(loss_weighted, False)
    """
    print("Winning team (weighted):")
    print(sorted(win_weighted.items(), key=lambda x: x[1], reverse=True)[:3])

    print("Losing team (weighted):")
    print(sorted(loss_weighted.items(), key=lambda x: x[1], reverse=True)[:3])
    """

if __name__ == "__main__":
    match_ids = get_all_match_ids()
    print(f"{len(match_ids)} comp matches found")
    process_all_matches_parallel(match_ids, max_workers=30)
    print_tc()