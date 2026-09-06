#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

FIELD_LABELS = {
    "totalRegisteredCameras": "registered",
    "totalIntegratedCameras": "integrated",
    "totalOwnedCameras": "owned",
    "totalSharedCameras": "shared",
    "subscribedCameras": "subscribed",
}

def git(*args):
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.rstrip("\n")

def get_changed_files():
    """Return list of (status, path) from --cached diff."""
    out = git("diff", "--cached", "--name-status")
    if not out:
        return []
    files = []
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            files.append((parts[0], parts[1]))
    return files

def get_head_file(path):
    """Return the committed version of a file, or None if new."""
    out = git("show", f"HEAD:{path}")
    return out

def last_jsonl_line(content):
    """Parse the last JSON line from a JSONL string. Returns dict or None."""
    lines = content.strip().split("\n")
    if not lines:
        return None
    for line in reversed(lines):
        line = line.strip()
        if line:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None

def describe_change(prev, curr):
    """Compare two stats dicts, return a short human string."""
    parts = []
    for key, label in FIELD_LABELS.items():
        p = prev.get(key)
        c = curr.get(key)
        if p == c:
            continue
        if p is None:
            parts.append(f"{label}={c}")
        elif c is None:
            parts.append(f"{label} removed")
        else:
            diff = c - p
            arrow = "▲" if diff > 0 else "▼"
            parts.append(f"{label} {arrow}{abs(diff)}")
    if not parts:
        return None
    return ", ".join(parts)

def main():
    files = get_changed_files()
    if not files:
        print("data: no changes")
        return 0

    data_changes = []  # (slug, description)
    mou_changes = set()
    org_changes = set()
    logo_changes = set()
    system_changes = []
    has_non_data = False

    for status, path in files:
        if path == "fusus-system.json":
            head_content = get_head_file(path)
            try:
                with open(path) as f:
                    staged_content = f.read()
                prev_v = json.loads(head_content).get("version") if head_content else None
                curr_v = json.loads(staged_content).get("version") if staged_content else None
                if prev_v != curr_v and curr_v:
                    system_changes.append(f"platform v{curr_v}")
                else:
                    system_changes.append("domain routing/status")
            except Exception:
                system_changes.append("platform status")
            continue

        if not path.startswith("data/"):
            has_non_data = True
            continue

        parts = path.split("/")
        if len(parts) < 3:
            continue

        slug = parts[1]
        filename = parts[2]

        if filename == "stats.jsonl":
            head_content = get_head_file(path)
            try:
                with open(path) as f:
                    staged_content = f.read()
            except Exception:
                continue

            prev = last_jsonl_line(head_content) if head_content else None
            curr = last_jsonl_line(staged_content)

            if prev is None and curr:
                if "error" in curr:
                    data_changes.append((slug, f"blocked ({curr['error']})"))
                elif head_content is None:
                    data_changes.append((slug, "new"))
                else:
                    data_changes.append((slug, "first snapshot"))
            elif prev and curr:
                prev_err = "error" in prev
                curr_err = "error" in curr
                if prev_err and curr_err:
                    data_changes.append((slug, "still blocked"))
                elif prev_err:
                    data_changes.append((slug, "recovered"))
                elif curr_err:
                    data_changes.append((slug, f"blocked ({curr['error']})"))
                else:
                    desc = describe_change(prev, curr)
                    if desc:
                        data_changes.append((slug, desc))
                    else:
                        data_changes.append((slug, "no change"))
        elif filename == "mou.html":
            mou_changes.add(slug)
        elif filename == "organization.json":
            org_changes.add(slug)
        elif filename.startswith("logo."):
            logo_changes.add(slug)

    body_lines = []
    all_affected_slugs = set(s for s, d in data_changes if d and d != "no change" and not d.startswith("still blocked"))
    all_affected_slugs.update(mou_changes)
    all_affected_slugs.update(org_changes)
    all_affected_slugs.update(logo_changes)

    changed_stats = [(s, d) for s, d in data_changes if d and d != "no change" and not d.startswith("still blocked")]
    new_portals = [(s, d) for s, d in data_changes if d == "new" or d == "first snapshot"]

    if system_changes and not all_affected_slugs:
        print(f"system: update Fusus ({', '.join(system_changes)})")
    elif all_affected_slugs or new_portals:
        summary_parts = []
        if changed_stats:
            summary_parts.append(f"{len(changed_stats)} with count changes")
        if mou_changes:
            summary_parts.append(f"{len(mou_changes)} MOU updates")
        if org_changes:
            summary_parts.append(f"{len(org_changes)} metadata updates")
        if logo_changes:
            summary_parts.append(f"{len(logo_changes)} logo updates")
        if new_portals:
            summary_parts.append(f"{len(new_portals)} new")

        print(f"data: update {len(all_affected_slugs)} Fusus portals ({', '.join(summary_parts)})")

        if changed_stats:
            body_lines.append("")
            body_lines.append("Camera Count Changes:")
            for slug, desc in changed_stats:
                body_lines.append(f"  {slug}: {desc}")

        if mou_changes:
            body_lines.append("")
            body_lines.append("MOU Legal Updates:")
            for slug in sorted(mou_changes):
                body_lines.append(f"  {slug}: MOU terms updated")

        if org_changes:
            body_lines.append("")
            body_lines.append("Organization Metadata Updates:")
            for slug in sorted(org_changes):
                body_lines.append(f"  {slug}: organization profile updated")

        if logo_changes:
            body_lines.append("")
            body_lines.append("Logo Updates:")
            for slug in sorted(logo_changes):
                body_lines.append(f"  {slug}: agency logo updated")

        if new_portals:
            body_lines.append("")
            body_lines.append("New Portals:")
            for slug, desc in new_portals:
                body_lines.append(f"  {slug}")

    elif has_non_data:
        print("chore: update source files")

    if body_lines:
        print()
        print("\n".join(body_lines))

    return 0

if __name__ == "__main__":
    sys.exit(main())

