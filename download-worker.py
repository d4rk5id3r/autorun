import os
import json
import requests
import concurrent.futures
from tqdm import tqdm
import argparse

API_URL = "https://api.wordpress.org/plugins/info/1.2/"
PER_PAGE = 1000  # max allowed per API call
OUTPUT_DIR = "plugins"


def fetch_plugins():
    """Fetch all plugins from the WordPress.org API (paginated)."""
    all_plugins = []
    page = 1
    print("[*] Starting plugin metadata collection...")

    while True:
        params = {
            "action": "query_plugins",
            "request[per_page]": PER_PAGE,
            "request[page]": page
        }
        resp = requests.get(API_URL, params=params)
        if resp.status_code != 200:
            print(f"[!] Failed to fetch page {page}: HTTP {resp.status_code}")
            break

        data = resp.json()
        plugins = data.get("plugins", [])
        if not plugins:
            break

        all_plugins.extend(plugins)
        print(f"  -> Page {page}: +{len(plugins)} plugins (total: {len(all_plugins)})")
        page += 1

    print(f"[*] Completed: Collected {len(all_plugins)} plugins total.")
    return all_plugins


def filter_plugins(plugins, min_installs, max_installs):
    """Filter plugins by install count range."""
    return [
        p for p in plugins
        if min_installs <= p.get("active_installs", 0) <= max_installs
    ]


def download_plugin(slug):
    """Download a single plugin .zip from WordPress.org."""
    url = f"https://downloads.wordpress.org/plugin/{slug}.zip"
    path = os.path.join(OUTPUT_DIR, f"{slug}.zip")

    if os.path.exists(path):
        return f"[SKIP] {slug} (already downloaded)"

    try:
        resp = requests.get(url, stream=True, timeout=30)
        if resp.status_code == 200:
            with open(path, "wb") as f:
                for chunk in resp.iter_content(1024 * 64):
                    f.write(chunk)
            return f"[OK] {slug}"
        else:
            return f"[FAIL] {slug} (HTTP {resp.status_code})"
    except Exception as e:
        return f"[ERROR] {slug}: {e}"


def main():
    parser = argparse.ArgumentParser(description="Download WordPress plugins by install count range.")
    parser.add_argument("--min", type=int, default=0, help="Minimum installs (default: 0)")
    parser.add_argument("--max", type=int, default=1000000, help="Maximum installs (default: 1,000,000)")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    min_installs = args.min
    max_installs = args.max

    print(f"[*] Filtering plugins with installs between {min_installs} and {max_installs}...")

    plugins = fetch_plugins()
    filtered = filter_plugins(plugins, min_installs, max_installs)

    print(f"[*] Found {len(filtered)} plugins in range {min_installs}-{max_installs} installs.")

    if not filtered:
        return

    slugs = [p["slug"] for p in filtered]

    print("[*] Starting concurrent downloads...\n")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(tqdm(executor.map(download_plugin, slugs), total=len(slugs)))

    print("\n".join(results))
    print(f"\n[*] All done. Plugins saved in '{OUTPUT_DIR}/'.")


if __name__ == "__main__":
    main()
