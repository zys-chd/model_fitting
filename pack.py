#!/usr/bin/env python3
"""
模型拟合工具 — 打包脚本

将项目文件打包为 ZIP，嵌入 C launcher 并编译为独立可执行文件。

用法:
    python pack.py              # 完整打包 + 编译
    python pack.py --zip-only   # 仅生成 resource.h
    python pack.py --compile    # 仅编译（需要已有 resource.h）

输出: launcher/model_fitting (macOS/Linux) 或 launcher/model_fitting.exe (Windows)

前置条件:
    - macOS/Linux: cc 或 gcc 可用
    - Windows:     Visual Studio 或 MinGW-w64
    - 所有平台:     zlib 开发库已安装
"""

import os
import sys
import struct
import zipfile
import zlib
import subprocess
import shutil
from pathlib import Path

HERE = Path(__file__).parent
LAUNCHER_DIR = HERE / "launcher"
BUILD_SCRIPT_PATH = HERE / "build_chatgpt.py"

# ── 排除列表 ─────────────────────────────────────────
EXCLUDE_DIRS = {
    ".git", "__pycache__", ".pytest_cache",
    "build", "dist", "log", ".venv_pack",
    ".Spotlight-V100", ".fseventsd", ".Trashes",
    ".TemporaryItems", "$RECYCLE.BIN",
    "launcher",  # 编译工具目录，不是运行时资源
}

EXCLUDE_FILES = {
    "model_fitting.zip",
    "保存文件.rda",
    "build_chatgpt.py",
    "pack.py",  # 打包脚本，不是运行时资源
    # 测试数据太大，不嵌入（用户自己准备数据）
    "test_weibull.csv",
    "test.xlsx",
}

# 压缩级别: 0=store, 6=默认, 9=最高
COMPRESS_LEVEL = 9


def should_exclude(relpath: str) -> bool:
    """检查路径是否应排除。"""
    # 检查每个路径段
    parts = Path(relpath).parts
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True
    # 检查文件名
    fname = os.path.basename(relpath)
    if fname in EXCLUDE_FILES:
        return True
    # 排除 macOS 资源分支文件
    if fname.startswith("._"):
        return True
    # 排除 .spec 文件
    if fname.endswith(".spec"):
        return True
    return False


def create_zip() -> bytes:
    """创建项目的 ZIP 压缩包，返回字节数据。"""
    buf = []

    # 收集所有文件
    files = []
    for root, dirs, names in os.walk(HERE):
        # 就地过滤目录
        dirs[:] = [d for d in sorted(dirs) if d not in EXCLUDE_DIRS]
        for name in sorted(names):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, HERE)
            if should_exclude(rel):
                continue
            files.append((full, rel))

    print(f"打包 {len(files)} 个文件 ...")

    # 用低级 API 写 ZIP，以便控制输出格式
    # 写入 ZIP 缓冲区
    entries = []  # (local_header_offset, central_dir_data)
    local_headers = []
    offset = 0

    for full_path, rel_path in files:
        with open(full_path, "rb") as f:
            data = f.read()

        # 统一路径分隔符为 '/'
        zip_name = "model_fitting/" + rel_path.replace("\\", "/")

        # 压缩
        crc = zlib.crc32(data) & 0xFFFFFFFF
        if COMPRESS_LEVEL > 0:
            compressed = zlib.compress(data, COMPRESS_LEVEL)
            if len(compressed) < len(data):
                method = 8  # DEFLATE
                comp_data = compressed[2:-4]  # 去掉 zlib header/trailer, 只保留 raw deflate
            else:
                method = 0  # STORE
                comp_data = data
        else:
            method = 0
            comp_data = data

        comp_size = len(comp_data)
        uncomp_size = len(data)

        # 构建 local file header
        name_bytes = zip_name.encode("utf-8")
        local_header = bytearray()
        local_header += struct.pack("<I", 0x04034b50)   # signature
        local_header += struct.pack("<H", 20)            # version needed
        local_header += struct.pack("<H", 0x0800)        # flags (UTF-8)
        local_header += struct.pack("<H", method)        # compression method
        local_header += struct.pack("<H", 0)             # last mod time
        local_header += struct.pack("<H", 0)             # last mod date
        local_header += struct.pack("<I", crc)           # crc32
        local_header += struct.pack("<I", comp_size)     # compressed size
        local_header += struct.pack("<I", uncomp_size)   # uncompressed size
        local_header += struct.pack("<H", len(name_bytes))  # filename length
        local_header += struct.pack("<H", 0)             # extra field length
        local_header += name_bytes

        # 构建 central directory entry
        cd_entry = bytearray()
        cd_entry += struct.pack("<I", 0x02014b50)       # signature
        cd_entry += struct.pack("<H", 20)                # version made by
        cd_entry += struct.pack("<H", 20)                # version needed
        cd_entry += struct.pack("<H", 0x0800)            # flags (UTF-8)
        cd_entry += struct.pack("<H", method)            # compression method
        cd_entry += struct.pack("<H", 0)                 # last mod time
        cd_entry += struct.pack("<H", 0)                 # last mod date
        cd_entry += struct.pack("<I", crc)               # crc32
        cd_entry += struct.pack("<I", comp_size)         # compressed size
        cd_entry += struct.pack("<I", uncomp_size)       # uncompressed size
        cd_entry += struct.pack("<H", len(name_bytes))   # filename length
        cd_entry += struct.pack("<H", 0)                 # extra field length
        cd_entry += struct.pack("<H", 0)                 # file comment length
        cd_entry += struct.pack("<H", 0)                 # disk number start
        cd_entry += struct.pack("<H", 0)                 # internal file attributes
        cd_entry += struct.pack("<I", 0)                 # external file attributes
        cd_entry += struct.pack("<I", offset)            # relative offset of local header
        cd_entry += name_bytes

        entries.append((len(local_headers), cd_entry))
        local_headers.append(bytes(local_header) + comp_data)
        offset += len(local_headers[-1])

    # 组装输出
    result = bytearray()
    cd_start = 0

    for lh in local_headers:
        result += lh
    cd_start = len(result)

    for _, cd in entries:
        result += cd
    cd_end = len(result)

    # EOCD record
    result += struct.pack("<I", 0x06054b50)  # signature
    result += struct.pack("<H", 0)            # disk number
    result += struct.pack("<H", 0)            # disk with CD
    result += struct.pack("<H", len(entries)) # entries on this disk
    result += struct.pack("<H", len(entries)) # total entries
    result += struct.pack("<I", cd_end - cd_start)  # size of CD
    result += struct.pack("<I", cd_start)     # offset of CD
    result += struct.pack("<H", 0)            # comment length

    print(f"  ZIP 大小: {len(result) / 1024:.1f} KB")
    return bytes(result)


def generate_header(zip_data: bytes, output_path: Path):
    """将 ZIP 数据生成为 C 头文件。"""
    lines = [
        "/* 自动生成 — 由 pack.py 创建 */",
        "/* 包含模型拟合工具的嵌入式资源 ZIP */",
        "",
        f"/* 压缩后大小: {len(zip_data)} 字节 */",
    ]

    # 写为 C 数组，每行 16 字节
    array_name = "resource_zip"
    size_name = "resource_zip_size"

    data_lines = []
    for i in range(0, len(zip_data), 16):
        chunk = zip_data[i:i + 16]
        hex_bytes = ", ".join(f"0x{b:02x}" for b in chunk)
        data_lines.append(f"    {hex_bytes},")

    lines.append(f"static const unsigned char {array_name}[] = {{")
    lines.extend(data_lines)
    lines.append("};")
    lines.append("")
    lines.append(f"static const size_t {size_name} = sizeof({array_name});")
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"  生成: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")


def find_compiler():
    """查找可用的 C 编译器。"""
    candidates = ["cc", "gcc", "clang"]

    # macOS 优先用 clang
    if sys.platform == "darwin":
        candidates = ["clang", "cc", "gcc"]

    for cc in candidates:
        if shutil.which(cc):
            return cc
    return None


def compile_launcher():
    """编译 launcher.c。"""
    cc = find_compiler()
    if not cc:
        print("[错误] 找不到 C 编译器 (cc/gcc/clang)")
        print("  macOS:  xcode-select --install")
        print("  Linux:  sudo apt install build-essential")
        print("  Windows: 安装 Visual Studio 或 MinGW-w64")
        return False

    src = LAUNCHER_DIR / "launcher.c"
    if not src.exists():
        print(f"[错误] 找不到源文件: {src}")
        return False

    if sys.platform == "win32":
        out = LAUNCHER_DIR / "model_fitting.exe"
    else:
        out = LAUNCHER_DIR / "model_fitting"

    # 编译选项
    flags = [
        cc,
        "-O2",
        "-s",  # strip symbols
        "-o", str(out),
        str(src),
        "-lz",
        "-DRESOURCE_H",
        f"-I{LAUNCHER_DIR}",
    ]

    # macOS 需要额外的安全标志来允许 fork (因为程序不在 bundle 里)
    # 实际上普通 CLI 程序不需要这个，但加上没坏处

    print(f"编译: {' '.join(str(f) for f in flags)}")
    result = subprocess.run(
        [str(f) for f in flags],
        cwd=LAUNCHER_DIR,
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"[错误] 编译失败:\n{result.stderr}")
        return False

    # 警告不算失败，但值得显示
    if result.stderr.strip():
        print(f"[警告]\n{result.stderr.strip()}")

    size = os.path.getsize(out)
    print(f"[✓] 编译成功: {out} ({size / 1024:.0f} KB)")

    if sys.platform != "win32":
        os.chmod(out, 0o755)

    return True


def pack():
    """完整打包流程。"""
    print("╔══════════════════════════════╗")
    print("║  模型拟合工具 — C Launcher   ║")
    print("║       打包脚本               ║")
    print("╚══════════════════════════════╝")
    print()

    # 1. 切换到项目根目录
    os.chdir(HERE)

    # 2. 创建 ZIP
    print("── 1. 创建资源包 ──")
    zip_data = create_zip()

    # 3. 生成 resource.h
    print("\n── 2. 生成 resource.h ──")
    resource_h = LAUNCHER_DIR / "resource.h"
    generate_header(zip_data, resource_h)

    # 4. 编译
    print("\n── 3. 编译启动器 ──")
    if not compile_launcher():
        return 1

    print("\n[✓] 打包完成!")
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="模型拟合工具打包脚本")
    parser.add_argument("--zip-only", action="store_true", help="仅生成 resource.h")
    parser.add_argument("--compile", action="store_true", help="仅编译（需要已有 resource.h）")
    args = parser.parse_args()

    if args.compile:
        sys.exit(0 if compile_launcher() else 1)
    elif args.zip_only:
        zip_data = create_zip()
        resource_h = LAUNCHER_DIR / "resource.h"
        generate_header(zip_data, resource_h)
        sys.exit(0)
    else:
        sys.exit(pack())
