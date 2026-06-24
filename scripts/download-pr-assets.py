import json
import sys
import os
import base64
import urllib.request
import urllib.error
from pathlib import Path


def download_pr_assets(plugin_dir: str, output_dir: str):
    github_token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")

    if not repo:
        print("GITHUB_REPOSITORY not set", file=sys.stderr)
        sys.exit(1)

    api_base = f"https://api.github.com/repos/{repo}"

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TubaBot-Downloader",
    }
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    pr_number = None
    if event_path and os.path.exists(event_path):
        with open(event_path, "r", encoding="utf-8") as f:
            event = json.load(f)
            if "issue" in event and "pull_request" in event.get("issue", {}):
                pr_number = event["issue"]["number"]

    if not pr_number:
        print("Could not determine PR number", file=sys.stderr)
        sys.exit(1)

    print(f"Downloading assets from PR #{pr_number}, plugin_dir={plugin_dir}")

    def api_get(url):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    pr_data = api_get(f"{api_base}/pulls/{pr_number}")
    head_sha = pr_data["head"]["sha"]
    head_ref = pr_data["head"]["ref"]

    tree_data = api_get(f"{api_base}/git/trees/{head_sha}?recursive=1")
    tree = tree_data.get("tree", [])

    os.makedirs(output_dir, exist_ok=True)

    plugin_prefix = plugin_dir.rstrip("/") + "/"
    downloaded_files = []

    for item in tree:
        if item["type"] != "blob":
            continue
        item_path = item["path"]
        if not item_path.startswith(plugin_prefix):
            continue

        rel_path = item_path[len(plugin_prefix):]
        if not rel_path:
            continue

        local_path = os.path.join(output_dir, rel_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        print(f"  Downloading: {item_path} -> {local_path}")

        blob_data = api_get(f"{api_base}/git/blobs/{item['sha']}")
        content = blob_data.get("content", "")
        encoding = blob_data.get("encoding", "base64")

        if encoding == "base64":
            raw = base64.b64decode(content.replace("\n", ""))
            with open(local_path, "wb") as f:
                f.write(raw)
        else:
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(content)

        downloaded_files.append(rel_path)

    print(f"Downloaded {len(downloaded_files)} files: {downloaded_files}")

    result = {
        "status": "ok",
        "downloaded": downloaded_files,
        "output_dir": output_dir,
    }
    result_path = os.path.join(output_dir, "_download_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def main():
    if len(sys.argv) < 3:
        print("Usage: download-pr-assets.py <plugin_dir> <output_dir>", file=sys.stderr)
        sys.exit(1)

    download_pr_assets(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
