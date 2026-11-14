"""A stand-in for a resident program of another version, for the tests of the real one.

    python standin_resident.py <state folder> <version>

It does what a resident program of version 0.1.0 did as far as another copy of the program can see: it holds
`daemon.lock`, writes `daemon.json` (port, token, pid, version) and answers `hello` on 127.0.0.1. It knows no
other op (0.1.0 had no `stop`), and it wakes nobody.
"""
import json
import os
import socket
import sys

home, version = sys.argv[1], sys.argv[2]
os.makedirs(home, exist_ok=True)

lock = open(os.path.join(home, "daemon.lock"), "a+")
if sys.platform == "win32":
    import msvcrt
    lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
else:
    import fcntl
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

s = socket.socket()
s.bind(("127.0.0.1", 0))
s.listen(16)
token = "standin-" + os.urandom(12).hex()
with open(os.path.join(home, "daemon.json"), "w", encoding="utf-8") as f:
    json.dump({"port": s.getsockname()[1], "token": token, "pid": os.getpid(), "version": version}, f)
print("ready", flush=True)

while True:
    c, _ = s.accept()
    try:
        c.settimeout(5)
        line = c.makefile("r", encoding="utf-8").readline()
        req = json.loads(line)
        if req.get("token") != token:
            continue                                    # a wrong token: closed with no answer
        if req.get("op") == "hello":
            answer = {"ok": True, "pid": os.getpid(), "version": version}
        else:
            answer = {"ok": False, "error": "unknown op"}
        c.sendall((json.dumps(answer) + chr(10)).encode("utf-8"))
    except (OSError, ValueError):
        pass
    finally:
        c.close()
