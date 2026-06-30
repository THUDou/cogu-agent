
import sys
import argparse
import re
from pathlib import Path

HEADING_RE = re.compile(r'^(#{1,6})\s*(.+?)\s*$')
HR_RE = re.compile(r'^\s*[-*]{3,}\s*$')


def normalize_title(title: str) -> str:
    if not title:
        return ''
    text = title.strip()
    text = re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]+', '_', text)
    text = re.sub(r'_+', '_', text).strip('_')
    return text.lower()




def extract_leading_number(text: str) -> int | None:
    if not text:
        return None

    m = re.match(r'^(\d{1,3})', text.strip())
    if m:
        return int(m.group(1))

    text_lower = text.lower().strip()

    m = re.match(r'^(?:slide|page|p)\s*[-_:]?\s*(\d{1,3})', text_lower)
    if m:
        return int(m.group(1))

    m = re.match(r'^第\s*(\d{1,3})\s*[页张]', text_lower)
    if m:
        return int(m.group(1))

    return None


def build_match_maps(svg_stems: list[str]) -> tuple[set[str], dict[str, list[str]], dict[int, list[str]]]:
    exact = set(svg_stems)
    norm_map: dict[str, list[str]] = {}
    num_map: dict[int, list[str]] = {}
    for stem in svg_stems:
        norm = normalize_title(stem)
        if norm:
            norm_map.setdefault(norm, []).append(stem)
        num = extract_leading_number(stem)
        if num is not None:
            num_map.setdefault(num, []).append(stem)
    return exact, norm_map, num_map


def match_title(
    raw_title: str,
    exact: set[str],
    norm_map: dict[str, list[str]],
    num_map: dict[int, list[str]],
    svg_stems: list[str] | None = None,
) -> str | None:
    if raw_title in exact:
        return raw_title
    norm = normalize_title(raw_title)
    if norm in norm_map and len(norm_map[norm]) == 1:
        return norm_map[norm][0]
    num = extract_leading_number(raw_title)
    if num is not None and num in num_map and len(num_map[num]) == 1:
        return num_map[num][0]
    if norm and svg_stems:
        candidates = [s for s in svg_stems if norm in normalize_title(s)]
        if len(candidates) == 1:
            return candidates[0]
    return None


def find_svg_files(project_path: Path) -> list[Path]:
    svg_dir = project_path / 'svg_output'

    if not svg_dir.exists():
        print(f"Error: {svg_dir} directory does not exist")
        return []

    return sorted(svg_dir.glob('*.svg'))


def parse_total_md(
    md_path: Path,
    svg_stems: list[str] | None = None,
    verbose: bool = True,
) -> dict[str, str]:
    if not md_path.exists():
        print(f"Error: {md_path} file does not exist")
        return {}

    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error: Unable to read file {md_path}: {e}")
        return {}

    svg_stems = svg_stems or []
    exact, norm_map, num_map = build_match_maps(svg_stems)

    notes: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    unmatched_headings: list[str] = []

    lines = content.splitlines()
    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            raw_title = m.group(2).strip()
            matched = match_title(raw_title, exact, norm_map, num_map, svg_stems)
            if matched:
                if current_key is not None:
                    text = '\n'.join(current_lines).strip()
                    if current_key in notes and text:
                        notes[current_key] = (notes[current_key].rstrip() + "\n\n" + text).strip()
                    elif current_key not in notes:
                        notes[current_key] = text
                current_key = matched
                current_lines = []
                continue
            unmatched_headings.append(raw_title)

        if HR_RE.match(line):
            continue
        if current_key is not None:
            current_lines.append(line)

    if current_key is not None:
        text = '\n'.join(current_lines).strip()
        if current_key in notes and text:
            notes[current_key] = (notes[current_key].rstrip() + "\n\n" + text).strip()
        elif current_key not in notes:
            notes[current_key] = text

    if verbose and unmatched_headings:
        print("\n[Notice] Found unmatched headings (ignored):")
        for t in unmatched_headings[:10]:
            print(f"  - {t}")
        if len(unmatched_headings) > 10:
            print(f"  ... and {len(unmatched_headings) - 10} more")

    return notes


def check_svg_note_mapping(svg_files: list[Path], notes: dict[str, str]) -> tuple[bool, list[str]]:
    missing_notes = []

    for svg_path in svg_files:
        svg_stem = svg_path.stem

        if svg_stem not in notes:
            missing_notes.append(svg_stem)

    return len(missing_notes) == 0, missing_notes


def split_notes(notes: dict[str, str], output_dir: Path, verbose: bool = True) -> bool:
    if not notes:
        print("Error: No notes content found")
        return False

    output_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0

    for title, content in notes.items():
        output_path = output_dir / f"{title}.md"

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            if verbose:
                print(f"  Generated: {output_path.name}")

            success_count += 1

        except Exception as e:
            if verbose:
                print(f"  Error: Unable to write file {output_path}: {e}")

    if verbose:
        print(f"\n[Done] Successfully generated {success_count}/{len(notes)} file(s)")

    return success_count == len(notes)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='PPT Master - Speaker Notes Splitting Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    %(prog)s projects/<svg_title>_ppt169_YYYYMMDD
    %(prog)s projects/<svg_title>_ppt169_YYYYMMDD -o notes
    %(prog)s projects/<svg_title>_ppt169_YYYYMMDD -q

Features:
    - Reads the total.md speaker notes file
    - Checks the mapping between SVG files and notes
    - Splits notes into multiple individual files
    - Output filenames match SVG filenames
