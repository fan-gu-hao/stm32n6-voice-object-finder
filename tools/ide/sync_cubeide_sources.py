#!/usr/bin/env python3
"""將 Course17 的 Src/Inc 完整連結到既有 CubeIDE 專案。

預設僅預覽；--apply 會備份並更新 .project。執行前請關閉 CubeIDE。
"""

import argparse
from datetime import datetime
import hashlib
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET


def resolve_link(uri, project_dir):
    if uri.startswith("PARENT-2-PROJECT_LOC/"):
        return (project_dir.parent.parent / uri.split("/", 1)[1]).resolve()
    if uri.startswith("PROJECT_LOC/"):
        return (project_dir / uri.split("/", 1)[1]).resolve()
    if uri.startswith("file:"):
        parsed = urlparse(uri)
        if parsed.netloc not in ("", "localhost"):
            raise ValueError("遇到遠端連結，請先核對設定：" + uri)
        return Path(unquote(parsed.path)).resolve()
    path = Path(uri)
    if path.is_absolute():
        return path.resolve()
    raise ValueError("無法安全判定既有連結，請貼回此訊息：" + uri)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path,
        default=Path.home() / "STM32N6ai/course17_voice_object_finder",
        help="Course17 專案根目錄",
    )
    parser.add_argument("--apply", action="store_true", help="備份後套用變更")
    args = parser.parse_args()
    fw = args.root.expanduser().resolve() / "firmware"
    project_dir = fw / "STM32CubeIDE/STM32N6570-DK"
    project = project_dir / ".project"
    if not project.is_file():
        raise ValueError("找不到已確認的專案設定：" + str(project))
    for folder in ("Src", "Inc"):
        if not (fw / folder).is_dir():
            raise ValueError("找不到資料夾：" + str(fw / folder))
    if not (fw / "Src/finder_kws.c").is_file():
        raise ValueError("找不到 finder_kws.c，請確認 --root 指向正確的 Course17")

    original = project.read_bytes()
    original_hash = hashlib.sha256(original).digest()
    xml_parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    root = ET.fromstring(original, parser=xml_parser)
    if root.tag != "projectDescription":
        raise ValueError("不是預期的 Eclipse 專案設定")
    links = root.find("linkedResources")
    if links is None:
        links = ET.SubElement(root, "linkedResources")
    changed = False
    for folder in ("Src", "Inc"):
        selected = []
        for link in links.findall("link"):
            name = link.findtext("name", "")
            if name == folder or name.startswith(folder + "/"):
                selected.append(link)
                uri = link.findtext("locationURI") or link.findtext("location", "")
                if uri.startswith("virtual:"):
                    continue
                actual = resolve_link(uri, project_dir)
                expected = (fw / name).resolve()
                if actual != expected:
                    raise ValueError(
                        "既有連結指向其他位置，停止修改：" + name + " → " + uri
                    )
        uri = "PARENT-2-PROJECT_LOC/" + folder
        if (len(selected) == 1
                and selected[0].findtext("name") == folder
                and selected[0].findtext("type") == "2"
                and selected[0].findtext("locationURI") == uri):
            print("已完整連結：", folder, "→", fw / folder)
            continue
        for link in selected:
            links.remove(link)
        link = ET.SubElement(links, "link")
        ET.SubElement(link, "name").text = folder
        ET.SubElement(link, "type").text = "2"
        ET.SubElement(link, "locationURI").text = uri
        changed = True
        print("整合資料夾連結：", folder, "→", fw / folder)

    print("專案名稱：", root.findtext("name"))
    print("變更檔案：", project)
    cp = project_dir / ".cproject"
    if cp.is_file():
        builders = list(ET.parse(cp).getroot().iter("builder"))
        if any(b.get("managedBuildOn") == "true" for b in builders):
            print("建置設定仍是 IDE 自動建置；正式建置請沿用目前的終端機 Makefile 指令。")
    if not changed:
        print("Src 與 Inc 已同步，無須修改。")
        return
    if not args.apply:
        print("以上是預覽。關閉 CubeIDE 後，加入 --apply 即可套用。")
        return

    ET.indent(root, space="\t")
    updated = ET.tostring(root, encoding="UTF-8", xml_declaration=True) + b"\n"
    ET.fromstring(updated)
    backup = project.with_name(
        ".project.backup_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    )
    if hashlib.sha256(project.read_bytes()).digest() != original_hash:
        raise ValueError("專案設定在執行期間被修改，請關閉 CubeIDE 後重試。")
    shutil.copy2(project, backup)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=project_dir, prefix=".project.sync_", delete=False) as out:
            temporary = Path(out.name)
            out.write(updated)
            out.flush()
            os.fsync(out.fileno())
        temporary.chmod(stat.S_IMODE(project.stat().st_mode))
        if hashlib.sha256(project.read_bytes()).digest() != original_hash:
            raise ValueError("專案設定被其他程式修改，未套用變更。")
        os.replace(temporary, project)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print("備份位置：", backup)
    print("完成。重新開啟 CubeIDE，選取專案按 F5，再執行索引重建（Index → Rebuild）。")
    print("finder_kws.c 會出現在 Src；今後新增 Src/Inc 檔案，重新整理即可顯示。")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, ET.ParseError) as error:
        print("未完成：", error, file=sys.stderr)
        sys.exit(1)
