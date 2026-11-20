//! Writing the project's repository files for the person who chose this computer to do it (w2): the server hands
//! the resident program a write delivery (`{"kind": "write", "op": "save"|"delete"|"rename", "repo", "branch",
//! "path", "to"?, "content_b64"?, "base", "message"}`) and waits for the answer this module makes
//! (`{"result": "done"|"conflict"|"failed", "commit"?, "sha"?, "current"?, "detail"?}`).
//!
//! How: with the `git` on PATH and nothing else, from a **partial bare clone of the program's own** per repository,
//! `<ASTERISM_HOME>/repos/<owner>__<name>.git` (`git clone --bare --filter=blob:none`: the history's trees, and
//! only the blobs this program writes). It never touches a working copy of the person's. For each write:
//! fetch the branch into `refs/remotes/origin/<branch>`; compare `base` with the blob of `path` there (another
//! one, or none: `conflict` with the blob there now); build the new tree in a temporary index from that commit
//! (`read-tree`, `update-index --index-info`, `write-tree`); `commit-tree` on that commit (author and committer from
//! the person's git configuration on this computer); `push` the commit to the branch, never forced. A push refused
//! because the branch moved is a `conflict`, after a fresh fetch says what the file is now.
//!
//! Credentials: git's own (its credential helper, SSH). This program never asks for, keeps or logs a password or a
//! token, and git is told never to prompt (the resident program has no terminal): a push that needs a login git
//! cannot find is `failed`, with git's own short reason. Writes are done one at a time.
//!
//! For tests only: `ASTERISM_GIT_REMOTE` names a local repository that stands in for every repository address.

use serde_json::{json, Value};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

/// A write is done within this; the server waits 60 seconds for its answer.
const BUDGET: Duration = Duration::from_secs(50);
/// Whether git is here is looked at again after this long (the sessions report says it).
const LOOK_AGAIN: Duration = Duration::from_secs(300);
const DETAIL_MOST: usize = 200;
const ZERO: &str = "0000000000000000000000000000000000000000";

static ONE_AT_A_TIME: Mutex<()> = Mutex::new(());
static HAVE_GIT: Mutex<Option<(Instant, bool)>> = Mutex::new(None);

fn lock<T>(m: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    m.lock().unwrap_or_else(|e| e.into_inner())
}

/// Whether `git` runs here (for the sessions report: `"git": true|false`).
pub fn available() -> bool {
    let mut known = lock(&HAVE_GIT);
    if let Some((at, have)) = *known {
        if at.elapsed() < LOOK_AGAIN {
            return have;
        }
    }
    let have = run(None, &["--version"], None, None, Instant::now() + Duration::from_secs(10)).is_ok_and(|o| o.ok);
    *known = Some((Instant::now(), have));
    have
}

// ----------------------------------------------------------------------------- running git

struct Out {
    ok: bool,
    stdout: String,
    stderr: String,
}

/// One git command, in `git_dir` when given, with the temporary `index` when given and `input` on its stdin. Err:
/// git could not be started, or did not end before `deadline` (it is stopped then).
fn run(git_dir: Option<&Path>, args: &[&str], index: Option<&Path>, input: Option<&[u8]>, deadline: Instant) -> Result<Out, String> {
    let mut cmd = Command::new("git");
    if let Some(dir) = git_dir {
        cmd.arg("--git-dir").arg(dir);
    }
    cmd.args(args);
    for v in ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE"] {
        cmd.env_remove(v);
    }
    // Never a prompt: the resident program has no terminal and nobody would answer it.
    cmd.env("GIT_TERMINAL_PROMPT", "0").env("GCM_INTERACTIVE", "never").env("SSH_ASKPASS_REQUIRE", "never");
    cmd.env("LC_ALL", "C").env("LANGUAGE", "C");
    if let Some(i) = index {
        cmd.env("GIT_INDEX_FILE", i);
    }
    cmd.stdin(if input.is_some() { Stdio::piped() } else { Stdio::null() }).stdout(Stdio::piped()).stderr(Stdio::piped());
    crate::sys::no_window(&mut cmd);
    let mut child = cmd.spawn().map_err(|e| format!("git cannot be started ({e}); is git installed and on PATH?"))?;
    if let (Some(data), Some(mut stdin)) = (input, child.stdin.take()) {
        let data = data.to_vec();
        std::thread::spawn(move || {
            let _ = stdin.write_all(&data);
        });
    }
    let mut so = child.stdout.take();
    let mut se = child.stderr.take();
    let out_t = std::thread::spawn(move || {
        let mut b = Vec::new();
        if let Some(s) = so.as_mut() {
            let _ = s.read_to_end(&mut b);
        }
        b
    });
    let err_t = std::thread::spawn(move || {
        let mut b = Vec::new();
        if let Some(s) = se.as_mut() {
            let _ = s.read_to_end(&mut b);
        }
        b
    });
    let status = loop {
        match child.try_wait() {
            Ok(Some(s)) => break s,
            Ok(None) if Instant::now() >= deadline => {
                let _ = child.kill();
                let _ = child.wait();
                return Err("git did not finish in time".into());
            }
            Ok(None) => std::thread::sleep(Duration::from_millis(20)),
            Err(e) => return Err(format!("git: {e}")),
        }
    };
    let stdout = String::from_utf8_lossy(&out_t.join().unwrap_or_default()).into_owned();
    let stderr = String::from_utf8_lossy(&err_t.join().unwrap_or_default()).into_owned();
    Ok(Out { ok: status.success(), stdout, stderr })
}

/// git's own reason, short, in one line, without anything that looks like a login in an address.
fn reason(o: &Out) -> String {
    let text = if o.stderr.trim().is_empty() { &o.stdout } else { &o.stderr };
    let line = text
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty() && !l.starts_with("hint:"))
        .filter(|l| !l.starts_with("warning: filtering not recognized"))
        .last()
        .unwrap_or("git failed")
        .to_string();
    tidy(&line)
}

fn tidy(line: &str) -> String {
    // "scheme://user:secret@host" -> "scheme://host"
    let mut out = String::new();
    let mut rest = line;
    while let Some(i) = rest.find("://") {
        out.push_str(&rest[..i + 3]);
        rest = &rest[i + 3..];
        let end = rest.find(|c: char| c.is_whitespace() || c == '/' || c == '\'' || c == '"').unwrap_or(rest.len());
        if let Some(at) = rest[..end].rfind('@') {
            rest = &rest[at + 1..];
        }
    }
    out.push_str(rest);
    let clean: String = out.chars().filter(|c| !c.is_control()).collect();
    clean.chars().take(DETAIL_MOST).collect()
}

// ----------------------------------------------------------------------------- what a delivery asks

struct Ask {
    op: String,
    repo: String,
    owner: String,
    name: String,
    branch: Option<String>,
    path: String,
    to: Option<String>,
    data: Option<Vec<u8>>,
    base: Option<String>,
    message: String,
}

fn failed(detail: &str) -> Value {
    json!({"result": "failed", "detail": tidy(detail)})
}

fn conflict(current: Option<&str>) -> Value {
    json!({"result": "conflict", "current": current})
}

/// A path of the repository as the server's rules have it: names joined by '/', none empty, '.', '..' or `.git`,
/// no backslash, no control character.
fn good_path(p: &str) -> bool {
    !p.is_empty()
        && p.len() <= 4096
        && !p.chars().any(|c| c == '\\' || c.is_control())
        && p.split('/').all(|s| !s.is_empty() && s != "." && s != ".." && !s.eq_ignore_ascii_case(".git"))
}

fn good_name(s: &str) -> bool {
    !s.is_empty() && s.len() <= 100 && s != "." && s != ".." && s.chars().all(|c| c.is_ascii_alphanumeric() || "._-".contains(c))
}

/// A branch name git takes as one (and never as an option).
fn good_branch(b: &str) -> bool {
    !b.is_empty()
        && b.len() <= 255
        && !b.starts_with('-')
        && !b.starts_with('/')
        && !b.ends_with('/')
        && !b.ends_with(".lock")
        && !b.contains("..")
        && !b.contains("@{")
        && !b.chars().any(|c| c.is_control() || c.is_whitespace() || "~^:?*[\\".contains(c))
}

fn parse(d: &Value) -> Result<Ask, String> {
    let s = |k: &str| d[k].as_str().map(String::from);
    let op = s("op").filter(|o| ["save", "delete", "rename"].contains(&o.as_str())).ok_or("an unknown kind of write")?;
    let repo = s("repo").ok_or("no repository")?;
    let rest = repo.strip_prefix("https://github.com/").ok_or("not a GitHub repository address")?;
    let mut parts = rest.trim_end_matches('/').split('/');
    let (owner, name) = match (parts.next(), parts.next(), parts.next()) {
        (Some(o), Some(n), None) => (o.to_string(), n.trim_end_matches(".git").to_string()),
        _ => return Err("not a GitHub repository address".into()),
    };
    if !good_name(&owner) || !good_name(&name) {
        return Err("not a GitHub repository address".into());
    }
    let branch = s("branch");
    if branch.as_deref().is_some_and(|b| !good_branch(b)) {
        return Err("not a branch name".into());
    }
    let path = s("path").filter(|p| good_path(p)).ok_or("not a path of the repository")?;
    let to = s("to");
    if op == "rename" && !to.as_deref().is_some_and(|t| good_path(t) && t != path) {
        return Err("not a path to rename to".into());
    }
    let data = match s("content_b64") {
        Some(b) => Some(base64(&b).ok_or("the content is not base64")?),
        None if op == "save" => return Err("no content".into()),
        None => None,
    };
    let base = s("base");
    if op != "save" && base.is_none() {
        return Err("no base".into());
    }
    let message = s("message").filter(|m| !m.trim().is_empty() && m.len() <= 1000).ok_or("no commit message")?;
    Ok(Ask { op, repo, owner, name, branch, path, to, data, base, message })
}

fn base64(text: &str) -> Option<Vec<u8>> {
    let mut out = Vec::with_capacity(text.len() * 3 / 4);
    let (mut acc, mut bits) = (0u32, 0u32);
    for c in text.bytes() {
        let v = match c {
            b'A'..=b'Z' => c - b'A',
            b'a'..=b'z' => c - b'a' + 26,
            b'0'..=b'9' => c - b'0' + 52,
            b'+' => 62,
            b'/' => 63,
            b'=' => break,
            b'\r' | b'\n' => continue,
            _ => return None,
        };
        acc = (acc << 6) | u32::from(v);
        bits += 6;
        if bits >= 8 {
            bits -= 8;
            out.push((acc >> bits) as u8);
            acc &= (1 << bits) - 1;
        }
    }
    Some(out)
}

/// Where the clone fetches from and pushes to: the repository's address, or (tests) ASTERISM_GIT_REMOTE.
fn remote_url(repo: &str) -> String {
    match std::env::var("ASTERISM_GIT_REMOTE").ok().filter(|v| !v.is_empty()) {
        Some(r) if r.contains("://") => r,
        Some(r) => {
            // A local path as a file:// address: a partial clone of a plain path would ignore the filter.
            let abs = std::path::absolute(&r).map(|p| p.to_string_lossy().replace('\\', "/")).unwrap_or(r);
            if abs.starts_with('/') { format!("file://{abs}") } else { format!("file:///{abs}") }
        }
        None => repo.to_string(),
    }
}

// ----------------------------------------------------------------------------- the write

/// Do one write delivery; the answer for `POST /api/computer/write` (without the delivery id).
pub fn write(home: &Path, d: &Value) -> Value {
    let ask = match parse(d) {
        Ok(a) => a,
        Err(e) => return failed(&format!("this program cannot do this write: {e}")),
    };
    let _one = lock(&ONE_AT_A_TIME);
    let deadline = Instant::now() + BUDGET;
    match Writer::new(home, &ask, deadline).and_then(|w| w.go(&ask)) {
        Ok(v) => v,
        Err(e) => failed(&e),
    }
}

struct Writer {
    dir: PathBuf,
    deadline: Instant,
}

/// One entry of a tree: (mode, type, hash).
type Entry = (String, String, String);

impl Writer {
    fn new(home: &Path, ask: &Ask, deadline: Instant) -> Result<Writer, String> {
        let repos = home.join("repos");
        crate::state::ensure_dir(&repos).map_err(|e| format!("cannot create {} ({e})", repos.display()))?;
        let dir = repos.join(format!("{}__{}.git", ask.owner, ask.name));
        let url = remote_url(&ask.repo);
        if !dir.join("HEAD").is_file() {
            let tmp = repos.join(format!("{}__{}.git.part-{}", ask.owner, ask.name, std::process::id()));
            let _ = std::fs::remove_dir_all(&tmp);
            let tmp_s = tmp.to_string_lossy().into_owned();
            let o = run(None, &["clone", "--bare", "--filter=blob:none", "--no-tags", "--quiet", "--", &url, &tmp_s], None, None, deadline)?;
            if !o.ok {
                let _ = std::fs::remove_dir_all(&tmp);
                return Err(format!("cannot clone the repository: {}", reason(&o)));
            }
            std::fs::rename(&tmp, &dir).map_err(|e| {
                let _ = std::fs::remove_dir_all(&tmp);
                format!("cannot keep the clone ({e})")
            })?;
        }
        let w = Writer { dir, deadline };
        let now = w.git(&["config", "--get", "remote.origin.url"], None, None)?;
        if now.stdout.trim() != url {
            w.must(&["remote", "set-url", "origin", &url], None, None, "cannot set the repository's address")?;
        }
        Ok(w)
    }

    fn git(&self, args: &[&str], index: Option<&Path>, input: Option<&[u8]>) -> Result<Out, String> {
        run(Some(&self.dir), args, index, input, self.deadline)
    }

    /// A git command that must succeed; its standard output, trimmed.
    fn must(&self, args: &[&str], index: Option<&Path>, input: Option<&[u8]>, what: &str) -> Result<String, String> {
        let o = self.git(args, index, input)?;
        if !o.ok {
            return Err(format!("{what}: {}", reason(&o)));
        }
        Ok(o.stdout.trim().to_string())
    }

    /// The branch to write: the one the server named, else the repository's default branch.
    fn branch(&self, ask: &Ask) -> Result<String, String> {
        if let Some(b) = &ask.branch {
            return Ok(b.clone());
        }
        let out = self.must(&["ls-remote", "--symref", "origin", "HEAD"], None, None, "cannot read the repository")?;
        out.lines()
            .find_map(|l| l.strip_prefix("ref: refs/heads/").and_then(|r| r.split('\t').next()).map(String::from))
            .filter(|b| good_branch(b))
            .ok_or_else(|| "the repository has no default branch".to_string())
    }

    /// Fetch the branch; the commit at its tip.
    fn fetch(&self, branch: &str) -> Result<String, String> {
        let spec = format!("+refs/heads/{branch}:refs/remotes/origin/{branch}");
        self.must(&["fetch", "--no-tags", "--quiet", "origin", &spec], None, None, "cannot fetch the branch")?;
        self.must(&["rev-parse", "--verify", "--quiet", &format!("refs/remotes/origin/{branch}^{{commit}}")], None, None, "the branch is not there")
    }

    /// The entry at `path` in `commit`, or None.
    fn entry(&self, commit: &str, path: &str) -> Result<Option<Entry>, String> {
        let o = self.must_raw(&["ls-tree", "-z", "--full-tree", commit, "--", path])?;
        for rec in o.split('\0') {
            let Some((head, name)) = rec.split_once('\t') else { continue };
            if name != path {
                continue;
            }
            let mut f = head.split(' ');
            if let (Some(m), Some(t), Some(h)) = (f.next(), f.next(), f.next()) {
                return Ok(Some((m.to_string(), t.to_string(), h.to_string())));
            }
        }
        Ok(None)
    }

    fn must_raw(&self, args: &[&str]) -> Result<String, String> {
        let o = self.git(args, None, None)?;
        if !o.ok {
            return Err(format!("cannot read the repository: {}", reason(&o)));
        }
        Ok(o.stdout)
    }

    /// The blob at `path` in `commit` (None: no file there).
    fn blob(&self, commit: &str, path: &str) -> Result<Option<String>, String> {
        Ok(self.entry(commit, path)?.filter(|e| e.1 == "blob").map(|e| e.2))
    }

    fn go(&self, ask: &Ask) -> Result<Value, String> {
        let branch = self.branch(ask)?;
        let tip = self.fetch(&branch)?;
        let now = self.entry(&tip, &ask.path)?;
        let current = now.as_ref().filter(|e| e.1 == "blob").map(|e| e.2.clone());
        // The file must be what the person started from (a new file: nothing there).
        if current.as_deref() != ask.base.as_deref() || (ask.base.is_none() && now.is_some()) {
            return Ok(conflict(current.as_deref()));
        }
        // The index lines (update-index --index-info -z): mode SP hash TAB path NUL; mode 0 takes a path out.
        let (lines, sha) = match ask.op.as_str() {
            "save" => {
                let data = ask.data.as_deref().unwrap_or_default();
                let blob = self.must(&["hash-object", "-w", "--no-filters", "--stdin"], None, Some(data), "cannot store the file")?;
                let mode = now.as_ref().map(|e| e.0.clone()).unwrap_or_else(|| "100644".into());
                (format!("{mode} {blob}\t{}\0", ask.path), Some(blob))
            }
            "delete" => (format!("0 {ZERO}\t{}\0", ask.path), None),
            _ => {
                let to = ask.to.as_deref().unwrap_or_default();
                if self.entry(&tip, to)?.is_some() {
                    return Ok(conflict(current.as_deref())); // something is at the new name already
                }
                let (mode, _, blob) = now.clone().unwrap_or_default();
                (format!("{mode} {blob}\t{to}\0" ) + &format!("0 {ZERO}\t{}\0", ask.path), Some(blob))
            }
        };
        let index = self.dir.join(format!("asterism-{}.index", crate::sys::random_hex(8)?));
        let built = self.build(&tip, &lines, &index, &ask.message);
        let _ = std::fs::remove_file(&index);
        let commit = built?;
        let target = format!("{commit}:refs/heads/{branch}");
        let o = self.git(&["push", "--porcelain", "origin", &target], None, None)?;
        if o.ok {
            let mut answer = json!({"result": "done", "commit": commit});
            if let Some(s) = sha {
                answer["sha"] = json!(s);
            }
            return Ok(answer);
        }
        // Refused because the branch moved (not a fast-forward): what the file is now, after a fresh fetch.
        let rejected = o.stdout.lines().any(|l| l.starts_with('!') && l.contains("[rejected]"));
        if rejected {
            let tip = self.fetch(&branch)?;
            return Ok(conflict(self.blob(&tip, &ask.path)?.as_deref()));
        }
        let why = o
            .stdout
            .lines()
            .find(|l| l.starts_with('!'))
            .and_then(|l| l.split('\t').nth(2))
            .map(String::from)
            .unwrap_or_else(|| reason(&o));
        Err(format!("the push was refused: {}", tidy(&why)))
    }

    /// The new commit: the tree of `tip` with `lines` applied, in a temporary index, committed on `tip`.
    fn build(&self, tip: &str, lines: &str, index: &Path, message: &str) -> Result<String, String> {
        self.must(&["read-tree", tip], Some(index), None, "cannot read the branch's tree")?;
        self.must(&["update-index", "-z", "--index-info"], Some(index), Some(lines.as_bytes()), "cannot change the tree")?;
        // The blobs of the files not written are not here (a partial clone): git is told not to look for them.
        let tree = self.must(&["write-tree", "--missing-ok"], Some(index), None, "cannot write the tree")?;
        let o = self.git(&["commit-tree", &tree, "-p", tip, "-F", "-"], None, Some(message.as_bytes()))?;
        if !o.ok {
            let r = reason(&o);
            if o.stderr.contains("tell me who you are") || o.stderr.contains("empty ident") || o.stderr.contains("user.email") {
                return Err("git on this computer has no user.name and user.email to commit with (git config --global user.name ..., user.email ...)".into());
            }
            return Err(format!("cannot commit: {r}"));
        }
        Ok(o.stdout.trim().to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn base64_decodes() {
        assert_eq!(base64("aGVsbG8=").unwrap(), b"hello");
        assert_eq!(base64("IyBQbGFuCgpzdGVwIHR3bwo=").unwrap(), b"# Plan\n\nstep two\n");
        assert!(base64("a$b").is_none());
    }

    #[test]
    fn paths_and_branches_follow_the_rules() {
        assert!(good_path("notes/plan.md") && !good_path("../x") && !good_path(".git/x") && !good_path("a\\b") && !good_path("a//b"));
        assert!(good_branch("main") && good_branch("feature/x") && !good_branch("-x") && !good_branch("a..b") && !good_branch("a b"));
    }

    #[test]
    fn a_login_in_an_address_is_not_repeated() {
        assert_eq!(tidy("fatal: unable to access 'https://bob:ghp_x@github.com/o/r/'"), "fatal: unable to access 'https://github.com/o/r/'");
    }
}
