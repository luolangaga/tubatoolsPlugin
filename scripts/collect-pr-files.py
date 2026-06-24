import base64
import json
import os
import sys
import urllib.request
import urllib.error


def collect_pr_files(pr_number: str, output_dir: str):
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo:
        print("GITHUB_REPOSITORY not set", file=sys.stderr)
        sys.exit(1)

    api_base = f"https://api.github.com/repos/{repo}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TubaBot",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    def api_get(url):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    pr_data = api_get(f"{api_base}/pulls/{pr_number}")
    head_sha = pr_data["head"]["sha"]

    files = api_get(f"{api_base}/pulls/{pr_number}/files?per_page=100")

    os.makedirs(output_dir, exist_ok=True)
    downloaded = []

    for f in files:
        filepath = f["filename"]
        if f.get("status") == "removed":
            continue

        ext = os.path.splitext(filepath)[1].lower()
        if ext not in (".zip", ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".msi", ".7z", ".rar", ".dll", ".sys", ".msc", ".lnk", ".json"):
            continue

        local_path = os.path.join(output_dir, os.path.basename(filepath))

        if f.get("raw_url"):
            try:
                req = urllib.request.Request(f["raw_url"], headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
                with open(local_path, "wb") as out:
                    out.write(data)
                downloaded.append(os.path.basename(filepath))
                print(f"  Downloaded: {filepath}")
            except Exception as e:
                print(f"  Failed to download {filepath}: {e}", file=sys.stderr)
        elif f.get("patch") and ext == ".json":
            with open(local_path, "w", encoding="utf-8") as out:
                out.write(f["patch"])
            downloaded.append(os.path.basename(filepath))

    print(f"Collected {len(downloaded)} files: {downloaded}")
    if not downloaded:
        print("Warning: no scannable files found in PR", file=sys.stderr)


def main():
    if len(sys.argv) < 3:
        print("Usage: collect-pr-files.py <pr_number> <output_dir>", file=sys.stderr)
        sys.exit(1)
    collect_pr_files(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
