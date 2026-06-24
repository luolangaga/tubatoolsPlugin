import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


VT_API_BASE = "https://www.virustotal.com/vtapi/v2"


def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def query_virustotal(sha256: str, api_key: str) -> dict:
    url = f"{VT_API_BASE}/file/report?apikey={api_key}&resource={sha256}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "TubaBot-VTCheck")

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 30 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
        except urllib.error.URLError:
            if attempt < 2:
                time.sleep(10)
            else:
                raise
    return {"response_code": 0, "verbose_msg": "Failed after retries"}


def scan_directory(scan_dir: str) -> dict:
    api_key = os.environ.get("VT_API_KEY", "")
    if not api_key:
        print("VT_API_KEY not set, skipping VirusTotal check", file=sys.stderr)
        return {"status": "skip", "message": "VIRUSTOTAL_API_KEY not configured"}

    results = []
    total_positives = 0
    total_total = 0
    all_files = []

    for root, dirs, files in os.walk(scan_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            if fname == "_download_result.json":
                continue
            if os.path.getsize(fpath) > 32 * 1024 * 1024:
                print(f"  Skipping large file (>32MB): {fname}")
                continue
            all_files.append(fpath)

    for fpath in all_files:
        fname = os.path.basename(fpath)
        print(f"  Checking: {fname}")
        file_sha256 = sha256_file(fpath)
        print(f"    SHA256: {file_sha256}")

        vt_data = query_virustotal(file_sha256, api_key)

        if vt_data.get("response_code") == 1:
            positives = vt_data.get("positives", 0)
            total = vt_data.get("total", 0)
            total_positives += positives
            total_total = total
            scan_date = vt_data.get("scan_date", "unknown")
            print(f"    Result: {positives}/{total} engines detected")
            results.append(
                {
                    "file": fname,
                    "sha256": file_sha256,
                    "positives": positives,
                    "total": total,
                    "scan_date": scan_date,
                    "permalink": vt_data.get("permalink", ""),
                    "status": "fail" if positives >= 3 else ("warn" if positives >= 1 else "pass"),
                }
            )
        else:
            msg = vt_data.get("verbose_msg", "unknown")
            print(f"    Not found in VT: {msg}")
            results.append(
                {
                    "file": fname,
                    "sha256": file_sha256,
                    "positives": -1,
                    "total": 0,
                    "status": "unknown",
                    "message": msg,
                }
            )

        time.sleep(15)

    overall_status = "pass"
    for r in results:
        if r["status"] == "fail":
            overall_status = "fail"
            break
        if r["status"] == "warn":
            overall_status = "warn"

    return {
        "status": overall_status,
        "positives": total_positives,
        "total": total_total if total_total > 0 else 0,
        "files": results,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: virustotal-check.py <scan_dir>", file=sys.stderr)
        sys.exit(1)

    result = scan_directory(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
