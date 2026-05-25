import json
import os
import re
from collections import Counter, defaultdict

from mutagen import File


SUPPORTED_AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".alac",
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".ogg",
    ".wav",
    ".wma",
}

# Personal spelling overrides for names that generic title-casing handles poorly.
CANONICAL_ARTIST_OVERRIDES = {
    "queens of the stone age": "Queens of the Stone Age",
}


def _first_tag(audio, keys):
    if not audio:
        return None

    for key in keys:
        value = audio.get(key)
        if not value:
            continue
        if isinstance(value, list):
            value = value[0] if value else None
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text

    return None


def _normalize_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _casefold(value):
    return _normalize_text(value).casefold()


def _parse_track_number(value):
    if not value:
        return None

    if isinstance(value, tuple):
        return value[0] if value else None

    match = re.search(r"\d+", str(value))
    if not match:
        return None

    return int(match.group(0))


def _filename_stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def _strip_track_prefix(name):
    return re.sub(r"^\s*\d+\s*[-_. ]+\s*", "", name).strip()


def _looks_like_title_match(filename, title):
    if not filename or not title:
        return False
    normalized_filename = _casefold(_strip_track_prefix(filename))
    normalized_title = _casefold(title)
    return normalized_filename == normalized_title


def read_track_metadata(path, root_dir):
    audio = File(path, easy=True)
    ext = os.path.splitext(path)[1].lower()
    rel_path = os.path.relpath(path, root_dir)
    track_raw = _first_tag(audio, ["tracknumber", "track"])

    return {
        "path": path,
        "relative_path": rel_path,
        "folder": os.path.dirname(rel_path),
        "filename": os.path.basename(path),
        "filename_stem": _filename_stem(path),
        "ext": ext,
        "title": _normalize_text(_first_tag(audio, ["title"])),
        "artist": _normalize_text(_first_tag(audio, ["artist"])),
        "album": _normalize_text(_first_tag(audio, ["album"])),
        "album_artist": _normalize_text(_first_tag(audio, ["albumartist", "album artist"])),
        "date": _normalize_text(_first_tag(audio, ["date", "year"])),
        "genre": _normalize_text(_first_tag(audio, ["genre"])),
        "track_number": _parse_track_number(track_raw),
        "track_raw": _normalize_text(track_raw),
    }


def iter_audio_files(root_dir):
    for root, _, files in os.walk(root_dir):
        for filename in sorted(files):
            ext = os.path.splitext(filename)[1].lower()
            if ext in SUPPORTED_AUDIO_EXTENSIONS:
                yield os.path.join(root, filename)


def _issue(issue_type, severity, message, path=None, details=None):
    return {
        "type": issue_type,
        "severity": severity,
        "message": message,
        "path": path,
        "details": details or {},
    }


def _find_case_variants(tracks, field):
    by_folded = defaultdict(Counter)
    for track in tracks:
        value = track.get(field)
        if value:
            by_folded[_casefold(value)][value] += 1

    issues = []
    for folded, variants in by_folded.items():
        if folded and len(variants) > 1:
            canonical = variants.most_common(1)[0][0]
            issues.append(_issue(
                f"{field}_case_variants",
                "warning",
                f"{field.replace('_', ' ').title()} has casing variants.",
                details={
                    "canonical_guess": canonical,
                    "variants": dict(variants),
                },
            ))
    return issues


def _find_known_name_mismatches(tracks):
    issues = []
    for track in tracks:
        for field in ["artist", "album_artist"]:
            value = track.get(field)
            if not value:
                continue

            canonical = CANONICAL_ARTIST_OVERRIDES.get(_casefold(value))
            if canonical and value != canonical:
                issues.append(_issue(
                    f"{field}_known_name_mismatch",
                    "info",
                    f"{field.replace('_', ' ').title()} differs from known canonical spelling.",
                    path=track["relative_path"],
                    details={
                        "value": value,
                        "canonical": canonical,
                    },
                ))

    return issues


def _audit_track(track):
    issues = []

    if not track["title"]:
        issues.append(_issue(
            "missing_title",
            "warning",
            "Track is missing title metadata.",
            path=track["relative_path"],
        ))
    elif not _looks_like_title_match(track["filename_stem"], track["title"]):
        issues.append(_issue(
            "filename_title_mismatch",
            "info",
            "Filename does not match title metadata after removing a leading track number.",
            path=track["relative_path"],
            details={
                "filename": track["filename_stem"],
                "title": track["title"],
            },
        ))

    for field in ["artist", "album", "track_number"]:
        if not track[field]:
            issues.append(_issue(
                f"missing_{field}",
                "warning",
                f"Track is missing {field.replace('_', ' ')} metadata.",
                path=track["relative_path"],
            ))

    if not track["album_artist"]:
        issues.append(_issue(
            "missing_album_artist",
            "info",
            "Track is missing album artist metadata.",
            path=track["relative_path"],
        ))

    return issues


def _audit_folders(tracks):
    issues = []
    by_folder = defaultdict(list)
    for track in tracks:
        by_folder[track["folder"]].append(track)

    for folder, folder_tracks in by_folder.items():
        albums = {track["album"] for track in folder_tracks if track["album"]}
        album_artists = {track["album_artist"] for track in folder_tracks if track["album_artist"]}
        track_numbers = [
            track["track_number"]
            for track in folder_tracks
            if track["track_number"] is not None
        ]

        if len(albums) > 1:
            issues.append(_issue(
                "mixed_album_names_in_folder",
                "warning",
                "Folder contains multiple album names.",
                details={
                    "folder": folder,
                    "albums": sorted(albums),
                },
            ))

        if len(album_artists) > 1:
            issues.append(_issue(
                "mixed_album_artists_in_folder",
                "info",
                "Folder contains multiple album artists.",
                details={
                    "folder": folder,
                    "album_artists": sorted(album_artists),
                },
            ))

        duplicates = [
            number
            for number, count in Counter(track_numbers).items()
            if count > 1
        ]
        if duplicates:
            issues.append(_issue(
                "duplicate_track_numbers_in_folder",
                "warning",
                "Folder contains duplicate track numbers.",
                details={
                    "folder": folder,
                    "track_numbers": duplicates,
                },
            ))

    return issues


def audit_metadata(root_dir):
    tracks = [
        read_track_metadata(path, root_dir)
        for path in iter_audio_files(root_dir)
    ]
    issues = []

    for track in tracks:
        issues.extend(_audit_track(track))

    issues.extend(_audit_folders(tracks))
    for field in ["artist", "album", "album_artist", "genre"]:
        issues.extend(_find_case_variants(tracks, field))
    issues.extend(_find_known_name_mismatches(tracks))

    return {
        "root_dir": root_dir,
        "track_count": len(tracks),
        "issue_count": len(issues),
        "tracks": tracks,
        "issues": issues,
    }


def write_metadata_audit_reports(audit, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "metadata_audit.json")
    md_path = os.path.join(output_dir, "metadata_audit.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)

    lines = [
        "# Metadata Audit",
        "",
        f"- Root: `{audit['root_dir']}`",
        f"- Tracks scanned: {audit['track_count']}",
        f"- Issues found: {audit['issue_count']}",
        "",
        "| Severity | Type | Path | Message |",
        "|----------|------|------|---------|",
    ]

    for issue in audit["issues"]:
        lines.append(
            f"| {_markdown_cell(issue['severity'])} | {_markdown_cell(issue['type'])} | "
            f"{_markdown_cell(issue.get('path') or issue.get('details', {}).get('folder', ''))} | "
            f"{_markdown_cell(issue['message'])} |"
        )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return {
        "json": json_path,
        "markdown": md_path,
    }


def _markdown_cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def _safe_filename_part(value):
    value = _normalize_text(value)
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = value.rstrip(" .")
    return value or "Untitled"


def _format_track_number(track_number):
    if track_number is None:
        return None
    return f"{track_number:02d}"


def build_filename_normalization_plan(audit):
    """
    Builds a read-only filename normalization plan from metadata audit data.

    The plan proposes filename-only changes within each file's current folder.
    It does not move folders or apply changes.
    """
    actions = []
    target_counts = Counter()

    for track in audit["tracks"]:
        track_number = _format_track_number(track.get("track_number"))
        title = track.get("title")

        if not track_number or not title:
            action = {
                "status": "blocked",
                "reason": "missing track number or title",
                "path": track["relative_path"],
                "proposed_path": None,
                "current_filename": track["filename"],
                "proposed_filename": None,
            }
        else:
            proposed_filename = f"{track_number} - {_safe_filename_part(title)}{track['ext']}"
            proposed_path = os.path.join(track["folder"], proposed_filename) if track["folder"] else proposed_filename
            status = "no_change" if proposed_path == track["relative_path"] else "rename"
            action = {
                "status": status,
                "reason": None,
                "path": track["relative_path"],
                "proposed_path": proposed_path,
                "current_filename": track["filename"],
                "proposed_filename": proposed_filename,
            }
            target_counts[proposed_path] += 1

        actions.append(action)

    for action in actions:
        proposed_path = action.get("proposed_path")
        if proposed_path and target_counts[proposed_path] > 1:
            action["status"] = "blocked"
            action["reason"] = "target filename collision"

    return {
        "root_dir": audit["root_dir"],
        "track_count": audit["track_count"],
        "rename_count": sum(1 for action in actions if action["status"] == "rename"),
        "blocked_count": sum(1 for action in actions if action["status"] == "blocked"),
        "actions": actions,
    }


def write_filename_plan_reports(plan, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "filename_normalization_plan.json")
    md_path = os.path.join(output_dir, "filename_normalization_plan.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)

    lines = [
        "# Filename Normalization Plan",
        "",
        f"- Root: `{plan['root_dir']}`",
        f"- Tracks scanned: {plan['track_count']}",
        f"- Proposed renames: {plan['rename_count']}",
        f"- Blocked actions: {plan['blocked_count']}",
        "",
        "| Status | Current Path | Proposed Path | Reason |",
        "|--------|--------------|---------------|--------|",
    ]

    for action in plan["actions"]:
        lines.append(
            f"| {_markdown_cell(action['status'])} | "
            f"{_markdown_cell(action['path'])} | "
            f"{_markdown_cell(action.get('proposed_path') or '')} | "
            f"{_markdown_cell(action.get('reason') or '')} |"
        )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return {
        "json": json_path,
        "markdown": md_path,
    }
