
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    from config import CANVAS_FORMATS
except ImportError:
    CANVAS_FORMATS = {
        'ppt169': {
            'name': 'PPT 16:9',
            'dimensions': '1280×720',
            'viewbox': '0 0 1280 720',
            'aspect_ratio': '16:9'
        },
        'ppt43': {
            'name': 'PPT 4:3',
            'dimensions': '1024×768',
            'viewbox': '0 0 1024 768',
            'aspect_ratio': '4:3'
        },
        'wechat': {
            'name': 'WeChat Article Header',
            'dimensions': '900×383',
            'viewbox': '0 0 900 383',
            'aspect_ratio': '2.35:1'
        },
        'xiaohongshu': {
            'name': '小红书',
            'dimensions': '1242×1660',
            'viewbox': '0 0 1242 1660',
            'aspect_ratio': '3:4'
        },
        'moments': {
            'name': 'Moments/Instagram',
            'dimensions': '1080×1080',
            'viewbox': '0 0 1080 1080',
            'aspect_ratio': '1:1'
        },
        'story': {
            'name': 'Story/Vertical',
            'dimensions': '1080×1920',
            'viewbox': '0 0 1080 1920',
            'aspect_ratio': '9:16'
        },
        'banner': {
            'name': 'Horizontal Banner',
            'dimensions': '1920×1080',
            'viewbox': '0 0 1920 1080',
            'aspect_ratio': '16:9'
        },
        'a4': {
            'name': 'A4 Print',
            'dimensions': '1240×1754',
            'viewbox': '0 0 1240 1754',
            'aspect_ratio': '√2:1'
        }
    }

CANVAS_FORMAT_ALIASES = {
    'xhs': 'xiaohongshu',
    'wechat_moment': 'moments',
    'wechat-moment': 'moments',
    '朋友圈': 'moments',
    '小红书': 'xiaohongshu',
}


def normalize_canvas_format(format_key: str) -> str:
    if not format_key:
        return ''
    key = format_key.strip().lower()
    return CANVAS_FORMAT_ALIASES.get(key, key)


def parse_project_name(dir_name: str) -> Dict[str, str]:
    result = {
        'name': dir_name,
        'format': 'unknown',
        'format_name': 'Unknown format',
        'date': 'unknown',
        'date_formatted': 'Unknown date'
    }

    dir_name_lower = dir_name.lower()

    date_match = re.search(r'_(\d{8})$', dir_name)
    if date_match:
        date_str = date_match.group(1)
        result['date'] = date_str
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            result['date_formatted'] = date_obj.strftime('%Y-%m-%d')
        except ValueError:
            pass

    full_match = re.match(r'^(?P<name>.+)_(?P<format>[a-z0-9_-]+)_(?P<date>\d{8})$', dir_name_lower)
    if full_match:
        raw_format = full_match.group('format')
        normalized_format = normalize_canvas_format(raw_format)
        if normalized_format in CANVAS_FORMATS:
            result['format'] = normalized_format
            result['format_name'] = CANVAS_FORMATS[normalized_format]['name']
            result['name'] = dir_name[:len(full_match.group('name'))]
            return result

    sorted_formats = sorted(CANVAS_FORMATS.keys(), key=len, reverse=True)
    for fmt_key in sorted_formats:
        if re.search(rf'_{re.escape(fmt_key)}(?:_\d{{8}})?$', dir_name_lower):
            result['format'] = fmt_key
            result['format_name'] = CANVAS_FORMATS[fmt_key]['name']
            break

    name = re.sub(r'_\d{8}$', '', dir_name)
    if result['format'] != 'unknown':
        name = re.sub(rf'_{re.escape(result["format"])}$', '', name, flags=re.IGNORECASE)
    result['name'] = name

    return result


def get_project_info(project_path: str) -> Dict:
    project_path = Path(project_path)

    parsed = parse_project_name(project_path.name)

    info = {
        'path': str(project_path),
        'dir_name': project_path.name,
        'name': parsed['name'],
        'format': parsed['format'],
        'format_name': parsed['format_name'],
        'date': parsed['date'],
        'date_formatted': parsed['date_formatted'],
        'exists': project_path.exists(),
        'svg_count': 0,
        'has_spec': False,
        'has_readme': False,
        'has_source': False,
        'source_count': 0,
        'spec_file': None,
        'svg_files': []
    }

    if not project_path.exists():
        return info

    info['has_readme'] = (project_path / 'README.md').exists()

    spec_files = ['design_spec.md', '设计规范与内容大纲.md', 'design_specification.md', '设计规范.md']
    for spec_file in spec_files:
        if (project_path / spec_file).exists():
            info['has_spec'] = True
            info['spec_file'] = spec_file
            break

    legacy_source_file = project_path / '来源文档.md'
    sources_dir = project_path / 'sources'
    info['has_source'] = legacy_source_file.exists() or sources_dir.exists()

    if sources_dir.exists():
        info['source_count'] = len([p for p in sources_dir.iterdir() if p.is_file()])

    svg_output = project_path / 'svg_output'
    if svg_output.exists():
        svg_files = sorted(svg_output.glob('*.svg'))
        info['svg_count'] = len(svg_files)
        info['svg_files'] = [f.name for f in svg_files]

    if info['format'] in CANVAS_FORMATS:
        info['canvas_info'] = CANVAS_FORMATS[info['format']]

    return info


def validate_project_structure(project_path: str, verbose: bool = False) -> Tuple[bool, List[str], List[str]]:
    project_path = Path(project_path)
    errors = []
    warnings = []

    try:
        from error_helper import ErrorHelper
        use_helper = True
    except ImportError:
        use_helper = False

    if not project_path.exists():
        msg = f"Project directory does not exist: {project_path}"
        if use_helper and verbose:
            msg += "\n" + ErrorHelper.format_error_message('missing_directory',
                                                           {'project_path': str(project_path)})
        errors.append(msg)
        return False, errors, warnings

    if not project_path.is_dir():
        errors.append(f"Not a valid directory: {project_path}")
        return False, errors, warnings

    if not (project_path / 'README.md').exists():
        msg = "Missing required file: README.md"
        if use_helper and verbose:
            msg += "\n" + ErrorHelper.format_error_message('missing_readme',
                                                           {'project_path': str(project_path)})
        errors.append(msg)

    spec_files = ['design_spec.md', '设计规范与内容大纲.md', 'design_specification.md', '设计规范.md']
    has_spec = any((project_path / f).exists() for f in spec_files)
    if not has_spec:
        msg = "Missing design specification file (suggested filename: design_spec.md)"
        if use_helper and verbose:
            msg += "\n" + ErrorHelper.format_error_message('missing_spec')
        warnings.append(msg)

    svg_output = project_path / 'svg_output'
    if not svg_output.exists():
        msg = "Missing svg_output directory"
        if use_helper and verbose:
            msg += "\n" + \
                ErrorHelper.format_error_message('missing_svg_output')
        errors.append(msg)
    elif not svg_output.is_dir():
        errors.append("svg_output is not a directory")
    else:
        svg_files = list(svg_output.glob('*.svg'))
        if not svg_files:
            msg = "svg_output directory is empty, no SVG files found"
            if use_helper and verbose:
                msg += "\n" + \
                    ErrorHelper.format_error_message('empty_svg_output')
            warnings.append(msg)
        else:
            for svg_file in svg_files:
                if not re.match(r'^(slide_\d+_\w+|P?\d+_.+)\.svg$', svg_file.name):
                    msg = f"Non-standard SVG file naming: {svg_file.name}"
                    if use_helper and verbose:
                        msg += "\n" + ErrorHelper.format_error_message('invalid_svg_naming',
                                                                       {'file_name': svg_file.name})
                    warnings.append(msg)

    dir_name = project_path.name
    if not re.search(r'_\d{8}$', dir_name):
        msg = f"Directory name missing date suffix (_YYYYMMDD): {dir_name}"
        if use_helper and verbose:
            msg += "\n" + \
                ErrorHelper.format_error_message('missing_date_suffix')
        warnings.append(msg)

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def validate_svg_viewbox(svg_files: List[Path], expected_format: Optional[str] = None) -> List[str]:
    warnings = []
    viewbox_pattern = re.compile(r'viewBox="([^"]+)"')
    viewboxes = set()

    expected_viewbox = None
    if expected_format and expected_format in CANVAS_FORMATS:
        expected_viewbox = CANVAS_FORMATS[expected_format]['viewbox']

    for svg_file in svg_files[:10]:  # Check first 10 files
        try:
            with open(svg_file, 'r', encoding='utf-8') as f:
                content = f.read(2000)  # Only read first 2000 characters
                match = viewbox_pattern.search(content)
                if match:
                    viewbox = match.group(1)
                    viewboxes.add(viewbox)

                    if expected_viewbox and viewbox != expected_viewbox:
                        warnings.append(
                            f"{svg_file.name}: viewBox '{viewbox}' does not match expected format "
                            f"'{expected_format}' (expected: '{expected_viewbox}')"
                        )
                else:
                    warnings.append(f"{svg_file.name}: viewBox attribute not found")
        except Exception as e:
            warnings.append(f"{svg_file.name}: Failed to read - {e}")

    if len(viewboxes) > 1:
        warnings.append(f"Multiple different viewBox settings detected: {viewboxes}")

    return warnings


def find_all_projects(base_dir: str) -> List[Path]:
    base_path = Path(base_dir)
    if not base_path.exists():
        return []

    projects = []
    for item in base_path.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            has_svg_output = (item / 'svg_output').exists()
            has_spec = any((item / f).exists() for f in
                           ['design_spec.md', '设计规范与内容大纲.md', 'design_specification.md', '设计规范.md'])

            if has_svg_output or has_spec:
                projects.append(item)

    return sorted(projects)


def format_file_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_project_stats(project_path: str) -> Dict:
    project_path = Path(project_path)
    stats = {
        'total_files': 0,
        'svg_files': 0,
        'md_files': 0,
        'html_files': 0,
        'total_size': 0,
        'svg_size': 0
    }

    if not project_path.exists():
        return stats

    for file in project_path.rglob('*'):
        if file.is_file():
            stats['total_files'] += 1
            file_size = file.stat().st_size
            stats['total_size'] += file_size

            if file.suffix == '.svg':
                stats['svg_files'] += 1
                stats['svg_size'] += file_size
            elif file.suffix == '.md':
                stats['md_files'] += 1
            elif file.suffix == '.html':
                stats['html_files'] += 1

    return stats


if __name__ == '__main__':
    import sys

    def print_usage() -> None:
        print("Usage: python3 project_utils.py <project_path>")

    if len(sys.argv) > 1:
        if sys.argv[1] in {'-h', '--help', 'help'}:
            print_usage()
            sys.exit(0)

        project_path = sys.argv[1]
        info = get_project_info(project_path)

        print(f"\nProject Info: {info['dir_name']}")
        print("=" * 60)
        print(f"Project Name: {info['name']}")
        print(f"Canvas Format: {info['format_name']} ({info['format']})")
        print(f"Created: {info['date_formatted']}")
        print(f"SVG Files: {info['svg_count']}")
        print(f"README: {'Yes' if info['has_readme'] else 'No'}")
        print(f"Design Spec: {'Yes' if info['has_spec'] else 'No'}")

        print("\nValidation Results:")
        print("-" * 60)
        is_valid, errors, warnings = validate_project_structure(project_path)

        if errors:
            print("[ERROR]")
            for error in errors:
                print(f"  - {error}")

        if warnings:
            print("[WARN]")
            for warning in warnings:
                print(f"  - {warning}")

        if is_valid and not warnings:
            print("[OK] Project structure is complete, no issues found")
    else:
        print_usage()
