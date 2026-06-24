import json
import os
import sys
import zipfile
from pathlib import Path

MAX_ZIP_SIZE_MB = 500
MAX_ICON_SIZE_KB = 512
VALID_ICON_FORMATS = {".png", ".ico", ".jpg", ".jpeg", ".svg"}
VALID_EXE_EXTENSIONS = {".exe", ".bat", ".cmd", ".msc", ".ps1", ".vbs", ".lnk"}


def validate_usability(plugin_json_path: str, download_dir: str) -> dict:
    errors = []
    warnings = []

    with open(plugin_json_path, "r", encoding="utf-8") as f:
        try:
            meta = json.load(f)
        except json.JSONDecodeError as e:
            return {"status": "fail", "errors": [f"plugin.json 解析失败: {e}"], "warnings": []}

    zip_file_name = meta.get("file")
    if not zip_file_name:
        errors.append("plugin.json 未指定 file 字段（ZIP 文件名）")
        return {"status": "fail", "errors": errors, "warnings": warnings}

    zip_path = os.path.join(download_dir, zip_file_name)
    if not os.path.exists(zip_path):
        errors.append(f"ZIP 文件不存在: {zip_file_name}")
        return {"status": "fail", "errors": errors, "warnings": warnings}

    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    if zip_size_mb > MAX_ZIP_SIZE_MB:
        errors.append(f"ZIP 文件过大: {zip_size_mb:.1f}MB (上限 {MAX_ZIP_SIZE_MB}MB)")

    extract_dir = os.path.join(download_dir, "_extracted")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            bad = zf.testzip()
            if bad:
                errors.append(f"ZIP 文件损坏，损坏条目: {bad}")
                return {"status": "fail", "errors": errors, "warnings": warnings}

            zf.extractall(extract_dir)
            zip_entries = zf.namelist()
    except zipfile.BadZipFile:
        errors.append("ZIP 文件格式无效或已损坏")
        return {"status": "fail", "errors": errors, "warnings": warnings}
    except Exception as e:
        errors.append(f"ZIP 解压失败: {e}")
        return {"status": "fail", "errors": errors, "warnings": warnings}

    all_extracted_files = []
    for root, dirs, files in os.walk(extract_dir):
        for fname in files:
            rel = os.path.relpath(os.path.join(root, fname), extract_dir)
            all_extracted_files.append(rel.replace("\\", "/"))

    launch_target = meta.get("launchTarget")
    if launch_target:
        found = any(
            f.lower().endswith(launch_target.lower()) or f.lower() == launch_target.lower()
            for f in all_extracted_files
        )
        if not found:
            errors.append(
                f"launchTarget '{launch_target}' 在 ZIP 中未找到。可用文件: {all_extracted_files[:10]}"
            )
    else:
        exe_files = [f for f in all_extracted_files if f.lower().endswith(".exe")]
        if not exe_files:
            warnings.append("ZIP 中未找到 .exe 文件，且未指定 launchTarget")
        elif len(exe_files) > 1:
            warnings.append(
                f"ZIP 中有多个 .exe 文件 ({len(exe_files)} 个)，建议指定 launchTarget"
            )

    arch_variants = meta.get("archVariants", [])
    if arch_variants:
        for av in arch_variants:
            av_file = av.get("file", "")
            if av_file:
                found = any(
                    f.lower().endswith(av_file.lower()) or f.lower() == av_file.lower()
                    for f in all_extracted_files
                )
                if not found:
                    errors.append(
                        f"archVariants 文件 '{av_file}' (arch={av.get('arch')}) 在 ZIP 中未找到"
                    )

    icon_file = meta.get("icon")
    if icon_file:
        icon_in_zip = any(
            f.lower() == icon_file.lower() or f.lower().endswith(icon_file.lower())
            for f in all_extracted_files
        )
        if not icon_in_zip:
            warnings.append(f"图标文件 '{icon_file}' 未找到")
        else:
            ext = Path(icon_file).suffix.lower()
            if ext not in VALID_ICON_FORMATS:
                errors.append(f"图标格式不支持: {ext}，支持: {', '.join(sorted(VALID_ICON_FORMATS))}")
            else:
                for f in all_extracted_files:
                    if f.lower() == icon_file.lower() or f.lower().endswith(icon_file.lower()):
                        full_icon = os.path.join(extract_dir, f)
                        if os.path.exists(full_icon):
                            icon_size_kb = os.path.getsize(full_icon) / 1024
                            if icon_size_kb > MAX_ICON_SIZE_KB:
                                warnings.append(
                                    f"图标文件过大: {icon_size_kb:.0f}KB (建议 ≤{MAX_ICON_SIZE_KB}KB)"
                                )
                            if ext == ".png":
                                try:
                                    from PIL import Image
                                    with Image.open(full_icon) as img:
                                        w, h = img.size
                                        if w > 256 or h > 256:
                                            warnings.append(
                                                f"图标尺寸过大: {w}x{h}，建议 ≤256x256"
                                            )
                                except ImportError:
                                    pass
                                except Exception:
                                    warnings.append("图标 PNG 文件可能已损坏")
                        break

    suspicious_scripts = []
    for f in all_extracted_files:
        ext = Path(f).suffix.lower()
        if ext in (".ps1", ".vbs", ".bat", ".cmd"):
            suspicious_scripts.append(f)
    if suspicious_scripts:
        warnings.append(
            f"ZIP 中包含脚本文件: {suspicious_scripts}，请确认安全性"
        )

    status = "fail" if errors else "pass"
    return {"status": status, "errors": errors, "warnings": warnings}


def main():
    if len(sys.argv) < 3:
        print("Usage: validate-usability.py <plugin.json> <download_dir>", file=sys.stderr)
        sys.exit(1)

    result = validate_usability(sys.argv[1], sys.argv[2])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
