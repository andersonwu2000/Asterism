//! What the resident program reports with the list of sessions (1x), read from this computer and nothing else:
//!
//! - each session's last activity (`active_at`): the modification time of the session's own record (the files
//!   `model.rs` already finds: Claude Code `projects/*/<session>.jsonl`, the Codex rollout of the thread). Only the
//!   file's time is read, never its content.
//! - the quotas of the products (`quotas`):
//!   - Codex: `rate_limits` of the last event that carries it, at the end of the most recently written rollout of
//!     a reported thread (the same end of the file `model.rs` reads for the model): `primary` / `secondary` with
//!     `used_percent`, `window_minutes` and `resets_at`, and `plan_type`.
//!   - Claude Code: `claude_oauth_usage.json` in the temporary folder, which the user's status line writes
//!     (`five_hour.utilization`, `seven_day.utilization`, `resets_at` where present), only while it is younger than
//!     `USAGE_FRESH`, only when a reported Claude Code session has its record here, and only for the default
//!     configuration (no `CLAUDE_CONFIG_DIR`: another configuration may be another account than the status line's).
//!
//! Nothing else of these files is kept, sent or logged. The program never reads credentials and never calls
//! Anthropic or OpenAI. Any failure means "not known", and nothing is said.

use crate::model::{self, Product};
use serde_json::{json, Map, Value};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

pub const USAGE_FILE: &str = "claude_oauth_usage.json";
const USAGE_FRESH: Duration = Duration::from_secs(15 * 60);
const USAGE_MAX: u64 = 64 * 1024;
// A record not found is looked for again after this long, not at every report.
const MISS_KEPT: Duration = Duration::from_secs(60);

/// Where each session's record was found, or when it was last looked for in vain.
#[derive(Default)]
pub struct Records {
    found: Mutex<HashMap<String, PathBuf>>,
    missed: Mutex<HashMap<String, Instant>>,
}

fn lock<T>(m: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    m.lock().unwrap_or_else(|e| e.into_inner())
}

impl Records {
    /// The record of the session `id` of `product`, if it is on this computer.
    pub fn path(&self, product: Product, id: &str) -> Option<PathBuf> {
        if !model::is_uuid(id) {
            return None; // ids are UUIDs; anything else is never put into a file name
        }
        let key = format!("{}:{id}", product as u8);
        let known = lock(&self.found).get(&key).cloned();
        if let Some(p) = known {
            if p.is_file() {
                return Some(p);
            }
            lock(&self.found).remove(&key);
        }
        if lock(&self.missed).get(&key).is_some_and(|at| at.elapsed() < MISS_KEPT) {
            return None;
        }
        match model::find(product, id) {
            Some(p) => {
                lock(&self.missed).remove(&key);
                lock(&self.found).insert(key, p.clone());
                Some(p)
            }
            None => {
                lock(&self.missed).insert(key, Instant::now());
                None
            }
        }
    }
}

fn unix(t: SystemTime) -> Option<u64> {
    t.duration_since(UNIX_EPOCH).ok().map(|d| d.as_secs())
}

/// When the file was last written, in Unix seconds.
pub fn modified(path: &Path) -> Option<u64> {
    unix(fs::metadata(path).ok()?.modified().ok()?)
}

/// The report's quotas: per product with something known, the last values found.
pub fn quotas(claude_records: bool, codex_rollouts: &[PathBuf]) -> Vec<Value> {
    let mut out = Vec::new();
    if claude_records && std::env::var_os("CLAUDE_CONFIG_DIR").is_none_or(|v| v.is_empty()) {
        if let Some(q) = read_usage(&std::env::temp_dir().join(USAGE_FILE)) {
            out.push(q);
        }
    }
    // The rollout written last says the newest limits.
    let newest = codex_rollouts.iter().filter_map(|p| Some((modified(p)?, p))).max_by_key(|(t, _)| *t);
    if let Some((_, path)) = newest {
        if let Some(q) = model::tail(path).and_then(|t| codex_limits(&t)) {
            out.push(q);
        }
    }
    out
}

/// The status line's cache, while it is fresh.
fn read_usage(path: &Path) -> Option<Value> {
    let meta = fs::metadata(path).ok()?;
    if !meta.is_file() || meta.len() > USAGE_MAX || meta.modified().ok()?.elapsed().ok()? > USAGE_FRESH {
        return None;
    }
    claude_usage(&fs::read(path).ok()?)
}

/// `five_hour` and `seven_day` of the status line's cache: `utilization` (0 to 100) and `resets_at` (Unix seconds or
/// an ISO 8601 time) where present.
pub fn claude_usage(raw: &[u8]) -> Option<Value> {
    let v: Value = serde_json::from_slice(raw).ok()?;
    let mut windows = Vec::new();
    for (key, name) in [("five_hour", "5h"), ("seven_day", "7d")] {
        let w = &v[key];
        let Some(used) = w["utilization"].as_f64().filter(|u| u.is_finite()) else { continue };
        let mut win = Map::new();
        win.insert("name".into(), json!(name));
        win.insert("used_percent".into(), json!(used.clamp(0.0, 100.0)));
        if let Some(t) = time_of(&w["resets_at"]) {
            win.insert("resets_at".into(), json!(t));
        }
        windows.push(Value::Object(win));
    }
    if windows.is_empty() {
        return None;
    }
    Some(json!({"product": "claude-code", "windows": windows}))
}

/// `rate_limits` of the last line that carries one, read from the end backwards.
pub fn codex_limits(tail: &[u8]) -> Option<Value> {
    let marker = &b"\"rate_limits\""[..];
    for line in tail.split(|c| *c == b'\n').rev() {
        if !line.windows(marker.len()).any(|w| w == marker) {
            continue;
        }
        let Ok(v) = serde_json::from_slice::<Value>(line) else { continue };
        let limits = [&v["payload"]["rate_limits"], &v["payload"]["info"]["rate_limits"], &v["rate_limits"]]
            .into_iter()
            .find(|l| l.is_object());
        let Some(limits) = limits else { continue };
        let mut windows = Vec::new();
        for key in ["primary", "secondary"] {
            let w = &limits[key];
            let (Some(used), Some(minutes)) = (w["used_percent"].as_f64(), w["window_minutes"].as_u64()) else { continue };
            if !used.is_finite() || minutes == 0 {
                continue;
            }
            let mut win = Map::new();
            win.insert("name".into(), json!(window_name(minutes)));
            win.insert("used_percent".into(), json!(used.clamp(0.0, 100.0)));
            if let Some(t) = w["resets_at"].as_u64() {
                win.insert("resets_at".into(), json!(t));
            }
            windows.push(Value::Object(win));
        }
        if windows.is_empty() {
            continue;
        }
        let mut q = Map::new();
        q.insert("product".into(), json!("codex"));
        if let Some(plan) = limits["plan_type"].as_str().filter(|p| valid_plan(p)) {
            q.insert("plan".into(), json!(plan));
        }
        q.insert("windows".into(), Value::Array(windows));
        return Some(Value::Object(q));
    }
    None
}

/// 300 minutes is "5h", 10080 "week"; any other length by its largest whole unit ("2d", "3h", "45m").
fn window_name(minutes: u64) -> String {
    match minutes {
        300 => "5h".into(),
        10080 => "week".into(),
        m if m % 1440 == 0 => format!("{}d", m / 1440),
        m if m % 60 == 0 => format!("{}h", m / 60),
        m => format!("{m}m"),
    }
}

/// What the server accepts: 1 to 40 printable characters.
fn valid_plan(s: &str) -> bool {
    !s.is_empty() && s.chars().count() <= 40 && !s.chars().any(char::is_control)
}

/// Unix seconds from a number or from an ISO 8601 time ("2026-11-17T05:00:00.5+08:00", "...Z").
fn time_of(v: &Value) -> Option<u64> {
    if let Some(n) = v.as_f64().filter(|n| n.is_finite() && *n >= 0.0) {
        return Some(n as u64);
    }
    iso_seconds(v.as_str()?)
}

fn iso_seconds(s: &str) -> Option<u64> {
    let b = s.as_bytes();
    let num = |from: usize, len: usize| -> Option<i64> {
        let part = s.get(from..from + len)?;
        part.bytes().all(|c| c.is_ascii_digit()).then(|| part.parse().ok())?
    };
    if b.len() < 19 || b[4] != b'-' || b[7] != b'-' || !matches!(b[10], b'T' | b't' | b' ') || b[13] != b':' || b[16] != b':' {
        return None;
    }
    let (y, mo, d, h, mi, se) = (num(0, 4)?, num(5, 2)?, num(8, 2)?, num(11, 2)?, num(14, 2)?, num(17, 2)?);
    if !(1..=12).contains(&mo) || !(1..=31).contains(&d) || h > 23 || mi > 59 || se > 60 {
        return None;
    }
    let mut i = 19;
    if b.get(i) == Some(&b'.') {
        i += 1;
        while b.get(i).is_some_and(u8::is_ascii_digit) {
            i += 1;
        }
    }
    let offset = match b.get(i) {
        Some(b'Z' | b'z') if i + 1 == b.len() => 0,
        Some(sign @ (b'+' | b'-')) if i + 6 == b.len() && b[i + 3] == b':' => {
            let o = num(i + 1, 2)? * 3600 + num(i + 4, 2)? * 60;
            if *sign == b'+' { o } else { -o }
        }
        None => 0, // no zone: taken as UTC
        _ => return None,
    };
    // Days from 1970-01-01 to the date (Howard Hinnant's days_from_civil).
    let (y, m) = if mo <= 2 { (y - 1, mo + 9) } else { (y, mo - 3) };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let doy = (153 * m + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days = era * 146097 + doe - 719468;
    u64::try_from(days * 86400 + h * 3600 + mi * 60 + se - offset).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_last_rate_limits_of_a_rollout_are_the_codex_quota() {
        let rollout = concat!(
            r#"{"type":"event_msg","payload":{"type":"token_count","rate_limits":{"primary":{"used_percent":80.0,"window_minutes":300,"resets_at":1}}}}"#, "\n",
            r#"{"type":"event_msg","payload":{"type":"token_count","info":null,"rate_limits":{"limit_id":"codex","primary":{"used_percent":1.0,"window_minutes":10080,"resets_at":1795260741},"secondary":null,"plan_type":"prolite"}}}"#, "\n",
            r#"{"type":"event_msg","payload":{"type":"token_count","rate_limits":null}}"#, "\n",
            r#"{"type":"response_item","payload":{"text":"\"rate_limits\" in a message"}}"#, "\r\n",
            "not json \"rate_limits\"\n"
        );
        let q = codex_limits(rollout.as_bytes()).expect("a quota");
        assert_eq!(
            q,
            json!({"product": "codex", "plan": "prolite",
                   "windows": [{"name": "week", "used_percent": 1.0, "resets_at": 1795260741u64}]})
        );
        let both = r#"{"payload":{"rate_limits":{"primary":{"used_percent":120,"window_minutes":300},"secondary":{"used_percent":41.5,"window_minutes":2880,"resets_at":"soon"},"plan_type":"\u0007"}}}"#;
        assert_eq!(
            codex_limits(both.as_bytes()).unwrap(),
            json!({"product": "codex", "windows": [{"name": "5h", "used_percent": 100.0},
                                                    {"name": "2d", "used_percent": 41.5}]}),
            "a percentage is kept within 0 to 100, a time that is no number and a plan that is not text are left out"
        );
        assert_eq!(codex_limits(b"{\"rate_limits\":{\"primary\":null}}\n"), None);
        assert_eq!(codex_limits(b""), None);
        assert_eq!((window_name(60), window_name(45), window_name(1440)), ("1h".into(), "45m".into(), "1d".into()));
    }

    #[test]
    fn the_status_lines_cache_is_the_claude_code_quota() {
        let cache = br#"{"five_hour":{"utilization":23.5,"resets_at":"2026-11-17T05:00:00.123456+00:00"},
                         "seven_day":{"utilization":41,"resets_at":1795260741},"seven_day_opus":null,"token":"never read"}"#;
        assert_eq!(
            claude_usage(cache).unwrap(),
            json!({"product": "claude-code", "windows": [
                {"name": "5h", "used_percent": 23.5, "resets_at": 1794891600u64},
                {"name": "7d", "used_percent": 41.0, "resets_at": 1795260741u64}]})
        );
        let partial = br#"{"five_hour":{"utilization":7},"seven_day":{"utilization":"41"}}"#;
        assert_eq!(claude_usage(partial).unwrap(), json!({"product": "claude-code", "windows": [{"name": "5h", "used_percent": 7.0}]}));
        assert_eq!(claude_usage(br#"{"five_hour":null}"#), None);
        assert_eq!(claude_usage(b"not json"), None);
    }

    #[test]
    fn iso_times_with_a_zone_are_unix_seconds() {
        assert_eq!(iso_seconds("1970-01-01T00:00:00Z"), Some(0));
        assert_eq!(iso_seconds("2026-11-17T13:00:00+08:00"), Some(1794891600));
        assert_eq!(iso_seconds("2026-11-17T05:00:00"), Some(1794891600));
        assert_eq!(iso_seconds("2000-02-29T12:30:15.9-01:30"), Some(951_832_815));
        for bad in ["2026-13-01T00:00:00Z", "2026-11-17", "2026-11-17T05:00:00+0800", "x026-11-17T05:00:00Z", "2026-11-17T05:00:00Zjunk"] {
            assert_eq!(iso_seconds(bad), None, "{bad}");
        }
    }

    #[test]
    fn a_stale_or_missing_cache_is_unknown() {
        let dir = std::env::temp_dir().join(format!("asterism-report-test-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let f = dir.join(USAGE_FILE);
        assert_eq!(read_usage(&f), None, "no file");
        fs::write(&f, br#"{"five_hour":{"utilization":5}}"#).unwrap();
        assert!(read_usage(&f).is_some(), "a fresh one is read");
        let old = SystemTime::now() - Duration::from_secs(16 * 60);
        fs::File::options().write(true).open(&f).unwrap().set_modified(old).unwrap();
        assert_eq!(read_usage(&f), None, "older than 15 minutes: unknown");
        assert!(modified(&f).is_some_and(|t| t + 15 * 60 < unix(SystemTime::now()).unwrap()));
        let _ = fs::remove_dir_all(&dir);
    }
}
