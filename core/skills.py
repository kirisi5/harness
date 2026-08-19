"""Skill 加载:扫描 skills/ 下 .md 的 frontmatter,按 description 关键词匹配用户问题。"""
import logging
import os
import pathlib
import re

logger = logging.getLogger("harness.skills")


def load_skills_for(user_query: str, skills_dir) -> str:
    """匹配成功后返回所有命中的 skill 全文,用于注入 system prompt。"""
    sd = pathlib.Path(skills_dir)
    if not sd.exists():
        return ""
    matched = []
    for fn in sorted(os.listdir(sd)):
        if not fn.endswith(".md"):
            continue
        try:
            text = (sd / fn).read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("skill 读取失败 %s: %s", fn, e)
            continue
        m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not m:
            continue
        meta = dict(re.findall(r"^(\w+):\s*(.*)$", m.group(1), re.MULTILINE))
        desc = meta.get("description", "")
        if any(kw in user_query for kw in desc.split() if len(kw) > 2):
            matched.append(text)
            logger.info("skill 命中: %s", fn)
    return "\n\n".join(matched)
