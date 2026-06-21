#!/usr/bin/env python3
"""
docx-craft template matcher.

Given a document type description, suggest the best matching recipe.
This is a helper for the Claude agent — the actual matching decision
is made by the LLM based on semantic understanding.

Usage:
    python scripts/template_match.py --type "行业分析报告"
    python scripts/template_match.py --type "学术论文"
    python scripts/template_match.py --type "通知"
    python scripts/template_match.py --list
"""

import argparse
import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

RECIPES_DIR = os.path.join(os.path.dirname(__file__), '..', 'recipes')

RECIPE_KEYWORDS = {
    'academic': ['论文', '学术', '综述', 'thesis', 'paper', 'dissertation', 'journal', '学术'],
    'report': ['报告', '分析', '行业', '市场', '商业', '年度', 'report', 'analysis', '行业分析', '调研'],
    'government': ['公文', '通知', '函', '决定', '批复', '意见', '公告', '通报', 'government', 'official', 'GB/T 9704'],
    'memo': ['备忘录', 'memo', 'memorandum'],
    'letter': ['信函', '邀请函', '推荐信', 'letter', 'cover letter', '邀请', '感谢信'],
    'meeting_decision': ['决策类会议纪要', '决策会议', '战略会议', '项目评审会', '决策类'],
    'meeting_daily': ['日常例会', '周例会', '例会', '站会', '定期会议', '部门会议'],
    'meeting_seminar': ['研讨会议', '研讨会', '研讨会纪要', '座谈', '工作坊', '研讨主题'],
}


def list_recipes():
    """List all available recipes with their labels."""
    for filename in sorted(os.listdir(RECIPES_DIR)):
        if filename.endswith('.json'):
            filepath = os.path.join(RECIPES_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                recipe = json.load(f)
            logger.info(f"  {recipe['name']:15s} — {recipe.get('label', '')}")


def match_recipe(doc_type):
    """Match a document type description to a recipe name."""
    doc_type_lower = doc_type.lower()
    scores = {}
    for recipe_name, keywords in RECIPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in doc_type_lower)
        scores[recipe_name] = score

    best = max(scores, key=scores.get)
    if not scores or scores.get(best, 0) == 0:
        return 'report'  # default fallback

    # Load and display the matched recipe
    filepath = os.path.join(RECIPES_DIR, f'{best}.json')
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            recipe = json.load(f)
        recipe_info = {
            'match': best,
            'label': recipe.get('label', ''),
            'fonts': recipe.get('fonts', {}),
            'page': recipe.get('page', {}),
        }
        logger.info(json.dumps(recipe_info, ensure_ascii=False, indent=2))
        return recipe_info
    else:
        info = {'match': best}
        logger.info(json.dumps(info, ensure_ascii=False))
        return info


def main():
    parser = argparse.ArgumentParser(description='docx-craft template matcher')
    parser.add_argument('--type', type=str, help='Document type description to match')
    parser.add_argument('--list', action='store_true', help='List all available recipes')
    args = parser.parse_args()

    if args.list:
        list_recipes()
    elif args.type:
        match_recipe(args.type)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
