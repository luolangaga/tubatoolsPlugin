import json
import os
import sys
from pathlib import Path


def find_file(dir_path, name):
    for root, dirs, files in os.walk(dir_path):
        for f in files:
            if f == name:
                return os.path.join(root, f)
    return None


def read_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def read_text(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def generate_report(results_dir: str) -> str:
    meta_result = read_json(find_file(results_dir, "metadata-result.json"))
    usability_result = read_json(find_file(results_dir, "usability-result.json"))
    vt_result = read_json(find_file(results_dir, "virustotal.json"))

    clamav_log = read_text(find_file(results_dir, "clamav.log"))
    yara_text = read_text(find_file(results_dir, "yara.txt"))

    meta_status = "✅" if meta_result and meta_result.get("status") == "pass" else "❌"
    usability_status = "✅" if usability_result and usability_result.get("status") == "pass" else "❌"

    clamav_infected = 0
    for line in clamav_log.splitlines():
        if "FOUND" in line:
            clamav_infected += 1
    clamav_status = "❌" if clamav_infected > 0 else "✅"

    yara_hits = len([l for l in yara_text.strip().splitlines() if l.strip()]) if yara_text.strip() else 0
    yara_status = "⚠️" if yara_hits > 0 else "✅"

    vt_positives = vt_result.get("positives", 0) if vt_result else 0
    vt_total = vt_result.get("total", 0) if vt_result else 0
    if vt_result is None:
        vt_status = "⏭️"
        vt_detail = "未配置或查询失败"
    elif vt_positives >= 3:
        vt_status = "❌"
        vt_detail = f"{vt_positives}/{vt_total} 引擎报毒"
    elif vt_positives >= 1:
        vt_status = "⚠️"
        vt_detail = f"{vt_positives}/{vt_total} 引擎报毒"
    else:
        vt_status = "✅"
        vt_detail = f"{vt_positives}/{vt_total} 引擎报毒"

    virus_overall = "✅"
    if clamav_status == "❌" or vt_status == "❌":
        virus_overall = "❌"
    elif yara_status == "⚠️" or vt_status == "⚠️":
        virus_overall = "⚠️"

    all_pass = meta_status == "✅" and virus_overall == "✅" and usability_status == "✅"

    report = "## 🔍 社区工具自动审核报告\n\n"
    report += "| 检查项 | 状态 | 详情 |\n"
    report += "|--------|------|------|\n"

    meta_detail = "格式正确，字段完整"
    if meta_result and meta_result.get("errors"):
        meta_detail = "; ".join(meta_result["errors"][:3])
    report += f"| 元数据校验 | {meta_status} | {meta_detail} |\n"

    virus_detail = f"ClamAV: {clamav_infected} 个威胁 · VirusTotal: {vt_detail} · YARA: {yara_hits} 条匹配"
    report += f"| 病毒扫描 | {virus_overall} | {virus_detail} |\n"

    usability_detail = "结构完整，启动目标存在"
    if usability_result and usability_result.get("errors"):
        usability_detail = "; ".join(usability_result["errors"][:3])
    report += f"| 可用性检查 | {usability_status} | {usability_detail} |\n"

    report += "\n---\n\n"

    if meta_result and meta_result.get("errors"):
        report += "### ⚠️ 元数据问题\n"
        for err in meta_result["errors"]:
            report += f"- {err}\n"
        report += "\n"

    if meta_result and meta_result.get("warnings"):
        report += "### 💡 元数据建议\n"
        for w in meta_result["warnings"]:
            report += f"- {w}\n"
        report += "\n"

    if clamav_infected > 0:
        report += "### 🚨 ClamAV 检测结果\n"
        for line in clamav_log.splitlines():
            if "FOUND" in line:
                report += f"- `{line.strip()}`\n"
        report += "\n"

    if yara_hits > 0:
        report += "### ⚠️ YARA 规则匹配\n"
        for line in yara_text.strip().splitlines()[:10]:
            if line.strip():
                report += f"- `{line.strip()}`\n"
        if yara_hits > 10:
            report += f"- ... 还有 {yara_hits - 10} 条匹配\n"
        report += "\n"

    if vt_result and vt_result.get("files"):
        report += "### 🛡️ VirusTotal 详细结果\n"
        for f in vt_result["files"]:
            if f.get("positives", 0) > 0:
                report += f"- **{f['file']}**: {f['positives']}/{f['total']} 引擎报毒 [查看报告]({f.get('permalink', '')})\n"
        report += "\n"

    if usability_result and usability_result.get("errors"):
        report += "### ⚠️ 可用性问题\n"
        for err in usability_result["errors"]:
            report += f"- {err}\n"
        report += "\n"

    if usability_result and usability_result.get("warnings"):
        report += "### 💡 可用性建议\n"
        for w in usability_result["warnings"]:
            report += f"- {w}\n"
        report += "\n"

    if all_pass:
        report += "### ✅ 审核通过\n\n该插件已通过所有自动检查，等待维护者最终确认后即可合并。\n\n"
    else:
        report += "### ❌ 审核未通过\n\n请根据上述问题修改后重新提交。修改后评论 `@tubabot review` 重新审核。\n\n"

    report += "*此报告由 **TubaBot** 自动生成，仅供参考。最终审核仍需人工确认。*"

    return report


def main():
    if len(sys.argv) < 2:
        print("Usage: generate-report.py <results_dir>", file=sys.stderr)
        sys.exit(1)

    report = generate_report(sys.argv[1])
    output_path = os.path.join(sys.argv[1], "report.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    sys.exit(0)


if __name__ == "__main__":
    main()
