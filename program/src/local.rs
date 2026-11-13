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
use std::process::{Command, Stdio};
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
    let mut s = connect(info, Duration::from_secs(10))?;
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
    let info = state::read_daemon(home)?;
    let hello = request(&info, json!({"op": "hello"})).ok()?;
    (hello["pid"].as_u64() == Some(u64::from(info.pid))).then_some(info)
}

/// The resident program, started if it does not answer. Two starters racing each start one; the second
/// exits at once (it cannot take `daemon.lock`), and both find the winner in `daemon.json`.
pub fn ensure_daemon(home: &Path) -> Result<DaemonInfo, String> {
    if let Some(info) = running(home) {
        return Ok(info);
    }
    state::ensure_dir(home).map_err(|e| format!("cannot create {} ({e})", home.display()))?;
    let exe = std::env::current_exe().map_err(|e| format!("cannot find this program's own file ({e})"))?;
    let mut cmd = Command::new(exe);
    cmd.arg("daemon")
        .env("ASTERISM_HOME", home)
        // Not the starter's folder: a running program keeps its folder from being removed on Windows.
        .current_dir(home)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    crate::sys::spawn_detached(&mut cmd).map_err(|e| format!("cannot start the resident program ({e})"))?;
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
    s.set_read_timeout(None).map_err(|e| e.to_string())?;
    let mut sink = [0u8; 256];
    loop {
        match r.read(&mut sink) {
            Ok(0) | Err(_) => return Ok(()),
            Ok(_) => {}
        }
    }
}
