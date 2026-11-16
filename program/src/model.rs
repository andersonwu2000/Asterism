//! Which model the agent of this session runs on, read from the agent's own session record on this computer
//! (best effort, never required):
//!
//! - Claude Code: `<CLAUDE_CONFIG_DIR or ~/.claude>/projects/*/<session id>.jsonl`; the model is `message.model`
//!   of the last line whose `type` is `"assistant"` and which is not a side chain.
//! - Codex: `<CODEX_HOME or ~/.codex>/sessions/**/rollout-*-<thread id>.jsonl`; the model is `payload.model` of
//!   the last line whose `type` is `"turn_context"`.
//!
//! Only the end of the one file is read (at most `TAIL` bytes), from the end backwards until such a line is
//! found, and only that one field is taken: nothing else of these files is kept, sent or logged. Any failure
//! (no file, unreadable, a format that changed, a value that is not a plain model name) means the model is
//! unknown, and nothing is said.

use serde_json::Value;
use std::fs;
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{Duration, Instant};

const TAIL: u64 = 256 * 1024;
// Codex keeps its rollouts in sessions/YYYY/MM/DD.
const CODEX_DEPTH: usize = 4;
// A record not found is looked for again after this long, not at every call.
const MISS_KEPT: Duration = Duration::from_secs(30);

#[derive(Clone, Copy, PartialEq)]
pub enum Product {
    ClaudeCode,
    Codex,
}

/// Where the record of a session was found, or when it was last looked for in vain.
#[derive(Default)]
pub struct Finder {
    found: Mutex<Option<(String, PathBuf)>>,
    missed: Mutex<Option<(String, Instant)>>,
}

impl Finder {
    /// The model the session `id` of `product` runs on now, if its record says it.
    pub fn model(&self, product: Product, id: &str) -> Option<String> {
        if !is_uuid(id) {
            return None; // ids are UUIDs; anything else is never put into a file name
        }
        let key = format!("{}:{id}", product as u8);
        let known = lock(&self.found).as_ref().filter(|(k, _)| *k == key).map(|(_, p)| p.clone());
        if let Some(path) = known {
            if let Some(tail) = tail(&path) {
                return last_model(product, &tail);
            }
            *lock(&self.found) = None; // the file went away: look for it again
        }
        if lock(&self.missed).as_ref().is_some_and(|(k, at)| *k == key && at.elapsed() < MISS_KEPT) {
            return None;
        }
        let Some(path) = find(product, id) else {
            *lock(&self.missed) = Some((key, Instant::now()));
            return None;
        };
        *lock(&self.found) = Some((key, path.clone()));
        last_model(product, &tail(&path)?)
    }
}

fn lock<T>(m: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    m.lock().unwrap_or_else(|e| e.into_inner())
}

/// 8-4-4-4-12 hexadecimal digits.
pub fn is_uuid(s: &str) -> bool {
    let b = s.as_bytes();
    b.len() == 36
        && b.iter().enumerate().all(|(i, c)| if matches!(i, 8 | 13 | 18 | 23) { *c == b'-' } else { c.is_ascii_hexdigit() })
}

/// What the server accepts: 1 to 64 of `[A-Za-z0-9._:/-]`.
pub fn valid_model(s: &str) -> bool {
    !s.is_empty() && s.len() <= 64 && s.bytes().all(|c| c.is_ascii_alphanumeric() || b"._:/-".contains(&c))
}

fn user_dir(var: &str, default: &str) -> Option<PathBuf> {
    if let Some(d) = std::env::var_os(var).filter(|v| !v.is_empty()) {
        return Some(PathBuf::from(d));
    }
    let base = if cfg!(windows) { std::env::var_os("USERPROFILE") } else { std::env::var_os("HOME") };
    base.filter(|v| !v.is_empty()).map(|b| PathBuf::from(b).join(default))
}

pub fn find(product: Product, id: &str) -> Option<PathBuf> {
    match product {
        Product::ClaudeCode => {
            let name = format!("{id}.jsonl");
            fs::read_dir(user_dir("CLAUDE_CONFIG_DIR", ".claude")?.join("projects"))
                .ok()?
                .flatten()
                .map(|e| e.path().join(&name))
                .find(|p| p.is_file())
        }
        Product::Codex => {
            let ending = format!("-{id}.jsonl");
            rollout(&user_dir("CODEX_HOME", ".codex")?.join("sessions"), &ending, CODEX_DEPTH)
        }
    }
}

/// The newest folders first: a thread that calls a tool is usually a recent one.
fn rollout(dir: &Path, ending: &str, depth: usize) -> Option<PathBuf> {
    let mut entries: Vec<_> = fs::read_dir(dir).ok()?.flatten().collect();
    entries.sort_by_key(|e| std::cmp::Reverse(e.file_name()));
    for e in entries {
        let Ok(kind) = e.file_type() else { continue };
        let name = e.file_name();
        let name = name.to_string_lossy();
        if kind.is_file() && name.starts_with("rollout-") && name.ends_with(ending) {
            return Some(e.path());
        }
        if kind.is_dir() && depth > 1 {
            if let Some(p) = rollout(&e.path(), ending, depth - 1) {
                return Some(p);
            }
        }
    }
    None
}

/// The last `TAIL` bytes of the file, from the start of a line.
pub fn tail(path: &Path) -> Option<Vec<u8>> {
    let mut f = fs::File::open(path).ok()?;
    let len = f.metadata().ok()?.len();
    let start = len.saturating_sub(TAIL);
    f.seek(SeekFrom::Start(start)).ok()?;
    let mut buf = Vec::new();
    f.take(TAIL).read_to_end(&mut buf).ok()?;
    if start > 0 {
        // The first line is cut: it begins after the first line break.
        let cut = buf.iter().position(|c| *c == b'\n')? + 1;
        buf.drain(..cut);
    }
    Some(buf)
}

/// The model of the last line that names one, read from the end backwards.
fn last_model(product: Product, tail: &[u8]) -> Option<String> {
    let (kind, marker) = match product {
        Product::ClaudeCode => ("assistant", &b"\"assistant\""[..]),
        Product::Codex => ("turn_context", &b"\"turn_context\""[..]),
    };
    for line in tail.split(|c| *c == b'\n').rev() {
        // Only lines that may be of the kind are parsed.
        if !line.windows(marker.len()).any(|w| w == marker) {
            continue;
        }
        let Ok(v) = serde_json::from_slice::<Value>(line) else { continue };
        if v["type"] != kind {
            continue;
        }
        let model = match product {
            Product::ClaudeCode => {
                if v["isSidechain"] == Value::Bool(true) {
                    continue;
                }
                &v["message"]["model"]
            }
            Product::Codex => &v["payload"]["model"],
        };
        return model.as_str().filter(|m| valid_model(m)).map(String::from);
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_last_main_chain_answer_names_the_model() {
        let rec = concat!(
            r#"{"type":"assistant","message":{"model":"claude-a"}}"#, "\n",
            r#"{"type":"assistant","isSidechain":true,"message":{"model":"claude-side"}}"#, "\n",
            r#"{"type":"user","message":{"content":"assistant","model":"opus"}}"#, "\r\n",
            "not json \"assistant\"\n"
        );
        assert_eq!(last_model(Product::ClaudeCode, rec.as_bytes()).as_deref(), Some("claude-a"));
        let codex = concat!(r#"{"type":"turn_context","payload":{"model":"gpt-x"}}"#, "\n", r#"{"type":"event_msg"}"#);
        assert_eq!(last_model(Product::Codex, codex.as_bytes()).as_deref(), Some("gpt-x"));
    }

    #[test]
    fn a_value_that_is_not_a_model_name_is_unknown() {
        let rec = r#"{"type":"assistant","message":{"model":"<synthetic>"}}"#;
        assert_eq!(last_model(Product::ClaudeCode, rec.as_bytes()), None);
        assert!(!valid_model(&"x".repeat(65)) && !valid_model("") && valid_model("claude-opus-5-5"));
        assert!(is_uuid("019a0000-0000-7000-8000-00000000c0de") && !is_uuid("s-cc-1") && !is_uuid("../../x"));
    }
}
