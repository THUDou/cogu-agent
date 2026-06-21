#!/usr/bin/env python3
"""
PPTX 转 PNG 图片 —— Spire.Presentation.Free
用法:
  python convert_to_images_spire.py --check
  python convert_to_images_spire.py --input=C:\a.pptx --output=C:\slides [--max-slides=10] [--offset=0]
退出码: 0=成功/可用, 1=失败/不可用
"""
import sys
import os
import argparse


def check_spire() -> bool:
    try:
        from spire.presentation import Presentation
        return True
    except ImportError:
        return False


def convert(input_path: str, output_dir: str, max_slides: int, offset: int = 0):
    from spire.presentation import Presentation

    abs_input = os.path.abspath(input_path)
    abs_output = os.path.abspath(output_dir)
    os.makedirs(abs_output, exist_ok=True)

    ppt = Presentation()
    ppt.LoadFromFile(abs_input)

    count = min(ppt.Slides.Count, max_slides)
    for i in range(count):
        out_path = os.path.join(abs_output, f"slide-{offset + i + 1:03d}.png")
        image = ppt.Slides[i].SaveAsImage()
        image.Save(out_path)
        print(f"  导出: {out_path}")

    ppt.Dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='仅检测 Spire 是否可用')
    parser.add_argument('--input', help='PPTX 文件路径')
    parser.add_argument('--output', help='图片输出目录')
    parser.add_argument('--max-slides', type=int, default=3, dest='max_slides')
    parser.add_argument('--offset', type=int, default=0, dest='offset',
                        help='输出文件名编号起始偏移（默认 0）')
    args = parser.parse_args()

    if args.check:
        available = check_spire()
        print(f"spire.presentation: {'可用' if available else '不可用'}")
        sys.exit(0 if available else 1)

    if not args.input or not args.output:
        print("错误: --input, --output 为必填参数", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.input):
        print(f"错误: 文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    try:
        convert(args.input, args.output, args.max_slides, args.offset)
        print(f"转换完成，输出目录: {args.output}")
    except Exception as e:
        print(f"转换失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
