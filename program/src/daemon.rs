//! The resident program (`asterism daemon`): one per state folder, started by `join` or by any `mcp` that
//! finds it missing, and left running.
//!
//! For every joined project it holds this computer's connection to the server: it reports the local
//! sessions it can wake right now (`POST /api/computer/sessions`, the complete list, again whenever it
//! changes), keeps a poll open (`GET /api/computer/poll`), puts each delivery in front of its session and
//! acknowledges (`POST /api/computer/ack`) only what was put there. Each project has two threads: the
//! reporter (sends the list when it changes) and the poller (polls, delivers, acknowledges), so that a new
//! session is reported while a poll is held.
//!
//! What it can wake: a Claude Code session while that session's `mcp` holds a connection to us (the
//! message channel and its token come from that connection, because only the session's environment has
//! them); a Codex thread from `threads.json` (written by `join` and `mcp` with the way to start `codex`
//! that the thread's own session found), until its agent leaves or a `codex queue` for it fails.
//!
//! Nothing may stop it: the server away (retry with a growing pause), a revoked credential (that project
//! stops, the others go on), a vanished channel (that delivery is not acknowledged; the server's rules
//! follow), a bug in one thread (the thread is started again).

use crate::http::{self, Fail};
use crate::local;
use crate::push;
use crate::state::{self, Project};
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap};
use std::fs::{self, OpenOptions};
use std::io::{BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::panic::{self, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Condvar, Mutex, MutexGuard, OnceLock};
use std::time::Duration;

const POLL_S: u64 = 25; // one held poll; short enough for any proxy in between
const RELOAD_EVERY: Duration = Duration::from_secs(30);
const LOG_MAX: u64 = 1024 * 1024;

static LOG_PATH: OnceLock<PathBuf> = OnceLock::new();

/// A line in `daemon.log`. Never a secret, never a message text.
fn log(line: &str) {
    if let Some(path) = LOG_PATH.get() {
        append_log(path, line);
    }
}

/// A line in the `daemon.log` of `home`, from a program that is not the resident program (`join`, `mcp`).
pub fn log_in(home: &Path, line: &str) {
    append_log(&home.join("daemon.log"), line);
}

fn append_log(path: &Path, line: &str) {
    if fs::metadata(path).is_ok_and(|m| m.len() > LOG_MAX) {
        let _ = fs::rename(path, path.with_extension("log.1"));
    }
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(f, "{} [{}] {line}", crate::sys::utc_iso(), std::process::id());
    }
}

pub fn log_panic(line: &str) {
    log(line);
}

fn lock<T>(m: &Mutex<T>) -> MutexGuard<'_, T> {
    // A thread that panicked while holding the lock is restarted; the data it guards stays usable.
    m.lock().unwrap_or_else(|e| e.into_inner())
}

struct Claude {
    socket: String,
    token: Option<String>,
    conn: u64,
}

#[derive(Default)]
struct Wakeable {
    gen: u64, // raised on every change of what can be woken
    claude: HashMap<String, Claude>,
    codex: BTreeMap<String, Vec<String>>,
    agents: HashMap<String, String>, // session -> agent, for `status` only
    next_conn: u64,
}

struct Proj {
    p: Project,
    stop: AtomicBool,
    force_report: AtomicBool,
    reported: AtomicU64, // the generation last reported; u64::MAX before the first report
    state: Mutex<String>,
}

impl Proj {
    fn stopped(&self) -> bool {
        self.stop.load(Ordering::SeqCst)
    }
    fn set_state(&self, s: &str) {
        let mut st = lock(&self.state);
        if *st != s {
            log(&format!("{}: {s}", self.p.slug));
            *st = s.to_string();
        }
    }
}

struct Daemon {
    home: PathBuf,
    token: String,
    agent: http::Agent,
    w: Mutex<Wakeable>,
    cv: Condvar,
    projects: Mutex<HashMap<String, Arc<Proj>>>,
    report_after: std::time::Instant,
}

pub fn run(home: PathBuf) -> i32 {
    if let Err(e) = state::ensure_dir(&home) {
        eprintln!("Cannot create the state folder {} ({e}).", home.display());
        return 1;
    }
    let _ = LOG_PATH.set(home.join("daemon.log"));
    // One per state folder: the lock is released by the system when this process ends, however it ends.
    match take_lock(&home) {
        Ok(true) => {}
        Ok(false) => return 0, // another one runs
        Err(e) => {
            log(&format!("cannot lock daemon.lock: {e}"));
            return 1;
        }
    }
    // Started by a resident program that is replacing itself: the sessions of the one before reconnect
    // within a second or two; reporting an empty list before that would show their agents offline.
    let grace = if std::env::var_os("ASTERISM_REPLACING").is_some() { Duration::from_secs(5) } else { Duration::ZERO };
    let listener = match TcpListener::bind(("127.0.0.1", 0)) {
        Ok(l) => l,
        Err(e) => {
            log(&format!("cannot listen on 127.0.0.1: {e}"));
            return 1;
        }
    };
    crate::sys::no_inherit(&listener);
    let port = listener.local_addr().map(|a| a.port()).unwrap_or(0);
    let token = match crate::sys::random_hex(32) {
        Ok(t) => t,
        Err(e) => {
            log(&e);
            return 1;
        }
    };
    if let Err(e) = state::write_daemon(&home, port, &token) {
        log(&format!("cannot write daemon.json: {e}"));
        return 1;
    }
    let _ = ME.set((port, token.clone()));
    log(&format!("started, version {}, port {port}", crate::VERSION));
    let d = Arc::new(Daemon {
        home: home.clone(),
        token,
        agent: http::agent(),
        w: Mutex::new(Wakeable::default()),
        cv: Condvar::new(),
        projects: Mutex::new(HashMap::new()),
        report_after: std::time::Instant::now() + grace,
    });
    d.reload();
    crate::update::start(home);
    {
        let d = d.clone();
        supervise("reload", move || loop {
            std::thread::sleep(RELOAD_EVERY);
            d.reload();
        });
    }
    for stream in listener.incoming() {
        let Ok(stream) = stream else { continue };
        crate::sys::no_inherit(&stream);
        let d = d.clone();
        std::thread::spawn(move || {
            let _ = panic::catch_unwind(AssertUnwindSafe(|| d.serve_local(stream)));
        });
    }
    0
}

/// `daemon.lock`, held while this process is the resident program. Kept here (not on the stack of `run`)
/// so that an update can hand it to the new program, and take it back if that one does not come up.
static LOCK: Mutex<Option<fs::File>> = Mutex::new(None);
/// This program's port and token, to write `daemon.json` again after an update that did not happen.
static ME: OnceLock<(u16, String)> = OnceLock::new();

/// Ok(false): another resident program holds the lock.
pub fn take_lock(home: &Path) -> std::io::Result<bool> {
    let f = OpenOptions::new().create(true).truncate(false).write(true).open(home.join("daemon.lock"))?;
    match f.try_lock() {
        Ok(()) => {
            *lock(&LOCK) = Some(f);
            Ok(true)
        }
        Err(fs::TryLockError::WouldBlock) => Ok(false),
        Err(fs::TryLockError::Error(e)) => Err(e),
    }
}

pub fn release_lock() {
    lock(&LOCK).take();
}

pub fn write_daemon_again(home: &Path) {
    if let Some((port, token)) = ME.get() {
        let _ = state::write_daemon(home, *port, token);
    }
}

pub fn log_line(line: &str) {
    log(line);
}

/// Run `body` on its own thread and start it again if it panics (after a pause). A body that returns
/// normally is done.
fn supervise(name: &'static str, body: impl Fn() + Send + 'static) {
    std::thread::spawn(move || loop {
        match panic::catch_unwind(AssertUnwindSafe(&body)) {
            Ok(()) => return,
            Err(_) => {
                log(&format!("{name}: restarted after an internal error"));
                std::thread::sleep(Duration::from_secs(5));
            }
        }
    });
}

/// Sleep, but wake early when the project is stopped.
fn nap(p: &Proj, d: Duration) {
    let mut left = d;
    while !left.is_zero() && !p.stopped() {
        let step = left.min(Duration::from_millis(250));
        std::thread::sleep(step);
        left -= step;
    }
}

struct Backoff(u64);
impl Backoff {
    fn next(&mut self) -> Duration {
        self.0 = (self.0 * 2).clamp(2, 30);
        Duration::from_secs(self.0)
    }
    fn reset(&mut self) {
        self.0 = 1;
    }
}

impl Daemon {
    fn changed(&self, w: &mut Wakeable) {
        w.gen += 1;
        self.cv.notify_all();
    }

    /// Read `projects/` and `threads.json` again; start, keep or stop each project's threads.
    fn reload(self: &Arc<Self>) {
        let threads = state::load_threads(&self.home);
        {
            let mut w = lock(&self.w);
            if w.codex != threads {
                w.codex = threads;
                self.changed(&mut w);
            }
        }
        let files = state::load_projects(&self.home);
        let mut projects = lock(&self.projects);
        projects.retain(|key, old| {
            let keep = files.iter().any(|p| p == &old.p);
            if !keep {
                log(&format!("{}: no longer served ({key})", old.p.slug));
                old.stop.store(true, Ordering::SeqCst);
            }
            keep
        });
        for p in files {
            if projects.contains_key(&p.key) {
                continue;
            }
            let proj = Arc::new(Proj {
                p,
                stop: AtomicBool::new(false),
                force_report: AtomicBool::new(false),
                reported: AtomicU64::new(u64::MAX),
                state: Mutex::new("connecting".into()),
            });
            log(&format!("{}: serving {}", proj.p.slug, proj.p.url));
            projects.insert(proj.p.key.clone(), proj.clone());
            let (d1, p1) = (self.clone(), proj.clone());
            supervise("reporter", move || d1.reporter(&p1));
            let (d2, p2) = (self.clone(), proj);
            supervise("poller", move || d2.poller(&p2));
        }
        self.cv.notify_all();
    }

    fn revoked(&self, p: &Proj) {
        p.set_state("stopped: the server no longer accepts this computer's credential (revoked); join again with a new invitation link");
        p.stop.store(true, Ordering::SeqCst);
        self.cv.notify_all();
    }

    fn call(&self, p: &Proj, method: &str, path: &str, body: Option<&Value>, query: &[(String, String)], t: Duration) -> Result<Value, Fail> {
        let auth = format!("Bearer {}", p.p.credential);
        http::call(&self.agent, method, &format!("{}/api/computer/{path}", p.p.url), body, &[("Authorization", &auth)], query, t)
    }

    /// Send the list of wakeable sessions whenever it changed (or the server may have lost it).
    fn reporter(&self, p: &Proj) {
        let wait = self.report_after.saturating_duration_since(std::time::Instant::now());
        nap(p, wait);
        let mut pause = Backoff(1);
        loop {
            let (gen, sessions) = {
                let mut w = lock(&self.w);
                loop {
                    if p.stopped() {
                        return;
                    }
                    let last = p.reported.load(Ordering::SeqCst);
                    if last != w.gen || p.force_report.swap(false, Ordering::SeqCst) {
                        break;
                    }
                    w = self.cv.wait_timeout(w, Duration::from_secs(30)).map(|r| r.0).unwrap_or_else(|e| e.into_inner().0);
                }
                let mut list: Vec<Value> = w.claude.keys().map(|s| json!({"session": s, "product": "claude-code"})).collect();
                list.extend(
                    w.codex.keys().filter(|t| !w.claude.contains_key(*t)).map(|t| json!({"session": t, "product": "codex"})),
                );
                (w.gen, list)
            };
            let n = sessions.len();
            match self.call(p, "POST", "sessions", Some(&json!({"sessions": sessions})), &[], Duration::from_secs(30)) {
                Ok(_) => {
                    p.reported.store(gen, Ordering::SeqCst);
                    // The server took the list; the poll opens right after, but answers only after up to POLL_S.
                    p.set_state("connected");
                    log(&format!("{}: reported {n} session(s)", p.p.slug));
                    pause.reset();
                    self.cv.notify_all();
                }
                Err(e) if e.is_revoked() => return self.revoked(p),
                Err(Fail::Unreachable(e)) => {
                    p.set_state(&format!("connecting: the server cannot be reached ({e})"));
                    nap(p, pause.next());
                }
                Err(Fail::Refused { message, .. }) => {
                    p.set_state(&format!("refused: {message}"));
                    nap(p, Duration::from_secs(30));
                }
            }
        }
    }

    /// Keep the computer's poll open; deliver and acknowledge what it hands out.
    fn poller(&self, p: &Proj) {
        // The server keeps the last list it was given; polling before ours is in would serve sessions of
        // an earlier run of this program. Except when we replace a running one: its list is the right one
        // until its sessions have reconnected, and a poll left closed that long would show them offline.
        let replacing = self.report_after > std::time::Instant::now();
        if !replacing {
            let mut w = lock(&self.w);
            while p.reported.load(Ordering::SeqCst) == u64::MAX {
                if p.stopped() {
                    return;
                }
                w = self.cv.wait_timeout(w, Duration::from_secs(1)).map(|r| r.0).unwrap_or_else(|e| e.into_inner().0);
            }
        }
        let mut pause = Backoff(1);
        let query = [("timeout".to_string(), POLL_S.to_string())];
        loop {
            if p.stopped() {
                return;
            }
            match self.call(p, "GET", "poll", None, &query, Duration::from_secs(POLL_S + 20)) {
                Ok(got) => {
                    p.set_state("connected");
                    pause.reset();
                    if let Some(ds) = got["deliveries"].as_array().filter(|a| !a.is_empty()) {
                        self.deliver(p, ds);
                    }
                }
                Err(e) if e.is_revoked() => return self.revoked(p),
                Err(Fail::Unreachable(e)) => {
                    p.set_state(&format!("connecting: the server cannot be reached ({e})"));
                    // It may come back as a new process: tell it the sessions again.
                    p.force_report.store(true, Ordering::SeqCst);
                    self.cv.notify_all();
                    nap(p, pause.next());
                }
                Err(Fail::Refused { message, .. }) => {
                    p.set_state(&format!("refused: {message}"));
                    nap(p, Duration::from_secs(30));
                }
            }
        }
    }

    fn deliver(&self, p: &Proj, ds: &[Value]) {
        enum To {
            Claude(String, Option<String>),
            Codex(Vec<String>),
        }
        let mut done = Vec::new();
        for d in ds {
            let (Some(id), Some(frame), Some(session)) = (d["delivery"].as_i64(), d["frame"].as_str(), d["session"].as_str()) else {
                continue;
            };
            if p.stopped() {
                break;
            }
            let to = {
                let mut w = lock(&self.w);
                if let Some(agent) = d["agent"].as_str() {
                    w.agents.insert(session.to_string(), agent.to_string());
                }
                if let Some(c) = w.claude.get(session) {
                    Some(To::Claude(c.socket.clone(), c.token.clone()))
                } else {
                    w.codex.get(session).map(|argv| To::Codex(argv.clone()))
                }
            };
            let result = match &to {
                Some(To::Claude(socket, token)) => push::push_claude(socket, token.as_deref(), frame),
                Some(To::Codex(argv)) => push::push_codex(argv, session, frame),
                None => Err("the session is not known here (any more)".into()),
            };
            match result {
                Ok(()) => {
                    log(&format!("{}: delivery {id} to {session}", p.p.slug));
                    done.push(id);
                }
                Err(e) => {
                    log(&format!("{}: delivery {id} to {session} failed: {e}", p.p.slug));
                    if matches!(to, Some(To::Codex(_))) {
                        self.forget_thread(session);
                    }
                }
            }
        }
        if done.is_empty() {
            return;
        }
        match self.call(p, "POST", "ack", Some(&json!({"deliveries": done})), &[], Duration::from_secs(30)) {
            Ok(_) => {}
            Err(e) if e.is_revoked() => self.revoked(p),
            // The server hands them out again later; delivering twice is better than losing one.
            Err(Fail::Unreachable(e)) => log(&format!("{}: acknowledging failed ({e})", p.p.slug)),
            Err(Fail::Refused { message, .. }) => log(&format!("{}: acknowledging refused ({message})", p.p.slug)),
        }
    }

    /// A Codex thread whose `codex queue` failed can no longer be woken from here.
    fn forget_thread(&self, thread: &str) {
        if let Err(e) = state::set_thread(&self.home, thread, None) {
            log(&format!("cannot update threads.json: {e}"));
        }
        let mut w = lock(&self.w);
        if w.codex.remove(thread).is_some() {
            self.changed(&mut w);
        }
    }

    // ------------------------------------------------------------------- the local protocol (see local.rs)

    fn serve_local(self: &Arc<Self>, stream: TcpStream) {
        let _ = stream.set_read_timeout(Some(Duration::from_secs(10)));
        let Ok(read_half) = stream.try_clone() else { return };
        crate::sys::no_inherit(&read_half);
        let mut r = BufReader::new(read_half);
        let Ok(Some(req)) = local::read_line(&mut r) else { return };
        if !same_secret(req["token"].as_str().unwrap_or(""), &self.token) {
            return;
        }
        let mut out = stream;
        let mut answer = |v: Value| out.write_all((v.to_string() + "\n").as_bytes()).is_ok();
        match req["op"].as_str().unwrap_or("") {
            "hello" => {
                answer(json!({"ok": true, "pid": std::process::id(), "version": crate::VERSION}));
            }
            "reload" => {
                self.reload();
                answer(json!({"ok": true}));
            }
            "stop" => {
                // `asterism uninstall`.
                log("stopped on request");
                answer(json!({"ok": true}));
                std::process::exit(0);
            }
            "status" => {
                answer(self.status());
            }
            "agent" => {
                if let Some(session) = req["session"].as_str() {
                    let mut w = lock(&self.w);
                    match req["agent"].as_str() {
                        Some(a) => w.agents.insert(session.to_string(), a.to_string()),
                        None => w.agents.remove(session),
                    };
                }
                answer(json!({"ok": true}));
            }
            "claude" => {
                let session = req["session"].as_str().unwrap_or("");
                let socket = req["socket"].as_str().unwrap_or("");
                if !state::valid_session(session) || socket.is_empty() {
                    answer(json!({"ok": false, "error": "a session id and a message channel are needed"}));
                    return;
                }
                let conn = {
                    let mut w = lock(&self.w);
                    w.next_conn += 1;
                    let conn = w.next_conn;
                    let token = req["socket_token"].as_str().map(String::from);
                    w.claude.insert(session.to_string(), Claude { socket: socket.to_string(), token, conn });
                    self.changed(&mut w);
                    conn
                };
                log(&format!("claude-code session {session} connected"));
                if answer(json!({"ok": true})) {
                    // Until the session's `mcp` ends: only then is the session gone.
                    local::wait_for_close(&mut r);
                }
                let mut w = lock(&self.w);
                // A restarted `mcp` of the same session may have connected meanwhile; keep that one.
                if w.claude.get(session).is_some_and(|c| c.conn == conn) {
                    w.claude.remove(session);
                    self.changed(&mut w);
                    log(&format!("claude-code session {session} gone"));
                }
            }
            _ => {
                answer(json!({"ok": false, "error": "unknown op"}));
            }
        }
    }

    fn status(&self) -> Value {
        let projects: Vec<Value> = {
            let ps = lock(&self.projects);
            let mut v: Vec<&Arc<Proj>> = ps.values().collect();
            v.sort_by(|a, b| a.p.key.cmp(&b.p.key));
            v.iter()
                .map(|p| json!({"slug": p.p.slug, "url": p.p.url, "person": p.p.person, "state": *lock(&p.state)}))
                .collect()
        };
        let w = lock(&self.w);
        let mut sessions: Vec<Value> =
            w.claude.keys().map(|s| json!({"session": s, "product": "claude-code", "agent": w.agents.get(s)})).collect();
        sessions.extend(
            w.codex
                .keys()
                .filter(|t| !w.claude.contains_key(*t))
                .map(|t| json!({"session": t, "product": "codex", "agent": w.agents.get(t)})),
        );
        json!({"ok": true, "pid": std::process::id(), "version": crate::VERSION, "projects": projects, "sessions": sessions})
    }
}

fn same_secret(a: &str, b: &str) -> bool {
    let (a, b) = (a.as_bytes(), b.as_bytes());
    a.len() == b.len() && a.iter().zip(b).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}
