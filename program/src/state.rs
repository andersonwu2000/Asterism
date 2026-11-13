//! The state folder (`ASTERISM_HOME`, default `~/.asterism`). Everything the program remembers is a file
//! here, so that a restarted resident program, a new `mcp` and `join` all start from the same facts:
//!
//! - `projects/<key>.json`: `{project, person, credential, created}`, one per joined project. The same file
//!   the Python helper writes, so a computer authorised with the helper needs no new approval. Secret.
//! - `daemon.json`: `{port, token, pid, version}` of the running resident program. Secret (the token).
//! - `daemon.lock`: held by the resident program while it runs; one per folder.
//! - `threads.json`: `{thread: {argv, since}}`, the Codex threads the resident program can wake, with the
//!   way to start `codex` that the thread's own session found (the resident program's PATH may differ).
//! - `pending.json`: `{session: {project, name, product, created}}`, "this conversation registers as NAME
//!   in this project", left by `join` for the `mcp` of that conversation.
//! - `state.lock`: taken while `threads.json` or `pending.json` is read and rewritten, by any process.
//! - `daemon.log`: what the resident program did (never a secret or a message text).
//!
//! On Unix, secret files are created mode 0600 and the folder 0700. On Windows the folder is in the user's
//! profile, whose default permissions already keep other ordinary users out; nothing is changed there.

use serde_json::{json, Map, Value};
use std::collections::BTreeMap;
use std::fs::{self, OpenOptions};
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

pub fn home() -> PathBuf {
    let h = match std::env::var_os("ASTERISM_HOME").filter(|v| !v.is_empty()) {
        Some(h) => PathBuf::from(h),
        None => {
            let base = if cfg!(windows) { std::env::var_os("USERPROFILE") } else { std::env::var_os("HOME") };
            base.filter(|v| !v.is_empty()).map(PathBuf::from).unwrap_or_else(|| PathBuf::from(".")).join(".asterism")
        }
    };
    // Absolute, because the resident program is started inside this folder and is told it again.
    std::path::absolute(&h).unwrap_or(h)
}

pub fn ensure_dir(dir: &Path) -> io::Result<()> {
    fs::create_dir_all(dir)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(dir, fs::Permissions::from_mode(0o700));
    }
    Ok(())
}

static TMP_SEQ: AtomicU64 = AtomicU64::new(0);

/// Write the whole file at once (a reader sees the old or the new content, never a part), readable by
/// this user only where the system has such modes.
pub fn write_private(path: &Path, data: &[u8]) -> io::Result<()> {
    if let Some(dir) = path.parent() {
        ensure_dir(dir)?;
    }
    let name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
    let tmp = path.with_file_name(format!(
        "{name}.{}.{}.part",
        std::process::id(),
        TMP_SEQ.fetch_add(1, Ordering::Relaxed)
    ));
    {
        let mut opts = OpenOptions::new();
        opts.write(true).create(true).truncate(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            opts.mode(0o600);
        }
        let mut f = opts.open(&tmp)?;
        f.write_all(data)?;
        let _ = f.sync_all();
    }
    // On Windows a reader holding the target open for a moment makes the replace fail; try again briefly.
    let mut last = None;
    for _ in 0..20 {
        match fs::rename(&tmp, path) {
            Ok(()) => return Ok(()),
            Err(e) => last = Some(e),
        }
        std::thread::sleep(Duration::from_millis(25));
    }
    let _ = fs::remove_file(&tmp);
    Err(last.unwrap_or_else(|| io::Error::other("rename failed")))
}

pub fn read_json(path: &Path) -> Option<Value> {
    serde_json::from_slice(&fs::read(path).ok()?).ok()
}

// --------------------------------------------------------------------------- projects (credentials)

#[derive(Clone, Debug, PartialEq)]
pub struct Project {
    pub key: String,
    pub url: String,
    pub slug: String,
    pub person: String,
    pub credential: String,
}

/// The file name of a project, as the Python helper computes it: host, port and path of its address with
/// everything but letters, digits, dots and dashes turned into underscores.
pub fn project_key(url: &str) -> String {
    let rest = url.split_once("://").map(|(_, r)| r).unwrap_or(url);
    let rest = rest.split(['?', '#']).next().unwrap_or("");
    let mapped: String =
        rest.chars().map(|c| if c.is_ascii_alphanumeric() || c == '.' || c == '-' { c } else { '_' }).collect();
    mapped.trim_matches('_').to_string()
}

pub fn slug_of(url: &str) -> String {
    url.trim_end_matches('/').rsplit('/').next().unwrap_or("").to_string()
}

fn projects_dir(home: &Path) -> PathBuf {
    home.join("projects")
}

pub fn load_projects(home: &Path) -> Vec<Project> {
    let mut out = Vec::new();
    let Ok(dir) = fs::read_dir(projects_dir(home)) else { return out };
    for entry in dir.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let Some(v) = read_json(&path) else { continue };
        let (Some(url), Some(cred)) = (v["project"].as_str(), v["credential"].as_str()) else { continue };
        let url = url.trim_end_matches('/').to_string();
        if !(url.starts_with("http://") || url.starts_with("https://")) || cred.is_empty() {
            continue;
        }
        out.push(Project {
            key: path.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default(),
            slug: slug_of(&url),
            person: v["person"].as_str().unwrap_or("").to_string(),
            credential: cred.to_string(),
            url,
        });
    }
    out.sort_by(|a, b| a.key.cmp(&b.key));
    out
}

pub fn load_project(home: &Path, url: &str) -> Option<Project> {
    let key = project_key(url);
    load_projects(home).into_iter().find(|p| p.key == key)
}

pub fn save_credential(home: &Path, url: &str, person: &str, credential: &str) -> io::Result<()> {
    let data = json!({"project": url, "person": person, "credential": credential, "created": crate::sys::utc_iso()});
    let text = serde_json::to_string_pretty(&data).unwrap_or_default();
    write_private(&projects_dir(home).join(format!("{}.json", project_key(url))), text.as_bytes())
}

// --------------------------------------------------------------------------- daemon.json

#[derive(Clone, Debug)]
pub struct DaemonInfo {
    pub port: u16,
    pub token: String,
    pub pid: u32,
}

pub fn read_daemon(home: &Path) -> Option<DaemonInfo> {
    let v = read_json(&home.join("daemon.json"))?;
    Some(DaemonInfo {
        port: u16::try_from(v["port"].as_u64()?).ok()?,
        token: v["token"].as_str()?.to_string(),
        pid: u32::try_from(v["pid"].as_u64()?).ok()?,
    })
}

pub fn write_daemon(home: &Path, port: u16, token: &str) -> io::Result<()> {
    let data = json!({"port": port, "token": token, "pid": std::process::id(), "version": crate::VERSION});
    write_private(&home.join("daemon.json"), data.to_string().as_bytes())
}

// --------------------------------------------------------------------------- threads.json and pending.json

/// Run `f` while holding `state.lock`, so that read-modify-write of the small state files by `join`,
/// several `mcp` and the resident program never lose each other's changes.
fn locked<T>(home: &Path, f: impl FnOnce() -> T) -> io::Result<T> {
    ensure_dir(home)?;
    let lock = OpenOptions::new().create(true).truncate(false).write(true).open(home.join("state.lock"))?;
    lock.lock()?;
    let out = f();
    let _ = lock.unlock();
    Ok(out)
}

fn read_map(path: &Path) -> Map<String, Value> {
    match read_json(path) {
        Some(Value::Object(m)) => m,
        _ => Map::new(),
    }
}

fn write_map(path: &Path, m: &Map<String, Value>) -> io::Result<()> {
    write_private(path, serde_json::to_string_pretty(m).unwrap_or_default().as_bytes())
}

/// What a Codex thread id may look like before it goes on a command line (as the helper checks it).
pub fn valid_thread(t: &str) -> bool {
    let b = t.as_bytes();
    !b.is_empty()
        && b.len() <= 128
        && b[0].is_ascii_alphanumeric()
        && b.iter().all(|c| c.is_ascii_alphanumeric() || *c == b'_' || *c == b'-')
}

/// What the server accepts as a session id: 1 to 200 printable ASCII characters, no spaces.
pub fn valid_session(s: &str) -> bool {
    !s.is_empty() && s.len() <= 200 && s.bytes().all(|c| (0x21..=0x7e).contains(&c))
}

pub fn load_threads(home: &Path) -> BTreeMap<String, Vec<String>> {
    let mut out = BTreeMap::new();
    for (thread, v) in read_map(&home.join("threads.json")) {
        let argv: Vec<String> =
            v["argv"].as_array().map(|a| a.iter().filter_map(|x| x.as_str().map(String::from)).collect()).unwrap_or_default();
        if valid_thread(&thread) && !argv.is_empty() {
            out.insert(thread, argv);
        }
    }
    out
}

/// Remember (Some) or forget (None) a Codex thread as wakeable. True when the file changed.
pub fn set_thread(home: &Path, thread: &str, argv: Option<&[String]>) -> io::Result<bool> {
    let path = home.join("threads.json");
    locked(home, || {
        let mut m = read_map(&path);
        let changed = match argv {
            Some(argv) => {
                let same = m.get(thread).and_then(|v| v["argv"].as_array()).is_some_and(|a| {
                    a.len() == argv.len() && a.iter().zip(argv).all(|(x, y)| x.as_str() == Some(y.as_str()))
                });
                if !same {
                    m.insert(thread.into(), json!({"argv": argv, "since": crate::sys::utc_iso()}));
                }
                !same
            }
            None => m.remove(thread).is_some(),
        };
        if changed {
            write_map(&path, &m)?;
        }
        Ok(changed)
    })?
}

#[derive(Clone, Debug)]
pub struct Pending {
    pub project: String,
    pub name: String,
}

/// A note left by `join` is kept this long; a conversation that never comes back must not register
/// months later.
const PENDING_TTL_S: u64 = 7 * 86400;

pub fn note_pending(home: &Path, session: &str, project_key: &str, name: &str, product: &str) -> io::Result<()> {
    let path = home.join("pending.json");
    let now = crate::sys::epoch_s();
    locked(home, || {
        let mut m = read_map(&path);
        m.retain(|_, v| v["created"].as_u64().is_some_and(|t| t + PENDING_TTL_S > now));
        m.insert(session.into(), json!({"project": project_key, "name": name, "product": product, "created": now}));
        write_map(&path, &m)
    })?
}

pub fn pending(home: &Path, session: &str) -> Option<Pending> {
    let v = read_map(&home.join("pending.json")).remove(session)?;
    if v["created"].as_u64().is_none_or(|t| t + PENDING_TTL_S <= crate::sys::epoch_s()) {
        return None;
    }
    Some(Pending { project: v["project"].as_str()?.to_string(), name: v["name"].as_str()?.to_string() })
}

pub fn forget_pending(home: &Path, session: &str) -> io::Result<()> {
    let path = home.join("pending.json");
    locked(home, || {
        let mut m = read_map(&path);
        if m.remove(session).is_some() {
            write_map(&path, &m)?;
        }
        Ok(())
    })?
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keys_match_the_python_helper() {
        assert_eq!(project_key("http://127.0.0.1:5123/lab"), "127.0.0.1_5123_lab");
        assert_eq!(project_key("https://asterismhub.com/my-lab"), "asterismhub.com_my-lab");
        assert_eq!(slug_of("https://asterismhub.com/my-lab"), "my-lab");
    }

    #[test]
    fn thread_ids() {
        assert!(valid_thread("019a-ff_x"));
        assert!(!valid_thread("-x"));
        assert!(!valid_thread("a b"));
        assert!(!valid_thread(""));
    }
}
