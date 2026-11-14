//! Let the product run the tools of `asterism-local` without asking. An agent is woken while its user may
//! be away; an approval prompt would leave it stuck (and `codex exec` with approval policy "never" refuses
//! the call outright). Each function changes only its own entry and keeps the rest of the file as it was.
//!
//! `join` does this for the product it hooks, whoever runs it: the person agreed to it when they made the
//! invitation link. `asterism allow` does it again on request (a repair).

use serde_json::Value;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

const CODEX_KEY: &str = "default_tools_approval_mode";
const CLAUDE_RULE: &str = "mcp__asterism-local";

fn user_dir(var: &str, default: &str) -> PathBuf {
    if let Some(d) = std::env::var_os(var).filter(|v| !v.is_empty()) {
        return PathBuf::from(d);
    }
    profile().join(default)
}

fn profile() -> PathBuf {
    let base = if cfg!(windows) { std::env::var_os("USERPROFILE") } else { std::env::var_os("HOME") };
    base.map(PathBuf::from).unwrap_or_default()
}

/// What a person sets by hand when this fails.
pub fn by_hand(product: &str) -> String {
    match product {
        "codex" => format!(
            "add the line {CODEX_KEY} = \"approve\" to the section [mcp_servers.asterism-local] of {}",
            user_dir("CODEX_HOME", ".codex").join("config.toml").display()
        ),
        _ => format!(
            "add \"{CLAUDE_RULE}\" to permissions.allow in {}",
            user_dir("CLAUDE_CONFIG_DIR", ".claude").join("settings.json").display()
        ),
    }
}

pub const ALLOWED: &str = "Asterism's tools were allowed to run without asking in {product}.";

/// `asterism allow [--client claude|codex]`: the person's explicit choice, for the named product or for every
/// product that has `asterism-local`.
pub fn run(args: &[String]) -> i32 {
    let client = match args {
        [] => None,
        [flag, v] if flag == "--client" => Some(v.as_str()),
        [one] => one.strip_prefix("--client="),
        _ => Some(""),
    };
    let products: Vec<&str> = match client {
        None => ["claude", "codex"].into_iter().filter(|p| added(p)).collect(),
        Some("claude") => vec!["claude"],
        Some("codex") => vec!["codex"],
        Some(_) => {
            eprintln!("Usage: asterism allow [--client claude|codex]");
            return 2;
        }
    };
    if products.is_empty() {
        println!("Asterism's tools are not added to Claude Code or Codex, so nothing was changed; run `asterism join` first.");
        return 1;
    }
    let mut code = 0;
    for p in products {
        if !added(p) {
            println!("Asterism's tools are not added to {}, so nothing was changed; run `asterism join` first.", display(p));
            code = 1;
            continue;
        }
        match allow(p) {
            Ok(()) => println!("{}", ALLOWED.replace("{product}", display(p))),
            Err(e) => {
                println!("Asterism's tools could not be allowed to run without asking in {}: {e}. To allow them, {}.", display(p), by_hand(p));
                code = 1;
            }
        }
    }
    code
}

pub fn display(product: &str) -> &'static str {
    if product == "codex" {
        "Codex"
    } else {
        "Claude Code"
    }
}

pub fn allow(product: &str) -> Result<(), String> {
    match product {
        "codex" => codex(&codex_config()),
        _ => claude(&claude_settings()),
    }
}

fn codex_config() -> PathBuf {
    user_dir("CODEX_HOME", ".codex").join("config.toml")
}

fn claude_settings() -> PathBuf {
    user_dir("CLAUDE_CONFIG_DIR", ".claude").join("settings.json")
}

/// Whether `asterism-local` is among the product's MCP servers (user scope), read from the product's files.
pub fn added(product: &str) -> bool {
    match product {
        "codex" => fs::read_to_string(codex_config()).is_ok_and(|t| codex_section(&t).is_some()),
        _ => {
            // Claude Code keeps its user-scope servers in .claude.json: inside CLAUDE_CONFIG_DIR when that is
            // set, else in the home folder itself.
            let file = match std::env::var_os("CLAUDE_CONFIG_DIR").filter(|v| !v.is_empty()) {
                Some(d) => PathBuf::from(d).join(".claude.json"),
                None => profile().join(".claude.json"),
            };
            fs::read(file)
                .ok()
                .and_then(|raw| serde_json::from_slice::<Value>(&raw).ok())
                .is_some_and(|v| v["mcpServers"].get("asterism-local").is_some())
        }
    }
}

/// Whether the product runs Asterism's tools without asking (read only).
pub fn allowed(product: &str) -> bool {
    match product {
        "codex" => fs::read_to_string(codex_config()).is_ok_and(|t| codex_section(&t).is_some_and(|s| s.2)),
        _ => fs::read(claude_settings())
            .ok()
            .and_then(|raw| serde_json::from_slice::<Value>(&raw).ok())
            .and_then(|v| v["permissions"]["allow"].as_array().cloned())
            .is_some_and(|a| a.iter().any(|x| x.as_str() == Some(CLAUDE_RULE))),
    }
}

/// The section `[mcp_servers.asterism-local]` of a Codex config: (its header line, the line after its end,
/// whether it holds the approval key), in lines as `split_inclusive('\n')` gives them.
fn codex_section(text: &str) -> Option<(usize, usize, bool)> {
    let lines: Vec<&str> = text.split_inclusive('\n').collect();
    let is_header = |l: &str| {
        let compact: String = l.trim().chars().filter(|c| !c.is_whitespace()).collect();
        compact == "[mcp_servers.asterism-local]" || compact == "[mcp_servers.\"asterism-local\"]"
    };
    let start = lines.iter().position(|l| is_header(l))?;
    let end = lines[start + 1..].iter().position(|l| l.trim_start().starts_with('[')).map_or(lines.len(), |i| start + 1 + i);
    let has_key = lines[start + 1..end].iter().any(|l| {
        l.split_once('=').is_some_and(|(k, _)| k.trim().trim_matches(|c| c == '"' || c == '\'') == CODEX_KEY)
    });
    Some((start, end, has_key))
}

/// `codex mcp add` has no option for this and does not keep a `-c` override, so the key is added to the
/// section that command wrote: one line inserted after the section's last line, nothing else touched.
fn codex(path: &Path) -> Result<(), String> {
    let text = fs::read_to_string(path).map_err(|e| format!("cannot read {} ({e})", path.display()))?;
    let lines: Vec<&str> = text.split_inclusive('\n').collect();
    let (start, end, has_key) =
        codex_section(&text).ok_or("there is no section [mcp_servers.asterism-local] in it")?;
    if has_key {
        return Ok(());
    }
    // After the last line of the section that is not blank, in the file's own line ending.
    let last = (start..end).rev().find(|&i| !lines[i].trim().is_empty()).unwrap_or(start);
    let eol = if lines[start].ends_with("\r\n") { "\r\n" } else { "\n" };
    let mut out = String::with_capacity(text.len() + 48);
    for (i, l) in lines.iter().enumerate() {
        out.push_str(l);
        if i == last {
            if !l.ends_with('\n') {
                out.push_str(eol);
            }
            out.push_str(&format!("{CODEX_KEY} = \"approve\"{eol}"));
        }
    }
    replace(path, out.as_bytes()).map_err(|e| format!("cannot write {} ({e})", path.display()))
}

/// The user settings of Claude Code: the server's tools in `permissions.allow`, once.
fn claude(path: &Path) -> Result<(), String> {
    let mut settings = match fs::read(path) {
        Ok(raw) => match serde_json::from_slice::<Value>(&raw) {
            Ok(v @ Value::Object(_)) => v,
            _ => return Err(format!("{} is not valid JSON, so it was left as it is", path.display())),
        },
        Err(e) if e.kind() == io::ErrorKind::NotFound => Value::Object(Default::default()),
        Err(e) => return Err(format!("cannot read {} ({e})", path.display())),
    };
    let perms = settings
        .as_object_mut()
        .and_then(|o| o.entry("permissions").or_insert_with(|| Value::Object(Default::default())).as_object_mut())
        .ok_or_else(|| format!("permissions in {} is not an object, so the file was left as it is", path.display()))?;
    let allow = perms
        .entry("allow")
        .or_insert_with(|| Value::Array(Vec::new()))
        .as_array_mut()
        .ok_or_else(|| format!("permissions.allow in {} is not a list, so the file was left as it is", path.display()))?;
    if allow.iter().any(|v| v.as_str() == Some(CLAUDE_RULE)) {
        return Ok(());
    }
    allow.push(Value::String(CLAUDE_RULE.into()));
    let text = serde_json::to_string_pretty(&settings).unwrap_or_default() + "\n";
    replace(path, text.as_bytes()).map_err(|e| format!("cannot write {} ({e})", path.display()))
}

/// Take `mcp__asterism-local` out of Claude Code's `permissions.allow` (only that entry). Ok(Some(path)) when
/// it was there and is gone, Ok(None) when there was nothing to take out.
pub fn disallow_claude() -> Result<Option<PathBuf>, String> {
    let path = claude_settings();
    let raw = match fs::read(&path) {
        Ok(raw) => raw,
        Err(e) if e.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(e) => return Err(format!("cannot read {} ({e})", path.display())),
    };
    let Ok(mut settings) = serde_json::from_slice::<Value>(&raw) else {
        return Err(format!("{} is not valid JSON, so it was left as it is", path.display()));
    };
    let Some(allow) = settings.pointer_mut("/permissions/allow").and_then(Value::as_array_mut) else { return Ok(None) };
    let before = allow.len();
    allow.retain(|v| v.as_str() != Some(CLAUDE_RULE));
    if allow.len() == before {
        return Ok(None);
    }
    let text = serde_json::to_string_pretty(&settings).unwrap_or_default() + "\n";
    replace(&path, text.as_bytes()).map_err(|e| format!("cannot write {} ({e})", path.display()))?;
    Ok(Some(path))
}

/// Replace the whole file at once, keeping the permissions it had.
fn replace(path: &Path, data: &[u8]) -> io::Result<()> {
    if let Some(dir) = path.parent() {
        fs::create_dir_all(dir)?;
    }
    let tmp = path.with_file_name(format!(
        "{}.asterism.{}.part",
        path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default(),
        std::process::id()
    ));
    fs::write(&tmp, data)?;
    if let Ok(meta) = fs::metadata(path) {
        let _ = fs::set_permissions(&tmp, meta.permissions());
    }
    fs::rename(&tmp, path).inspect_err(|_| {
        let _ = fs::remove_file(&tmp);
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn codex_section_gets_one_line() {
        let dir = std::env::temp_dir().join(format!("asterism-allow-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let p = dir.join("config.toml");
        let before = "# keep\r\n[mcp_servers.asterism-local]\r\ncommand = 'x'\r\nargs = [\"mcp\"]\r\n\r\n[other]\r\na = 1\r\n";
        fs::write(&p, before).unwrap();
        codex(&p).unwrap();
        codex(&p).unwrap();
        let after = fs::read_to_string(&p).unwrap();
        assert_eq!(after, before.replace("[\"mcp\"]\r\n", "[\"mcp\"]\r\ndefault_tools_approval_mode = \"approve\"\r\n"));
        fs::write(&p, "{ not json").unwrap();
        assert!(claude(&p).is_err());
        assert_eq!(fs::read_to_string(&p).unwrap(), "{ not json");
        let _ = fs::remove_dir_all(&dir);
    }
}
