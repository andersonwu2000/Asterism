//! Putting a message in front of a local agent, and starting the products' commands. Carried over from the
//! Python helper, whose behaviour was verified against the real products:
//!
//! - Claude Code: one auth line (when the session has a token) and one user line, JSON, written to the
//!   session's message channel: a named pipe on Windows, a Unix socket elsewhere.
//! - Codex: `codex queue --thread <thread> --message <frame>`, never through a shell. On Windows npm installs
//!   `codex` as a `.cmd` shim that only cmd.exe runs, and cmd.exe would cut a message at its first line break
//!   and act on what a hostile message smuggles in; so `codex.js` behind the shim is started with node directly.
//!   A message is at most 4,000 characters, so its frame always fits on a command line.

use std::io::{Read, Write};
use std::path::PathBuf;
use std::process::{Command, ExitStatus, Stdio};
use std::sync::mpsc;
use std::time::{Duration, Instant};

#[cfg(windows)]
const WIN_PROGRAMS: [&str; 2] = [".exe", ".com"]; // what Windows starts directly
#[cfg(windows)]
const WIN_SHELL: [&str; 2] = [".cmd", ".bat"]; // what only cmd.exe starts

/// How to start the command `name` from this process's PATH: (the file, whether it needs cmd.exe).
///
/// On Windows it never returns a file Windows cannot start: npm installs a command as three files side by
/// side (`codex`, a shell script without an extension; `codex.cmd`; `codex.ps1`). In each folder of PATH the
/// startable forms are looked for, programs first. The current folder is not searched.
pub fn command(name: &str) -> Option<(PathBuf, bool)> {
    let path = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path) {
        if dir.as_os_str().is_empty() {
            continue;
        }
        #[cfg(windows)]
        {
            for ext in WIN_PROGRAMS.iter().chain(WIN_SHELL.iter()) {
                let c = dir.join(format!("{name}{ext}"));
                if c.is_file() {
                    return Some((c, WIN_SHELL.contains(ext)));
                }
            }
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let c = dir.join(name);
            if c.metadata().is_ok_and(|m| m.is_file() && m.permissions().mode() & 0o111 != 0) {
                return Some((c, false));
            }
        }
    }
    None
}

/// How to start `codex` without a shell, or None if that cannot be done here.
///
/// The npm shim only starts node_modules/@openai/codex/bin/codex.js beside it, with the node.exe beside it or
/// else `node` from PATH; we start that program the same way, directly. Elsewhere `codex` is a program.
pub fn codex_argv() -> Option<Vec<String>> {
    let (found, shell) = command("codex")?;
    if !shell {
        return Some(vec![found.to_string_lossy().into_owned()]);
    }
    let here = found.parent()?;
    let script = here.join("node_modules").join("@openai").join("codex").join("bin").join("codex.js");
    let beside = here.join("node.exe");
    let node = if beside.is_file() {
        beside
    } else {
        match command("node") {
            Some((n, false)) => n,
            _ => return None,
        }
    };
    if !script.is_file() {
        return None;
    }
    Some(vec![node.to_string_lossy().into_owned(), script.to_string_lossy().into_owned()])
}

/// JSON as Python's json.dumps writes it by default: everything outside ASCII as \u escapes. The channel
/// was verified with exactly these bytes.
fn ascii_json(v: &serde_json::Value) -> String {
    let mut out = String::new();
    for ch in v.to_string().chars() {
        if ch.is_ascii() {
            out.push(ch);
        } else {
            let mut units = [0u16; 2];
            for u in ch.encode_utf16(&mut units) {
                out.push_str(&format!("\\u{u:04x}"));
            }
        }
    }
    out
}

/// Write a user turn holding `text` to a Claude Code session's message channel.
pub fn push_claude(socket: &str, token: Option<&str>, text: &str) -> Result<(), String> {
    let mut lines = Vec::new();
    if let Some(t) = token.filter(|t| !t.is_empty()) {
        lines.push(ascii_json(&serde_json::json!({"type": "auth", "token": t})));
    }
    lines.push(ascii_json(&serde_json::json!({"type": "user", "message": {"role": "user", "content": text}})));
    let payload = (lines.join("\n") + "\n").into_bytes();
    write_channel(socket, &payload)
}

#[cfg(windows)]
fn write_channel(path: &str, payload: &[u8]) -> Result<(), String> {
    const ERROR_PIPE_BUSY: i32 = 231;
    let end = Instant::now() + Duration::from_secs(5);
    loop {
        match std::fs::OpenOptions::new().read(true).write(true).open(path) {
            Ok(mut pipe) => {
                // One write, so that a pipe in message mode gets the whole payload as one message.
                return pipe.write_all(payload).map_err(|e| e.to_string());
            }
            // Every instance of the pipe is serving another writer for a moment.
            Err(e) if e.raw_os_error() == Some(ERROR_PIPE_BUSY) && Instant::now() < end => {
                std::thread::sleep(Duration::from_millis(50));
            }
            Err(e) => return Err(e.to_string()),
        }
    }
}

#[cfg(unix)]
fn write_channel(path: &str, payload: &[u8]) -> Result<(), String> {
    let mut s = std::os::unix::net::UnixStream::connect(path).map_err(|e| e.to_string())?;
    s.set_write_timeout(Some(Duration::from_secs(10))).map_err(|e| e.to_string())?;
    s.write_all(payload).map_err(|e| e.to_string())
}

/// Queue `text` on a Codex thread (an idle thread starts a turn), whole, as one argument, without a shell.
pub fn push_codex(argv: &[String], thread: &str, text: &str) -> Result<(), String> {
    if !crate::state::valid_thread(thread) || argv.is_empty() {
        return Err("not a Codex thread id".into());
    }
    let mut cmd = Command::new(&argv[0]);
    cmd.args(&argv[1..]).args(["queue", "--thread", thread, "--message", text]);
    match run(&mut cmd, Duration::from_secs(60)) {
        Ok((st, _, _)) if st.success() => Ok(()),
        Ok((st, _, _)) => Err(format!("codex queue exited with {}", st.code().map_or("a signal".into(), |c| c.to_string()))),
        Err(e) => Err(format!("codex queue could not run ({e})")),
    }
}

/// Run a command to its end with nothing on stdin; (status, stdout, stderr). Killed after `timeout`.
pub fn run(cmd: &mut Command, timeout: Duration) -> Result<(ExitStatus, String, String), String> {
    cmd.stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
    crate::sys::no_window(cmd);
    let mut child = cmd.spawn().map_err(|e| e.to_string())?;
    // Read both pipes on their own threads: a child filling one pipe while we wait would never end.
    let collect = |r: Option<Box<dyn Read + Send>>| {
        let (tx, rx) = mpsc::channel();
        std::thread::spawn(move || {
            let mut buf = Vec::new();
            if let Some(mut r) = r {
                let _ = r.read_to_end(&mut buf);
            }
            let _ = tx.send(String::from_utf8_lossy(&buf).into_owned());
        });
        rx
    };
    let out = collect(child.stdout.take().map(|p| Box::new(p) as Box<dyn Read + Send>));
    let err = collect(child.stderr.take().map(|p| Box::new(p) as Box<dyn Read + Send>));
    let end = Instant::now() + timeout;
    let status = loop {
        match child.try_wait() {
            Ok(Some(st)) => break st,
            Ok(None) if Instant::now() < end => std::thread::sleep(Duration::from_millis(25)),
            Ok(None) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(format!("no end after {} s", timeout.as_secs()));
            }
            Err(e) => return Err(e.to_string()),
        }
    };
    // A grandchild may still hold the pipes open (cmd.exe starting node); do not wait for it for long.
    let take = |rx: mpsc::Receiver<String>| rx.recv_timeout(Duration::from_secs(5)).unwrap_or_default();
    Ok((status, take(out), take(err)))
}

/// A command line for a person to copy, quoted where a shell needs it.
pub fn shown(args: &[String]) -> String {
    args.iter()
        .map(|a| {
            if !a.is_empty() && !a.chars().any(|c| c.is_whitespace() || "\"'&|<>^%!$`;()".contains(c)) {
                a.clone()
            } else {
                format!("\"{}\"", a.replace('"', "\\\""))
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

#[cfg(test)]
mod tests {
    #[test]
    fn json_is_ascii_like_python() {
        let s = super::ascii_json(&serde_json::json!({"t": "數 \u{1F600}"}));
        let esc = |hex: &str| format!("{}u{hex}", char::from(92));
        assert_eq!(s, format!("{{\"t\":\"{} {}{}\"}}", esc("6578"), esc("d83d"), esc("de00")));
    }
}
