"""Bounded subprocess I/O without a shell; kill the whole process group on timeout."""
import os
import selectors
import signal
import subprocess
import time
from .core import Rejected


def run(argv, *, cwd=None, data=None, timeout=120, limit=64_000, env=None):
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    # Inputs are bounded by the caller and smaller than the pipe capacity on supported hosts.
    if data is not None:
        proc.stdin.write(data.encode())
        proc.stdin.close()
    output = {proc.stdout: bytearray(), proc.stderr: bytearray()}
    selector = selectors.DefaultSelector()
    for stream in output:
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ)
    end = time.monotonic() + timeout
    try:
        while selector.get_map():
            if time.monotonic() >= end:
                raise Rejected("operation timed out; outcome may be partial")
            for key, _ in selector.select(min(0.1, max(0, end - time.monotonic()))):
                chunk = os.read(key.fileobj.fileno(), 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                else:
                    output[key.fileobj].extend(chunk)
                    if sum(map(len, output.values())) > limit:
                        raise Rejected("operation output limit exceeded")
        code = proc.wait(timeout=max(0.01, end-time.monotonic()))
        return code, output[proc.stdout].decode(errors="replace"), output[proc.stderr].decode(errors="replace")
    finally:
        selector.close()
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        for stream in output:
            stream.close()
