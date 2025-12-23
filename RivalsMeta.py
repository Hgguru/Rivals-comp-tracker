import json
from playwright.sync_api import sync_playwright
import re
import asyncio
from playwright.async_api import async_playwright
import math

CONCURRENT_REQUESTS = 10

team_comp_stats = {}

heroes = {
    1065: {"name": "Rogue", "role": "Vanguard"},
    1058: {"name": "Gambit", "role": "Strategist"},
    1050: {"name": "Invisible Woman", "role": "Strategist"},
    1047: {"name": "Jeff The Land Shark", "role": "Strategist"},
    1025: {"name": "Cloak & Dagger", "role": "Strategist"},
    1031: {"name": "Luna Snow", "role": "Strategist"},
    1036: {"name": "Spider Man", "role": "Duelist"},
    1023: {"name": "Rocket Raccoon", "role": "Strategist"},
    1030: {"name": "Moon Knight", "role": "Duelist"},
    1055: {"name": "Daredevil", "role": "Duelist"},
    1028: {"name": "Ultron", "role": "Strategist"},
    1037: {"name": "Magneto", "role": "Vanguard"},
    1021: {"name": "Hawkeye", "role": "Duelist"},
    1041: {"name": "Winter Soldier", "role": "Duelist"},
    1038: {"name": "Scarlet Witch", "role": "Duelist"},
    1053: {"name": "Emma Frost", "role": "Vanguard"},
    1043: {"name": "Star Lord", "role": "Duelist"},
    1054: {"name": "Phoenix", "role": "Duelist"},
    1042: {"name": "Peni Parker", "role": "Vanguard"},
    1014: {"name": "The Punisher", "role": "Duelist"},
    1024: {"name": "Hela", "role": "Duelist"},
    1048: {"name": "Psylocke", "role": "Duelist"},
    1032: {"name": "Squirrel Girl", "role": "Duelist"},
    1056: {"name": "Angela", "role": "Vanguard"},
    1039: {"name": "Thor", "role": "Vanguard"},
    1034: {"name": "Iron Man", "role": "Duelist"},
    1018: {"name": "Doctor Strange", "role": "Vanguard"},
    1029: {"name": "Magik", "role": "Duelist"},
    1035: {"name": "Venom", "role": "Vanguard"},
    1052: {"name": "Iron Fist", "role": "Duelist"},
    1020: {"name": "Mantis", "role": "Strategist"},
    1016: {"name": "Loki", "role": "Strategist"},
    1044: {"name": "Blade", "role": "Duelist"},
    1046: {"name": "Adam Warlock", "role": "Strategist"},
    1022: {"name": "Captain America", "role": "Vanguard"},
    1045: {"name": "Namor", "role": "Duelist"},
    1040: {"name": "Mister Fantastic", "role": "Duelist"},
    1027: {"name": "Groot", "role": "Vanguard"},
    1051: {"name": "The Thing", "role": "Vanguard"},
    1049: {"name": "Wolverine", "role": "Duelist"},
    1011: {"name": "Hulk", "role": "Vanguard"},
    1033: {"name": "Black Widow", "role": "Duelist"},
    1026: {"name": "Black Panther", "role": "Duelist"},
    1015: {"name": "Storm", "role": "Duelist"},
    1017: {"name": "Human Torch", "role": "Duelist"}
}

def get_aid(player_name: str):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        request_context = context.request

        url = "https://rivalsmeta.com/api/find-player"
        payload = {"name": player_name}
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://rivalsmeta.com",
            "Referer": "https://rivalsmeta.com/player/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 OPR/124.0.0.0",
        }

        # Convert payload to JSON string
        response = request_context.post(url, data=json.dumps(payload), headers=headers)
        # Parse JSON safely
        try:
            data = response.json()
        except Exception as e:
            print("Failed to parse JSON:", e)
            return None

        for player in data:
            if player.get("name").lower() == player_name.lower():
                return player.get("aid")
        return None
    
def update_player(aid: str):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        request_context = context.request

        url = f"https://rivalsmeta.com/api/update-player/{aid}"
        headers = {
            "Accept": "application/json",
            "Origin": "https://rivalsmeta.com",
            "Referer": "https://rivalsmeta.com/player/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 OPR/124.0.0.0",
        }

        # Try GET method
        response = request_context.get(url, headers=headers)

        try:
            data = response.json()
        except Exception as e:
            print("Failed to parse JSON:", e)
            return

        if data.get("status") == "success":
            print("Updated successfully")
        else:
            print("Update failed:", data)

def get_all_matches(aid: str, season: float):
    cs = int(season * 2)
    matches = []
    skip = 0

    pattern = re.compile(r'"match_uid"\s*:\s*"([^"]+)"')

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        request = context.request

        headers = {
            "Accept": "application/json",
            "Origin": "https://rivalsmeta.com",
            "Referer": "https://rivalsmeta.com/player/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        }

        # ---- FIRST CALL ----
        url = f"https://rivalsmeta.com/api/player-match-history/{aid}?skip=0&game_mode_id=2&hero_id=0&season={cs}"
        response = request.get(url, headers=headers)
        text = response.text()

        batch = pattern.findall(text)
        matches.extend(batch)

        # ---- PAGINATION ----
        while True:
            skip += 20
            url = f"https://rivalsmeta.com/api/player-match-history/{aid}?skip={skip}&game_mode_id=2&hero_id=0&season={cs}"
            response = request.get(url, headers=headers)
            text = response.text()
            new_batch = pattern.findall(text)
            if not new_batch:
                break

            matches.extend(new_batch)

        browser.close()
    print(f"{len(matches)} matches found")
    return matches

async def fetch_match_data(match_id, page):
    url = f"https://rivalsmeta.com/api/matches/{match_id}"
    try:
        response = await page.goto(url)
        # Wait until the response is fully loaded
        await page.wait_for_load_state("networkidle")
        content = await page.content()
        # Sometimes the content is JSON directly in response body
        # Playwright has a `response.json()` if we intercept the request
        resp = await page.request.get(url)
        data = await resp.json()
        return match_id, data
    except Exception as e:
        print(f"Error fetching match {match_id}: {e}")
        return match_id, None


def role_times_to_continuous_counts(role_times):
    #print(role_times)
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

# ---------- Thread-safe process_match ----------
async def process_match(match_id, request_context, semaphore):
    url = f"https://rivalsmeta.com/api/matches/{match_id}"

    headers = {
        "Accept": "application/json",
        "Origin": "https://rivalsmeta.com",
        "Referer": "https://rivalsmeta.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),
    }

    async with semaphore:
        try:
            resp = await request_context.get(url, headers=headers)
            if resp.status != 200:
                print(f"Failed {match_id}: {resp.status}")
                return

            data = await resp.json()
        except Exception as e:
            print(f"Error fetching {match_id}: {e}")
            return

    # ---------- PROCESS DATA ----------
    teams = {
        "win": {"Vanguard": 0.0, "Duelist": 0.0, "Strategist": 0.0},
        "loss": {"Vanguard": 0.0, "Duelist": 0.0, "Strategist": 0.0},
    }

    for player in data.get("match_players", []):
        is_win = player.get("is_win")
        #print(f"player {player["nick_name"]}: {is_win}")
        if is_win == 1:
            team_key = "win"
        elif is_win == 0:
            team_key = "loss"
        else:
            continue  # skip invalid players

        for hero in player.get("player_heroes", []):
            hero_id = hero.get("hero_id")
            play_time = hero.get("play_time", 0.0)

            hero_info = heroes.get(hero_id)
            if not hero_info:
                continue

            role = hero_info["role"]
            teams[team_key][role] += play_time

    # ---------- WEIGHTED COMPS ----------
    win_cont = role_times_to_continuous_counts(teams["win"])
    loss_cont = role_times_to_continuous_counts(teams["loss"])


    win_weighted = weighted_compositions(win_cont)
    loss_weighted = weighted_compositions(loss_cont)

    update_stats_weighted(weighted_compositions(win_cont), True)
    update_stats_weighted(weighted_compositions(loss_cont), False)
    """
    print("Winning team (weighted):")
    print(sorted(win_weighted.items(), key=lambda x: x[1], reverse=True)[:3])

    print("Losing team (weighted):")
    print(sorted(loss_weighted.items(), key=lambda x: x[1], reverse=True)[:3])
    """
# ---------- Multi-threaded executor ----------
async def process_all_matches(match_ids):
    async with async_playwright() as pw:
        request_context = await pw.request.new_context()

        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

        tasks = [
            process_match(mid, request_context, semaphore)
            for mid in match_ids
        ]

        await asyncio.gather(*tasks)
        await request_context.dispose()

# ---------- Print stats ----------
def print_tc():
    rows = []

    total_entries = sum(
        stats.get("weighted_matches", 0.0)
        for stats in team_comp_stats.values()
    )

    for comp, stats in team_comp_stats.items():
        matches = stats.get("weighted_matches", 0.0)
        wins = stats.get("weighted_wins", 0.0)

        pick_rate = matches / total_entries if total_entries > 0 else 0.0
        win_rate = wins / matches if matches > 0 else 0.0

        rows.append((
            comp,
            f"{matches:.2f}",
            f"{wins:.2f}",
            f"{pick_rate*100:.2f}%",
            f"{win_rate*100:.2f}%"
        ))

    # Sort by matches played
    rows.sort(key=lambda x: float(x[1]), reverse=True)

    headers = ("Team Comp", "Matches", "Wins", "Pick Rate", "Win Rate")

    col_widths = [
        max(len(str(row[i])) for row in ([headers] + rows))
        for i in range(len(headers))
    ]

    header_line = " | ".join(
        headers[i].ljust(col_widths[i]) for i in range(len(headers))
    )
    separator = "-+-".join("-" * col_widths[i] for i in range(len(headers)))

    print(header_line)
    print(separator)

    for row in rows:
        print(" | ".join(
            str(row[i]).ljust(col_widths[i]) for i in range(len(headers))
        ))

async def main():
    await process_all_matches(match_ids)
    print_tc()

player_name = input("Enter ign: ")
season = float(input("Enter season: "))
aid = get_aid(player_name)
print(f"AID for {player_name}: {aid}")
update_player(aid)
match_ids = get_all_matches(aid,season)
asyncio.run(main())
input()