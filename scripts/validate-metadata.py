import json
import sys
import os
import re
from pathlib import Path

VALID_CATEGORIES = [
    "处理器工具",
    "显卡工具",
    "烤鸡工具",
    "内存工具",
    "硬盘工具",
    "显示器工具",
    "外设工具",
    "综合检测",
    "其他工具",
]

VALID_ARCHS = {"x86", "x64", "ARM64"}

VALID_URL_PREFIXES = ("gc:", "gh:", "https://", "http://")

REQUIRED_FIELDS = ["id", "name", "category"]

VALID_VERSION_RE = re.compile(r"^\d+(\.\d+){0,3}(-[\w.]+)?$")


def validate_metadata(plugin_json_path: str) -> dict:
    errors = []
    warnings = []

    with open(plugin_json_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            return {"status": "fail", "errors": [f"JSON 解析失败: {e}"], "warnings": []}

    if not isinstance(data, dict):
        return {"status": "fail", "errors": ["plugin.json 根元素必须是对象"], "warnings": []}

    for field in REQUIRED_FIELDS:
        if field not in data or not str(data[field]).strip():
            errors.append(f"缺少必填字段: {field}")

    plugin_id = data.get("id", "")
    if plugin_id:
        if not re.match(r"^[a-zA-Z0-9_-]+$", str(plugin_id)):
            errors.append(f"id 只能包含字母、数字、下划线和连字符: {plugin_id}")

    category = data.get("category", "")
    if category and category not in VALID_CATEGORIES:
        errors.append(
            f"无效分类: {category}，有效值: {', '.join(VALID_CATEGORIES)}"
        )

    version = data.get("version")
    if version and not VALID_VERSION_RE.match(str(version)):
        warnings.append(f"版本号格式不规范: {version}，建议使用 semver (如 1.0.0)")

    download_url = data.get("downloadUrl")
    if download_url:
        if not any(str(download_url).startswith(p) for p in VALID_URL_PREFIXES):
            errors.append(
                f"downloadUrl 格式无效: {download_url}，须以 gc:/gh:/https:// 开头"
            )

    arch_variants = data.get("archVariants")
    if arch_variants:
        if not isinstance(arch_variants, list):
            errors.append("archVariants 必须是数组")
        else:
            for i, av in enumerate(arch_variants):
                if not isinstance(av, dict):
                    errors.append(f"archVariants[{i}] 必须是对象")
                    continue
                if "file" not in av or not av["file"]:
                    errors.append(f"archVariants[{i}] 缺少 file 字段")
                if "arch" not in av or av["arch"] not in VALID_ARCHS:
                    errors.append(
                        f"archVariants[{i}] arch 无效: {av.get('arch')}，有效值: {', '.join(sorted(VALID_ARCHS))}"
                    )

    tags = data.get("tags")
    if tags is not None:
        if not isinstance(tags, list):
            errors.append("tags 必须是数组")
        elif len(tags) == 0:
            warnings.append("tags 为空，建议添加标签以提高搜索可见性")

    file_field = data.get("file")
    if not file_field and not download_url:
        warnings.append("未指定 file 或 downloadUrl，用户可能无法下载该工具")

    plugins_root = Path(__file__).parent.parent / "plugins"
    if plugin_id and plugins_root.exists():
        existing_ids = set()
        for plugin_json in plugins_root.rglob("plugin.json"):
            if str(plugin_json) == os.path.abspath(plugin_json_path):
                continue
            try:
                with open(plugin_json, "r", encoding="utf-8") as pf:
                    existing = json.load(pf)
                    eid = existing.get("id")
                    if eid:
                        existing_ids.add(eid)
            except Exception:
                pass
        if plugin_id in existing_ids:
            errors.append(f"ID 已存在: {plugin_id}，每个插件 ID 必须唯一")

    status = "pass" if not errors else "fail"
    return {"status": status, "errors": errors, "warnings": warnings}


def main():
    if len(sys.argv) < 2:
        print("Usage: validate-metadata.py <plugin.json>", file=sys.stderr)
        sys.exit(1)

    result = validate_metadata(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
