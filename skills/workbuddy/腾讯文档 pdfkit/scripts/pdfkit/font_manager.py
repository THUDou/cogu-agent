
import os
import sys
import platform


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_BASEDIR = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", ".."))

_BUNDLED_FONT_NAME = "NotoSansSC-Regular.ttf"
BUNDLED_FONT = os.path.join(_SKILL_BASEDIR, "fonts", _BUNDLED_FONT_NAME)


def _is_bundled_font_available():
    return os.path.isfile(BUNDLED_FONT)



_system_cjk_font_cache = None  # 缓存搜索结果


_SYSTEM_FONT_PATHS = {
    "Darwin": [
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/Supplemental/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        os.path.expanduser("~/Library/Fonts/NotoSansSC-Regular.ttf"),
        os.path.expanduser("~/Library/Fonts/NotoSansSC-Regular.otf"),
    ],
    "Linux": [
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/droid/DroidSansFallback.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
        "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
        "/usr/share/fonts/google-droid/DroidSansFallback.ttf",
        "/usr/share/fonts/google-droid-sans-fonts/DroidSansFallback.ttf",
        "/usr/share/fonts/droid/DroidSansFallback.ttf",
        "/usr/share/fonts/truetype/DroidSansFallbackFull.ttf",
    ],
    "Windows": [
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "msyh.ttc"),
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "msyhbd.ttc"),
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "simsun.ttc"),
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "simhei.ttf"),
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "simkai.ttf"),
    ],
}


def _detect_ttc_cjk_index(font_path):
    if not font_path.lower().endswith('.ttc'):
        return 0

    try:
        from fontTools.ttLib import TTCollection
        ttc = TTCollection(font_path)
        test_cp = 0x4E2D
        for idx, font in enumerate(ttc.fonts):
            cmap = font.getBestCmap() or {}
            if test_cp in cmap:
                ttc.close()
                return idx
        ttc.close()
    except ImportError:
        pass
    except Exception:
        pass

    return 0


def find_system_cjk_font():
    global _system_cjk_font_cache
    if _system_cjk_font_cache is not None:
        return _system_cjk_font_cache if _system_cjk_font_cache != "" else None

    system = platform.system()
    candidates = _SYSTEM_FONT_PATHS.get(system, [])

    for key, paths in _SYSTEM_FONT_PATHS.items():
        if key != system:
            candidates.extend(paths)

    ttf_candidates = [p for p in candidates if p.lower().endswith('.ttf')]
    ttc_candidates = [p for p in candidates if not p.lower().endswith('.ttf')]

    for path in ttf_candidates + ttc_candidates:
        if os.path.exists(path):
            _system_cjk_font_cache = path
            return path

    search_dirs = []
    if system == "Darwin":
        search_dirs = ["/System/Library/Fonts", "/Library/Fonts",
                       os.path.expanduser("~/Library/Fonts")]
    elif system == "Linux":
        search_dirs = ["/usr/share/fonts", "/usr/local/share/fonts",
                       os.path.expanduser("~/.fonts")]
    elif system == "Windows":
        search_dirs = [os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")]

    cjk_keywords = ["noto", "cjk", "droid", "wqy", "heiti", "songti",
                     "pingfang", "msyh", "simhei", "simsun", "simkai",
                     "hiragino", "gothic", "mincho"]

    found_ttc = None
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        try:
            for root, dirs, files in os.walk(search_dir):
                for f in files:
                    if not f.lower().endswith(('.ttf', '.ttc', '.otf')):
                        continue
                    if any(kw in f.lower() for kw in cjk_keywords):
                        full_path = os.path.join(root, f)
                        if f.lower().endswith('.ttf'):
                            _system_cjk_font_cache = full_path
                            return full_path
                        elif found_ttc is None:
                            found_ttc = full_path
        except PermissionError:
            continue

    if found_ttc:
        _system_cjk_font_cache = found_ttc
        return found_ttc

    _system_cjk_font_cache = ""  # 标记已搜索过但未找到
    return None


def get_font_index(font_path):
    if not font_path:
        return 0
    return _detect_ttc_cjk_index(font_path)



def resolve_font(text=None, user_font=None, require_full_cjk=False):
    if user_font and os.path.exists(user_font):
        return user_font

    if _is_bundled_font_available():
        return BUNDLED_FONT

    sys_font = find_system_cjk_font()
    if sys_font:
        return sys_font

    print(
        "[font_manager] 警告: 未找到可用的中文字体。"
        "\n  内置字体不存在，本机也未找到 CJK 字体。"
        "\n  请运行 setup.sh (macOS/Linux) 或 setup.bat (Windows) 下载内置字体。",
        file=sys.stderr,
    )
    return None


def get_bundled_font():
    return BUNDLED_FONT if _is_bundled_font_available() else None


def text_covered_by_bundled(text):
    if not text:
        return True, []
    if _is_bundled_font_available():
        return True, []
    return False, list(set(text))



def make_fitz_font(font_path):
    import fitz
    if not font_path or not os.path.exists(font_path):
        return fitz.Font("helv")
    idx = _detect_ttc_cjk_index(font_path)
    return fitz.Font(fontfile=font_path, fontindex=idx)


def make_pil_font(font_path, font_size):
    from PIL import ImageFont
    if not font_path or not os.path.exists(font_path):
        return ImageFont.load_default()
    idx = _detect_ttc_cjk_index(font_path)
    return ImageFont.truetype(font_path, font_size, index=idx)


def register_reportlab_font(font_name, font_path):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if not font_path or not os.path.exists(font_path):
        return False

    try:
        if font_path.lower().endswith('.ttc'):
            idx = _detect_ttc_cjk_index(font_path)
            pdfmetrics.registerFont(TTFont(font_name, font_path, subfontIndex=idx))
        else:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        return True
    except Exception:
        if font_path.lower().endswith('.ttc'):
            for i in range(10):
                try:
                    pdfmetrics.registerFont(TTFont(font_name, font_path, subfontIndex=i))
                    return True
                except Exception:
                    continue
        return False
