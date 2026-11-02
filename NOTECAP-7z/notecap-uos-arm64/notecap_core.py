#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NoteCapture 跨平台 Markdown 与附件核心；不导入 tkinter 或平台 API。"""

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    Image = None
    HAS_PIL = False


FM_RE = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*\n?(.*)$", re.S)
IMAGE_REF_RE = re.compile(
    r"!\[([^\]\n]*)\]\(\s*(?:<([^>\n]+)>|([^\s)\n]+))(?:\s+[^)]*)?\)")
GENERATED_NAME_RE = re.compile(r"^image-(\d+)\.png$", re.I)
SAFE_ASSET_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def format_markdown_body(text):
    """保守整理正文：统一换行、合并多余空行，围栏代码块保持原样。"""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    fence_char = ""
    fence_len = 0
    for raw_line in text.split("\n"):
        if fence_char:
            lines.append(raw_line)
            closing = re.match(r"^ {0,3}%s{%d,}[ \t]*$" %
                               (re.escape(fence_char), fence_len), raw_line)
            if closing:
                fence_char = ""
                fence_len = 0
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})", raw_line)
        if opening:
            lines.append(raw_line.rstrip())
            fence = opening.group(1)
            fence_char = fence[0]
            fence_len = len(fence)
            continue
        line = raw_line.rstrip(" \t")
        if line and len(raw_line) - len(line) >= 2:
            line += "  "
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
        else:
            lines.append(line)
    return "\n".join(lines).strip("\n")


def safe_asset_path(raw_path):
    """只接受 assets 下单个安全文件名；返回规范 Markdown 相对路径。"""
    value = (raw_path or "").strip().replace("\\", "/")
    parts = value.split("/")
    if len(parts) != 3 or parts[:2] != [".", "assets"]:
        return None
    name = parts[2]
    if name in ("", ".", "..") or not SAFE_ASSET_NAME_RE.fullmatch(name):
        return None
    return "./assets/" + name


def image_fingerprint(image):
    """生成编辑器未保存比较用的指纹，不写文件、不改变图片。"""
    import hashlib
    if image is None:
        return None
    return (image.size, image.mode, hashlib.sha256(image.tobytes()).hexdigest())


def iter_image_references(text):
    """产出代码块外的图片引用，offset 为 Python 字符偏移。"""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    offset = 0
    fence_char = ""
    fence_len = 0
    for line in text.splitlines(keepends=True):
        if fence_char:
            closing = re.match(r"^ {0,3}%s{%d,}[ \t]*$" %
                               (re.escape(fence_char), fence_len), line.rstrip("\r\n"))
            if closing:
                fence_char = ""
                fence_len = 0
            offset += len(line)
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if opening:
            fence = opening.group(1)
            fence_char = fence[0]
            fence_len = len(fence)
            offset += len(line)
            continue
        for match in IMAGE_REF_RE.finditer(line):
            raw_path = match.group(2) if match.group(2) is not None else match.group(3)
            yield {
                "alt": match.group(1),
                "raw_path": raw_path,
                "path": safe_asset_path(raw_path),
                "start": offset + match.start(),
                "end": offset + match.end(),
            }
        offset += len(line)


def reference_at(text, offset):
    """返回光标点击位置所在的代码块外图片引用。"""
    if offset < 0:
        return None
    for ref in iter_image_references(text):
        if ref["start"] <= offset <= ref["end"]:
            return ref
    return None


def next_image_path(paths):
    """在现有文件名之后分配编号，不重排已有附件。"""
    maximum = 0
    for raw in paths:
        path = safe_asset_path(raw)
        match = GENERATED_NAME_RE.fullmatch(path.rsplit("/", 1)[-1]) if path else None
        if match:
            maximum = max(maximum, int(match.group(1)))
    return "./assets/image-%02d.png" % (maximum + 1)


def insert_image_reference(text, path, cursor, alt=None):
    """在光标处插入独立图片段落；返回 (新正文, 插入后光标)。"""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    path = safe_asset_path(path)
    if not path:
        raise ValueError("非法附件路径")
    cursor = max(0, min(int(cursor), len(text)))
    # 光标位于空行或换行边界时，吸收相邻换行，避免产生三行以上的空档。
    before = text[:cursor].rstrip("\n")
    after = text[cursor:].lstrip("\n")
    prefix = "\n\n" if before else ""
    suffix = "\n\n" if after else ""
    if alt is None:
        match = GENERATED_NAME_RE.fullmatch(path.rsplit("/", 1)[-1])
        alt = "图片 %d" % int(match.group(1)) if match else "图片"
    markdown = "![%s](%s)" % (alt, path)
    inserted = prefix + markdown + suffix
    return before + inserted + after, len(before) + len(inserted)


def referenced_asset_paths(text):
    return {ref["path"] for ref in iter_image_references(text) if ref["path"]}


def ensure_attachment_references(text, attachments):
    """保留已有位置，仅把未引用的现有附件补到正文末尾。"""
    body = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    referenced = referenced_asset_paths(body)
    missing = []
    for index, item in enumerate(attachments, 1):
        path = safe_asset_path(item.get("path"))
        if path and path not in referenced:
            missing.append("![%s](%s)" % (item.get("alt") or ("图片 %d" % index), path))
            referenced.add(path)
    if not missing:
        return body
    suffix = "\n\n" if body.strip() else ""
    return body.rstrip("\n") + suffix + "\n\n".join(missing)


def remove_image_references(text, path):
    """删除代码块外指向 path 的引用；独立引用行整行移除。"""
    path = safe_asset_path(path)
    if not path:
        return text
    body = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    refs = [ref for ref in iter_image_references(body) if ref["path"] == path]
    for ref in reversed(refs):
        start, end = ref["start"], ref["end"]
        line_start = body.rfind("\n", 0, start) + 1
        line_end = body.find("\n", end)
        if line_end < 0:
            line_end = len(body)
        if not body[line_start:start].strip() and not body[end:line_end].strip():
            start = line_start
            end = line_end + (1 if line_end < len(body) else 0)
        body = body[:start] + body[end:]
    return body


def attachment_reference_count(text, path):
    path = safe_asset_path(path)
    return sum(1 for ref in iter_image_references(text) if ref["path"] == path)


def attachment_issues(text, attachments):
    """返回 (缺失的有效引用, 非法路径引用)。"""
    available = {safe_asset_path(item.get("path")) for item in attachments}
    missing, invalid = [], []
    for ref in iter_image_references(text):
        if not ref["path"]:
            invalid.append(ref["raw_path"])
        elif ref["path"] not in available:
            missing.append(ref["path"])
    return sorted(set(missing)), sorted(set(invalid))


def _note_title(text, has_images=False):
    for line in (text or "").splitlines():
        title = line.strip()
        if not title:
            continue
        if title.startswith(("```", "~~~")):
            return "代码笔记"
        if IMAGE_REF_RE.fullmatch(title):
            continue
        title = re.sub(r"^(?:#{1,6}|>|[-+*]|\d+[.)])\s+", "", title).strip()
        return (title or "未命名笔记")[:80]
    return "图片笔记" if has_images else "未命名笔记"


def build_note_markdown(slot, text, rel, tags, source_app, created):
    """生成标准 Markdown；正文已有引用位置保持不变。"""
    slot = Path(slot)
    body = format_markdown_body(ensure_attachment_references(text, rel))
    tag_list = [t.strip() for t in (tags or "").replace("，", ",").split(",") if t.strip()]
    lines = [
        "---",
        "id: " + slot.parent.name.replace("-", "") + "-" + slot.name,
        "type: clip",
        "title: " + json.dumps(_note_title(body, bool(rel)), ensure_ascii=False),
        "created: " + created,
        "source:",
        "  app: " + json.dumps(source_app, ensure_ascii=False),
        '  title: ""',
    ]
    if tag_list:
        lines.append("tags:")
        lines.extend("  - " + json.dumps(t, ensure_ascii=False) for t in tag_list)
    else:
        lines.append("tags: []")
    if rel:
        lines.append("assets:")
        for item in rel:
            lines.append('  - path: "%s"' % item["path"])
            lines.append("    kind: " + item.get("kind", "screenshot"))
    else:
        lines.append("assets: []")
    lines.extend(["---", ""])
    if body:
        lines.append(body)
    return "\n".join(lines).rstrip("\n") + "\n"


def normalize_attachments(images=(), keep_extra=(), attachments=None):
    """兼容旧图片列表 API；新 API 使用带稳定 path 的附件字典。"""
    if attachments is None:
        attachments = []
        for index, img in enumerate(list(images) + list(keep_extra), 1):
            attachments.append({"path": "./assets/image-%02d.png" % index,
                                "kind": "screenshot" if index == 1 else "sketch",
                                "img": img})
    normalized, used = [], set()
    for item in attachments:
        path = safe_asset_path(item.get("path"))
        if not path:
            path = next_image_path(used)
        if path in used:
            raise ValueError("附件路径重复: " + path)
        img = item.get("img")
        if img is None:
            raise ValueError("附件缺少图片: " + path)
        normalized.append({"path": path, "kind": item.get("kind", "screenshot"),
                           "alt": item.get("alt", ""), "img": img})
        used.add(path)
    return normalized


def write_note(slot, text, images=(), tags="", source_app="", created=None,
               keep_extra=(), attachments=None, iso_now=None):
    """暂存附件和 Markdown，失败恢复旧 assets；返回实际 created。"""
    if not created:
        if iso_now is None:
            raise ValueError("created 或 iso_now 必须提供一个")
        created = iso_now()
    slot = Path(slot)
    slot.mkdir(parents=True, exist_ok=True)
    assets = slot / "assets"
    staging = Path(tempfile.mkdtemp(prefix=".assets-new-", dir=str(slot)))
    note_tmp = None
    backup = None

    def remove(path):
        if not path or not path.exists():
            return
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    try:
        if assets.is_dir():
            for item in assets.iterdir():
                if item.is_file() and GENERATED_NAME_RE.fullmatch(item.name):
                    continue
                target = staging / item.name
                if item.is_dir():
                    shutil.copytree(str(item), str(target))
                else:
                    shutil.copy2(str(item), str(target))

        rel = normalize_attachments(images, keep_extra, attachments)
        for item in rel:
            item["img"].save(staging / item["path"].rsplit("/", 1)[-1], "PNG")
        document = build_note_markdown(slot, text, rel, tags, source_app, created)
        fd, tmp_name = tempfile.mkstemp(prefix=".note-", suffix=".tmp", dir=str(slot))
        note_tmp = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(document)

        if assets.exists():
            backup = Path(tempfile.mkdtemp(prefix=".assets-old-", dir=str(slot)))
            backup.rmdir()
            os.replace(str(assets), str(backup))
        os.replace(str(staging), str(assets))
        staging = None
        os.replace(str(note_tmp), str(slot / "note.md"))
        note_tmp = None
    except Exception:
        if backup and backup.exists():
            remove(assets)
            os.replace(str(backup), str(assets))
            backup = None
        raise
    finally:
        for path in (staging, note_tmp):
            try:
                remove(path)
            except Exception:
                pass
    try:
        remove(backup)
    except Exception:
        pass
    return created


def _parse_frontmatter(fm):
    created, tag_list = "", []
    in_tags = False
    for line in fm.splitlines():
        if line.startswith("created:"):
            created = line.split(":", 1)[1].strip()
            in_tags = False
        elif line.startswith("tags:"):
            in_tags = True
            inline = line.split(":", 1)[1].strip()
            if inline and inline != "[]":
                try:
                    parsed = json.loads(inline)
                    if isinstance(parsed, list):
                        tag_list = [str(t) for t in parsed]
                except Exception:
                    tag_list = [t.strip().strip('"').strip("'")
                                for t in inline.strip("[]").split(",") if t.strip()]
        elif in_tags:
            item = re.match(r"^\s+-\s+(.+?)\s*$", line)
            if item:
                value = item.group(1)
                try:
                    value = json.loads(value)
                except Exception:
                    value = value.strip('"').strip("'")
                tag_list.append(str(value))
            elif line and not line[0].isspace():
                in_tags = False
    return created, tag_list


def load_note_document(slot):
    """返回正文（含原位置引用）、标签、附件、created、缺失引用。"""
    slot = Path(slot)
    md = slot / "note.md"
    raw = md.read_text(encoding="utf-8") if md.is_file() else ""
    match = FM_RE.match(raw)
    fm, body = (match.group(1), match.group(2)) if match else ("", raw)
    created, tag_list = _parse_frontmatter(fm)
    body = body.replace("\r\n", "\n").replace("\r", "\n").strip("\n")

    paths = []
    for ref in iter_image_references(body):
        if ref["path"] and ref["path"] not in paths:
            paths.append(ref["path"])
    assets = slot / "assets"
    if assets.is_dir():
        for path in sorted(assets.glob("image-*.png")):
            rel = safe_asset_path("./assets/" + path.name)
            if rel and rel not in paths:
                paths.append(rel)

    attachments, missing = [], []
    available = set()
    if HAS_PIL:
        for rel in paths:
            name = rel.rsplit("/", 1)[-1]
            path = assets / name
            try:
                with Image.open(path) as source:
                    img = source.convert("RGB")
                attachments.append({"path": rel, "kind": "screenshot",
                                    "alt": "图片 %d" % (len(attachments) + 1), "img": img})
                available.add(rel)
            except Exception:
                pass
    for ref in iter_image_references(body):
        if ref["path"] and ref["path"] not in available and ref["path"] not in missing:
            missing.append(ref["path"])
    return body, ", ".join(tag_list), attachments, created, missing


def load_note(slot):
    """兼容旧调用：返回 (正文, 标签串, 图片列表, created)。"""
    body, tags, attachments, created, _missing = load_note_document(slot)
    return body, tags, [item["img"] for item in attachments], created
