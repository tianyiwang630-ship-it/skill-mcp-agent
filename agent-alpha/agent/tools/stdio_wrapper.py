#!/usr/bin/env python3
"""
STDIO Wrapper - 过滤 MCP Server 的非 JSON-RPC 输出

用途：某些 MCP server（如 open-websearch）将调试日志输出到 stdout，
违反 MCP 协议（stdout 只能有 JSON-RPC 消息）。
本包装器过滤非 JSON-RPC 输出，将其重定向到 stderr。

关键设计：全程使用二进制模式，避免 Windows 文本模式的 CRLF 转换问题。
"""

import sys
import subprocess
import json
import threading
import os
import shutil


def is_json_rpc(line_bytes):
    """检查字节数据是否是 JSON-RPC 消息"""
    try:
        text = line_bytes.decode('utf-8').strip()
        if not text:
            return False
        obj = json.loads(text)
        return isinstance(obj, dict) and (
            'jsonrpc' in obj or 'id' in obj or 'method' in obj or 'result' in obj
        )
    except Exception:
        return False


def filter_stdout(process):
    """过滤 stdout，只转发 JSON-RPC 消息（二进制模式）"""
    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
            if is_json_rpc(line):
                # JSON-RPC 消息 → 转发到 stdout
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
            else:
                # 调试日志 → 重定向到 stderr
                try:
                    text = line.decode('utf-8', errors='replace').rstrip('\r\n')
                    if text.strip():
                        sys.stderr.write(f"[MCP Debug] {text}\n")
                        sys.stderr.flush()
                except Exception:
                    pass
    except Exception as e:
        sys.stderr.write(f"[Wrapper] stdout filter error: {e}\n")
        sys.stderr.flush()


def forward_stderr(process):
    """转发 stderr"""
    try:
        while True:
            line = process.stderr.readline()
            if not line:
                break
            try:
                text = line.decode('utf-8', errors='replace')
                sys.stderr.write(text)
                sys.stderr.flush()
            except Exception:
                pass
    except Exception:
        pass


def forward_stdin(process):
    """转发 stdin（二进制模式，字节级转发）"""
    try:
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                break
            process.stdin.write(line)
            process.stdin.flush()
    except Exception as e:
        sys.stderr.write(f"[Wrapper] stdin forward error: {e}\n")
        sys.stderr.flush()


def resolve_command(args):
    """
    解析命令路径（与 MCP SDK 一致的方式）

    在 Windows 上使用 shutil.which() 找到完整路径，
    支持 .cmd / .bat / .exe 扩展名自动解析。
    """
    command = args[0]

    if os.name == 'nt':
        # 先尝试原始命令
        resolved = shutil.which(command)
        if resolved:
            return [resolved] + args[1:]

        # 尝试常见扩展名
        for ext in ['.cmd', '.bat', '.exe']:
            resolved = shutil.which(command + ext)
            if resolved:
                return [resolved] + args[1:]

    return args


def main():
    """主函数"""
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: stdio_wrapper.py <command> [args...]\n")
        sys.exit(1)

    command = resolve_command(sys.argv[1:])

    sys.stderr.write(f"[Wrapper] Starting: {' '.join(command)}\n")
    sys.stderr.flush()

    # 二进制模式，无缓冲
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    # 启动转发线程
    threads = [
        threading.Thread(target=filter_stdout, args=(process,), daemon=True),
        threading.Thread(target=forward_stderr, args=(process,), daemon=True),
        threading.Thread(target=forward_stdin, args=(process,), daemon=True),
    ]
    for t in threads:
        t.start()

    # 等待子进程结束
    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()

    sys.exit(process.returncode)


if __name__ == "__main__":
    main()
