#!/usr/bin/env python3
"""
mineru-api.py - 使用 MinerU 精准解析 API 将 PDF 转换为 Markdown

用法:
    python3 mineru-api.py <pdf_path> [--lang ch|en]

环境变量:
    MINERU_API_TOKEN - MinerU API Token (从 bashrc 加载)
"""

import argparse
import os
import sys
import time
import zipfile
import requests
from pathlib import Path

BASE_URL = "https://mineru.net/api/v4"
DEFAULT_TIMEOUT = 300  # 5 minutes
POLL_INTERVAL = 3
MODEL_VERSION = "vlm"


def get_token():
    """从环境变量获取 API Token"""
    token = os.environ.get("MINERU_API_TOKEN")
    if not token:
        print("Error: MINERU_API_TOKEN not set. Add to ~/.bashrc:")
        print("  export MINERU_API_TOKEN='your_token_here'")
        sys.exit(1)
    return token


def upload_and_parse(pdf_path: Path, token: str, language: str = "ch") -> str:
    """
    上传 PDF 并提交解析任务

    返回: task_id
    """
    file_name = pdf_path.name

    # 1. 获取签名上传 URL
    url = f"{BASE_URL}/file-urls/batch"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = {
        "files": [{"name": file_name}],
        "model_version": MODEL_VERSION,  # 高质量 VLM 模型
        "language": language,
        "enable_formula": True,
        "enable_table": True,
    }

    resp = requests.post(url, headers=headers, json=data)
    result = resp.json()

    if result.get("code") != 0:
        print(f"Error: 获取上传链接失败 - {result.get('msg')}")
        sys.exit(1)

    batch_id = result["data"]["batch_id"]
    file_url = result["data"]["file_urls"][0]
    print(f"  任务已创建, batch_id: {batch_id}")

    # 2. PUT 上传文件到 OSS
    print(f"  上传文件...")
    with open(pdf_path, "rb") as f:
        put_resp = requests.put(file_url, data=f)
        if put_resp.status_code not in (200, 201):
            print(f"Error: 文件上传失败, HTTP {put_resp.status_code}")
            sys.exit(1)

    print(f"  文件上传成功")
    return batch_id


def poll_batch_result(batch_id: str, token: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    轮询批量任务结果

    返回: 包含 full_zip_url 的结果字典
    """
    url = f"{BASE_URL}/extract-results/batch/{batch_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    state_labels = {
        "waiting-file": "等待文件上传",
        "pending": "排队中",
        "running": "解析中",
        "converting": "格式转换中",
    }

    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(url, headers=headers)
        result = resp.json()

        if result.get("code") != 0:
            print(f"Error: 查询失败 - {result.get('msg')}")
            sys.exit(1)

        extract_results = result["data"]["extract_result"]
        for item in extract_results:
            state = item.get("state")
            elapsed = int(time.time() - start)

            if state == "done":
                return item

            if state == "failed":
                print(f"[{elapsed}s] 解析失败: {item.get('err_msg')}")
                sys.exit(1)

            # 显示进度
            if state == "running" and "extract_progress" in item:
                progress = item["extract_progress"]
                print(f"[{elapsed}s] 解析中... {progress.get('extracted_pages')}/{progress.get('total_pages')} 页")
            else:
                print(f"[{elapsed}s] {state_labels.get(state, state)}...")

        time.sleep(POLL_INTERVAL)

    print(f"Error: 轮询超时 ({timeout}s)")
    sys.exit(1)


def download_and_extract(zip_url: str, output_dir: Path, stem: str) -> Path:
    """
    下载 ZIP 并提取 Markdown

    返回: markdown 文件路径
    """
    print(f"  下载结果 ZIP...")
    resp = requests.get(zip_url, stream=True)

    zip_path = output_dir / f"{stem}_result.zip"
    with open(zip_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"  解压 ZIP...")
    extract_dir = output_dir / f"{stem}_extracted"
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    # 找到 full.md 文件
    md_file = None
    for f in extract_dir.rglob("*.md"):
        if "full" in f.name or f.name == f"{stem}.md":
            md_file = f
            break

    if not md_file:
        # 兜底：找第一个 .md 文件
        md_file = next(extract_dir.rglob("*.md"), None)

    if md_file:
        # 移动到目标位置
        target_md = output_dir / f"{stem}.md"
        target_md.write_text(md_file.read_text(encoding="utf-8"))

        # 提取 images 目录
        images_src = None
        for d in extract_dir.rglob("images"):
            if d.is_dir():
                images_src = d
                break

        if images_src:
            target_images = output_dir / f"{stem}_images"
            if target_images.exists():
                import shutil
                shutil.rmtree(target_images)
            import shutil
            shutil.copytree(images_src, target_images)
            print(f"  提取图片到: {target_images}")

        # 清理临时文件
        import shutil
        shutil.rmtree(extract_dir)
        zip_path.unlink()

        return target_md

    print(f"Error: ZIP 中未找到 Markdown 文件")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="MinerU API PDF 转 Markdown")
    parser.add_argument("pdf_path", help="PDF 文件路径")
    parser.add_argument("--lang", "-l", default="ch", choices=["ch", "en"],
                        help="文档语言 (默认 ch)")
    parser.add_argument("--timeout", "-t", type=int, default=DEFAULT_TIMEOUT,
                        help="超时时间 (秒)")

    args = parser.parse_args()

    pdf_path = Path(args.pdf_path).resolve()
    if not pdf_path.exists():
        print(f"Error: 文件不存在: {pdf_path}")
        sys.exit(1)

    output_dir = pdf_path.parent
    stem = pdf_path.stem

    print(f"=== MinerU API ===")
    print(f"  PDF:    {pdf_path}")
    print(f"  Output: {output_dir}/{stem}.md")
    print(f"  Lang:   {args.lang}")
    print(f"  Model:  {MODEL_VERSION}")
    print()

    token = get_token()

    # 1. 上传并提交任务
    print("[1/3] 上传文件并提交解析任务...")
    batch_id = upload_and_parse(pdf_path, token, args.lang)

    # 2. 等待解析完成
    print("[2/3] 等待解析完成...")
    result = poll_batch_result(batch_id, token, args.timeout)

    # 3. 下载并提取结果
    print("[3/3] 下载并提取结果...")
    zip_url = result.get("full_zip_url")
    if not zip_url:
        print(f"Error: 未获取到 ZIP URL")
        sys.exit(1)

    md_path = download_and_extract(zip_url, output_dir, stem)

    print()
    print(f"Done! {md_path}")
    if (output_dir / f"{stem}_images").exists():
        print(f"  + {stem}_images/")


if __name__ == "__main__":
    main()
