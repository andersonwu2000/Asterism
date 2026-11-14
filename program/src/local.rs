//! The private protocol between `join` / `mcp` / `status` and the resident program.
//!
//! TCP on 127.0.0.1, at the port in `daemon.json`. A client connects and sends one line: a JSON object with
//! `token` (from `daemon.json`, which only this user can read) and `op`. The resident program answers one
//! line, `{"ok": true, ...}` or `{"ok": false, "error": "..."}`; a wrong token closes the connection with
//! no answer. The ops:
//!
//! - `hello` -> `{ok, pid, version}`: is it running, and is it the one of this state folder.
//! - `reload` -> `{ok}`: read `projects/` and `threads.json` again (a credential or a Codex thread changed).
//! - `status` -> `{ok, pid, version, projects: [{slug, url, person, state}], sessions: [{session, product,
//!   agent}]}`.
//! - `agent` `{session, agent}` -> `{ok}`: which agent a session is now (`agent` null: none); for `status`.
//! - `claude` `{session, socket, socket_token}` -> `{ok}`, and the connection stays open: this Claude Code
//!   session can be woken through that message channel for as long as the connection lives. The client
//!   sends nothing more; its end (the session's `mcp` exits) ends the session's wakeability.
//!
//! Codex threads need no connection: they are in `threads.json`, because a thread stays wakeable when its
//! `mcp` process ends (Codex restarts it as it likes).

use crate::state::{self, DaemonInfo};
use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::Path;
use std::time::{Duration, Instant};

pub const MAX_LINE: u64 = 64 * 1024;

fn connect(info: &DaemonInfo, timeout: Duration) -> Result<TcpStream, String> {
    let addr = SocketAddr::from(([127, 0, 0, 1], info.port));
    let s = TcpStream::connect_timeout(&addr, Duration::from_secs(2)).map_err(|e| e.to_string())?;
    s.set_read_timeout(Some(timeout)).map_err(|e| e.to_string())?;
    s.set_write_timeout(Some(Duration::from_secs(5))).map_err(|e| e.to_string())?;
    Ok(s)
}

pub fn read_line(r: &mut impl BufRead) -> Result<Option<Value>, String> {
    let mut line = String::new();
    let n = r.take(MAX_LINE).read_line(&mut line).map_err(|e| e.to_string())?;
    if n == 0 {
        return Ok(None);
    }
    serde_json::from_str(line.trim()).map(Some).map_err(|e| e.to_string())
}

fn send(s: &mut TcpStream, info: &DaemonInfo, mut req: Value) -> Result<(), String> {
    req["token"] = Value::String(info.token.clone());
    s.write_all((req.to_string() + "\n").as_bytes()).map_err(|e| e.to_string())
}

/// One request and its answer.
pub fn request(info: &DaemonInfo, req: Value) -> Result<Value, String> {
    request_within(info, req, Duration::from_secs(10))
}

fn request_within(info: &DaemonInfo, req: Value, timeout: Duration) -> Result<Value, String> {
    let mut s = connect(info, timeout)?;
    send(&mut s, info, req)?;
    let got = read_line(&mut BufReader::new(s))?.ok_or("the resident program closed the connection")?;
    if got["ok"] == json!(true) {
        Ok(got)
    } else {
        Err(got["error"].as_str().unwrap_or("refused").to_string())
    }
}

/// The resident program of this state folder, if it runs and answers.
pub fn running(home: &Path) -> Option<DaemonInfo> {
    hello(home).map(|(info, _)| info)
}

/// The resident program of this state folder and the version its `hello` gave (None: it gave none), if it
/// runs and answers. Answering with the token of `daemon.json` and the pid written there makes it this state
/// folder's resident program and nothing else.
fn hello(home: &Path) -> Option<(DaemonInfo, Option<String>)> {
    let info = state::read_daemon(home)?;
    let hello = request(&info, json!({"op": "hello"})).ok()?;
    let version = hello["version"].as_str().map(String::from);
    (hello["pid"].as_u64() == Some(u64::from(info.pid))).then_some((info, version))
}

/// The dotted numbers of a version ("0.1.10" -> [0, 1, 10]); None for anything else.
fn parse_version(v: &str) -> Option<Vec<u64>> {
    v.split('.')
        .map(|p| if !p.is_empty() && p.bytes().all(|b| b.is_ascii_digit()) { p.parse::<u64>().ok() } else { None })
        .collect()
}

/// Whether a resident program of version `theirs` is older than `ours`: compared number by number (0.1.10
/// is newer than 0.1.9); a missing or unreadable version counts as older. When our own version cannot be
/// read, nothing counts as older: two programs must never replace each other back and forth.
pub fn older(theirs: Option<&str>, ours: &str) -> bool {
    let Some(mut ours) = parse_version(ours) else { return false };
    let Some(mut theirs) = theirs.and_then(parse_version) else { return true };
    let n = ours.len().max(theirs.len());
    ours.resize(n, 0);
    theirs.resize(n, 0);
    theirs < ours
}

/// End the resident program `info` names: ask it to `stop` (programs before 0.1.2 do not know the
/// request), and end its process when it is still there a few seconds later. Returns once the process is
/// gone, so that `daemon.lock` is free again; Err (the reason) when it could not be ended.
///
/// `info` must come from `running` or `hello`: the pid of `daemon.json`, confirmed by a `hello` answered with
/// that file's token, is this state folder's resident program and nothing else.
pub fn stop_resident(info: &DaemonInfo) -> Result<(), String> {
    use crate::sys::Process;
    // Held from before the request on: on Windows the handle keeps the pid from naming another process later.
    let process = Process::open(info.pid);
    let _ = request_within(info, json!({"op": "stop"}), Duration::from_secs(3));
    let gone_within = |p: &Process, secs: u64| {
        let end = Instant::now() + Duration::from_secs(secs);
        while p.alive() {
            if Instant::now() >= end {
                return false;
            }
            std::thread::sleep(Duration::from_millis(100));
        }
        true
    };
    match process {
        Ok(None) => Ok(()),
        Ok(Some(p)) => {
            if gone_within(&p, 3) {
                return Ok(());
            }
            let mut said = p.end(false).err();
            if gone_within(&p, 3) {
                return Ok(());
            }
            if cfg!(unix) {
                said = p.end(true).err().or(said);
                if gone_within(&p, 3) {
                    return Ok(());
                }
            }
            Err(said.map_or("did not go away when it was ended".into(),|e| format!("could not be ended ({e})")))
        }
        // Not ours to end (more privileged, or another user's): it may still have stopped on request.
        Err(e) => {
            let end = Instant::now() + Duration::from_secs(5);
            while Instant::now() < end {
                if matches!(Process::open(info.pid), Ok(None)) {
                    return Ok(());
                }
                std::thread::sleep(Duration::from_millis(100));
            }
            Err(format!("could not be ended ({e})"))
        }
    }
}

/// The resident program, started if it does not answer. Two starters racing each start one; the second
/// exits at once (it cannot take `daemon.lock`), and both find the winner in `daemon.json`.
///
/// A resident program older than this one is ended and this one's started in its place (an update put a
/// new program in place while the old one ran). One of the same or a newer version is left alone: the `mcp`
/// of a session opened before an update must not bring the old version back.
pub fn ensure_daemon(home: &Path) -> Result<DaemonInfo, String> {
    let mut replacing = false;
    if let Some((info, version)) = hello(home) {
        if !older(version.as_deref(), crate::VERSION) {
            return Ok(info);
        }
        let theirs = version.as_deref().unwrap_or("unknown");
        let (pid, ours) = (info.pid, crate::VERSION);
        if let Err(e) = stop_resident(&info) {
            crate::daemon::log_in(home, &format!("could not replace the resident program of version {theirs} (process {pid}) with version {ours}: it {e}"));
            return Err(format!(
                "an older resident program (version {theirs}, process {pid}) is running and {e}; end process {pid} yourself (in the Task Manager on Windows, with `kill {pid}` elsewhere), then the next agent session or `asterism join` starts version {ours}"
            ));
        }
        crate::daemon::log_in(home, &format!("replaced the resident program of version {theirs} (process {pid}) with version {ours}"));
        replacing = true;
    }
    state::ensure_dir(home).map_err(|e| format!("cannot create {} ({e})", home.display()))?;
    let exe = std::env::current_exe().map_err(|e| format!("cannot find this program's own file ({e})"))?;
    let mut env = vec![("ASTERISM_HOME", home.as_os_str())];
    if replacing {
        // As after a self-update: the sessions of the old one reconnect before the new one reports its list.
        env.push(("ASTERISM_REPLACING", std::ffi::OsStr::new("1")));
    }
    // In the state folder, not the starter's: a running program keeps its folder from being removed on Windows.
    crate::sys::spawn_detached(&exe, &["daemon"], &env, home).map_err(|e| format!("cannot start the resident program ({e})"))?;
    let end = Instant::now() + Duration::from_secs(15);
    while Instant::now() < end {
        std::thread::sleep(Duration::from_millis(100));
        if let Some(info) = running(home) {
            return Ok(info);
        }
    }
    Err(format!("the resident program did not answer after it was started; see {}", home.join("daemon.log").display()))
}

/// Ask the resident program to read the state files again. Best effort: a program started later reads them
/// anyway.
pub fn reload(home: &Path) {
    if let Some(info) = running(home) {
        let _ = request(&info, json!({"op": "reload"}));
    }
}

pub fn tell_agent(home: &Path, session: &str, agent: Option<&str>) {
    if let Some(info) = state::read_daemon(home) {
        let _ = request(&info, json!({"op": "agent", "session": session, "agent": agent}));
    }
}

/// Hold the connection that makes a Claude Code session wakeable; returns when it ends (the resident
/// program went away), so that the caller can start it again and come back.
pub fn hold_claude(info: &DaemonInfo, session: &str, socket: &str, socket_token: Option<&str>) -> Result<(), String> {
    let mut s = connect(info, Duration::from_secs(10))?;
    send(&mut s, info, json!({"op": "claude", "session": session, "socket": socket, "socket_token": socket_token}))?;
    let mut r = BufReader::new(s.try_clone().map_err(|e| e.to_string())?);
    let got = read_line(&mut r)?.ok_or("the resident program closed the connection")?;
    if got["ok"] != json!(true) {
        return Err(got["error"].as_str().unwrap_or("refused").to_string());
    }
    // The clone in `r` is a socket handle of its own with the timeout `connect` gave it; it is the one read.
    let _ = s.set_read_timeout(None);
    wait_for_close(&mut r);
    Ok(())
}

/// Block until the other end closes the connection. A quiet connection is not a closed one: a read that
/// times out (if a timeout is still set somewhere) or is interrupted just reads again; only the end of the
/// stream or a real error ends the wait.
pub fn wait_for_close(r: &mut BufReader<TcpStream>) {
    let _ = r.get_ref().set_read_timeout(None);
    let mut sink = [0u8; 256];
    loop {
        match r.read(&mut sink) {
            Ok(0) => return,
            Ok(_) => {}
            Err(e) if matches!(e.kind(), std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut | std::io::ErrorKind::Interrupted) => {}
            Err(_) => return,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::older;

    #[test]
    fn versions_compare_number_by_number() {
        assert!(older(Some("0.1.9"), "0.1.10"));
        assert!(!older(Some("0.1.10"), "0.1.9"));
        assert!(older(Some("0.1.0"), "0.1.2"));
        assert!(older(Some("0.9.99"), "1.0.0"));
        assert!(!older(Some("0.2.0"), "0.1.99"));
        assert!(!older(Some("0.1"), "0.1.0"), "missing numbers count as zeros");
        assert!(older(Some("0.1"), "0.1.1"));
    }

    #[test]
    fn equal_versions_are_not_older() {
        assert!(!older(Some("0.1.2"), "0.1.2"));
        assert!(!older(Some("10.20.30"), "10.20.30"));
    }

    #[test]
    fn a_missing_or_unreadable_version_counts_as_older() {
        for theirs in [None, Some(""), Some("garbage"), Some("0.1.x"), Some("0..1"), Some("+1.0.0"), Some("0.1.2-beta"), Some(" 0.1.2")] {
            assert!(older(theirs, "0.1.2"), "{theirs:?}");
        }
    }

    #[test]
    fn an_unreadable_own_version_replaces_nothing() {
        assert!(!older(None, "garbage"));
        assert!(!older(Some("0.0.1"), ""));
    }
}
