//! `asterism join <link> [--name NAME] [--client claude|codex|none]`: authorise this computer with an agent
//! invitation link, make sure the resident program runs, add `asterism mcp` to the product that ran us, and
//! remember the name this conversation should register with.

use crate::http::{self, Fail};
use crate::local;
use crate::push;
use crate::state;
use serde_json::json;
use std::path::Path;
use std::process::Command;
use std::time::Duration;

const SERVER_NAME: &str = "asterism-local";

// Agent-facing wording, word for word from the contract.
pub const ENDING: &str = "This computer is set up. If you can see the Asterism tools of `asterism-local` in this \
conversation, call `register` now with an agent name of your choice (or the one your user gave you). If you cannot \
see them, this conversation started before they were added: tell your user that Asterism is installed and ask them \
to reopen this conversation (close it and open the same conversation again; in a terminal, resume it; in a desktop \
app or an IDE, restart the app and come back to this conversation), then call `register` when you are back.";
const NOT_ADDED: &str = "Not added to any agent. To add it, run one of:";

const USAGE: &str = "Usage: asterism join <invitation link> [--name NAME] [--client claude|codex|none]";

#[derive(Debug, PartialEq)]
struct Link {
    link: String,
    project_url: String,
}

/// `<scheme>://<host>[/<path>]/<slug>/a/<code>`, as the server makes them.
fn parse_link(raw: &str) -> Option<Link> {
    let s = raw.trim().trim_end_matches('/');
    let (scheme, rest) = s.split_once("://")?;
    if scheme != "https" && scheme != "http" {
        return None;
    }
    let parts: Vec<&str> = rest.split('/').collect();
    let n = parts.len();
    if n < 4 || parts[n - 2] != "a" {
        return None;
    }
    let host_ok = !parts[0].is_empty()
        && parts[0].chars().all(|c| c.is_ascii_alphanumeric() || ".-:[]".contains(c));
    let seg_ok = |p: &str| !p.is_empty() && p.chars().all(|c| c.is_ascii_alphanumeric() || "._~-".contains(c));
    let code_ok = |p: &str| !p.is_empty() && p.chars().all(|c| c.is_ascii_alphanumeric() || "_-".contains(c));
    if !host_ok || !parts[1..n - 2].iter().all(|p| seg_ok(p)) || !valid_slug(parts[n - 3]) || !code_ok(parts[n - 1]) {
        return None;
    }
    Some(Link { link: s.to_string(), project_url: format!("{scheme}://{}", parts[..n - 2].join("/")) })
}

fn valid_slug(s: &str) -> bool {
    let b = s.as_bytes();
    !b.is_empty()
        && b.len() <= 40
        && (b[0].is_ascii_lowercase() || b[0].is_ascii_digit())
        && b.iter().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || *c == b'-')
}

fn valid_name(s: &str) -> bool {
    let b = s.as_bytes();
    !b.is_empty()
        && b.len() <= 40
        && b[0].is_ascii_alphanumeric()
        && b.iter().all(|c| c.is_ascii_alphanumeric() || b"._-".contains(c))
}

fn env(name: &str) -> Option<String> {
    std::env::var(name).ok().map(|v| v.trim().to_string()).filter(|v| !v.is_empty())
}

struct Args {
    link: String,
    name: Option<String>,
    client: Option<String>,
}

fn parse_args(args: &[String]) -> Result<Args, String> {
    let (mut link, mut name, mut client) = (None, None, None);
    let mut i = 0;
    while i < args.len() {
        let a = &args[i];
        let (key, inline) = match a.split_once('=') {
            Some((k, v)) if k.starts_with("--") => (k.to_string(), Some(v.to_string())),
            _ => (a.clone(), None),
        };
        match key.as_str() {
            "--name" | "--client" => {
                let v = match inline {
                    Some(v) => v,
                    None => {
                        i += 1;
                        args.get(i).cloned().ok_or(format!("{key} needs a value."))?
                    }
                };
                if key == "--name" {
                    name = Some(v);
                } else {
                    client = Some(v);
                }
            }
            k if k.starts_with("--") => return Err(format!("Unknown option {k}.")),
            _ if link.is_none() => link = Some(a.clone()),
            _ => return Err(format!("Unexpected argument {a}.")),
        }
        i += 1;
    }
    Ok(Args { link: link.ok_or("The invitation link is missing.")?, name, client })
}

pub fn run(home: &Path, raw: &[String]) -> i32 {
    let args = match parse_args(raw) {
        Ok(a) => a,
        Err(e) => {
            eprintln!("{e}\n{USAGE}");
            return 2;
        }
    };
    let Some(link) = parse_link(&args.link) else {
        println!("This is not an Asterism agent invitation link; such a link looks like https://<host>/<project>/a/<code>.");
        return 2;
    };
    if let Some(n) = args.name.as_deref().filter(|n| !valid_name(n)) {
        println!("The name {n:?} cannot be an agent name: 1 to 40 letters, digits, dots, dashes or underscores, starting with a letter or digit.");
        return 2;
    }
    // Which product runs us: the one to add the tools to.
    let product = match args.client.as_deref() {
        Some("claude") => Some("claude"),
        Some("codex") => Some("codex"),
        Some("none") => None,
        Some(other) => {
            println!("--client must be claude, codex or none, not {other:?}.");
            return 2;
        }
        None if env("CODEX_THREAD_ID").is_some() => Some("codex"),
        None if env("CLAUDE_CODE_SESSION_ID").is_some() => Some("claude"),
        None => None,
    };

    // 1. Redeem the link. A computer that already holds a credential for this project shows it, so that the
    //    server keeps it instead of making a second one.
    let agent = http::agent();
    let held = state::load_project(home, &link.project_url);
    let auth = held.as_ref().map(|p| format!("Bearer {}", p.credential));
    let headers: Vec<(&str, &str)> = auth.iter().map(|a| ("Authorization", a.as_str())).collect();
    let body = json!({
        "computer": crate::sys::hostname(),
        // The server records which product redeemed the link; with none, the more common one.
        "product": if product == Some("codex") { "codex" } else { "claude-code" },
    });
    let url = format!("{}/redeem", link.link);
    let got = match http::call(&agent, "POST", &url, Some(&body), &headers, &[], Duration::from_secs(30)) {
        Ok(v) => v,
        Err(Fail::Refused { message, .. }) => {
            println!("{message}");
            return 1;
        }
        Err(Fail::Unreachable(e)) => {
            println!("The Asterism server at {} cannot be reached ({e}). Nothing was changed; try again later.", link.project_url);
            return 1;
        }
    };
    let person = got["person"].as_str().unwrap_or("?").to_string();
    let project_name = got["project"]["name"].as_str().unwrap_or(state::slug_of(&link.project_url).as_str()).to_string();
    match got["credential"].as_str() {
        Some(cred) => {
            if let Err(e) = state::save_credential(home, &link.project_url, &person, cred) {
                println!("The link was accepted, but this computer's credential could not be stored in {} ({e}). Ask your user for a new link once that is fixed.", home.display());
                return 1;
            }
            println!("This computer now acts for {person} in the project \"{project_name}\" ({}).", link.project_url);
        }
        None if held.is_some() => {
            println!("This computer already acts for {person} in the project \"{project_name}\" ({}); it keeps its credential.", link.project_url);
        }
        None => {
            println!("The server accepted the link but gave this computer no credential. Ask your user for a new link.");
            return 1;
        }
    }

    // 2. The resident program.
    if let Err(e) = local::ensure_daemon(home) {
        println!("The resident program could not be started: {e}. The next agent session starts it again.");
    }

    // A Codex conversation can be woken from now on, by the `codex` its own environment finds.
    if let Some(thread) = env("CODEX_THREAD_ID").filter(|t| state::valid_thread(t)) {
        if let Some(argv) = push::codex_argv() {
            let _ = state::set_thread(home, &thread, Some(&argv));
        }
    }

    // 5. "This conversation registers as NAME in this project", for its `mcp` to act on.
    if let Some(name) = &args.name {
        let session = env("ASTERISM_SESSION").or_else(|| env("CODEX_THREAD_ID")).or_else(|| env("CLAUDE_CODE_SESSION_ID"));
        match session.filter(|s| state::valid_session(s)) {
            Some(s) => {
                let key = state::project_key(&link.project_url);
                let kind = if product == Some("codex") { "codex" } else { "claude-code" };
                if let Err(e) = state::note_pending(home, &s, &key, name, kind) {
                    println!("The name {name} could not be remembered ({e}); register with it yourself.");
                }
            }
            None => println!("This did not run inside an agent's conversation, so the name {name} is not remembered; register with it."),
        }
    }
    local::reload(home);

    // 3, 4. The tools, in the invited product only.
    let exe = std::env::current_exe().map(|p| p.to_string_lossy().into_owned()).unwrap_or_else(|_| "asterism".into());
    match product {
        None => {
            println!("{NOT_ADDED}");
            for p in ["claude", "codex"] {
                println!("  {}", push::shown(&add_command(p, &exe)));
            }
        }
        Some(p) => {
            if !add_to_product(p, &exe) {
                println!(
                    "Where things stand: this computer's approval is stored (running join again needs a new link but \
                     no new approval) and the resident program is installed; only adding the tools to {p} is left. \
                     Run the command above, then reopen this conversation."
                );
                return 3;
            }
        }
    }
    println!("{ENDING}");
    0
}

fn add_command(product: &str, exe: &str) -> Vec<String> {
    let mut c: Vec<String> = vec![product.into(), "mcp".into(), "add".into(), SERVER_NAME.into()];
    if product == "claude" {
        c.extend(["--scope".into(), "user".into()]);
    }
    c.extend(["--".into(), exe.into(), "mcp".into()]);
    c
}

fn remove_command(product: &str) -> Vec<String> {
    let mut c: Vec<String> = vec![product.into(), "mcp".into(), "remove".into(), SERVER_NAME.into()];
    if product == "claude" {
        c.extend(["--scope".into(), "user".into()]);
    }
    c
}

/// Add `asterism mcp` to the product's MCP servers with the product's own command, replacing an older entry
/// of the same name. False (and what to run by hand is printed) when that cannot be done.
fn add_to_product(product: &str, exe: &str) -> bool {
    let add = add_command(product, exe);
    let shown = push::shown(&add);
    let Some((found, shell)) = push::command(product) else {
        println!("No `{product}` that can be started was found, so nothing was added. Run this yourself:\n  {shown}");
        return false;
    };
    // A .cmd runs in cmd.exe, which acts on characters like & or %; then every argument must be free of them.
    if shell && add.iter().any(|a| a.chars().any(|c| "&|<>^%!\"\r\n".contains(c))) {
        println!("A path here contains characters the Windows shell would misread. Run this yourself:\n  {shown}");
        return false;
    }
    let run = |args: &[String]| {
        let mut cmd = Command::new(&found);
        cmd.args(&args[1..]);
        push::run(&mut cmd, Duration::from_secs(120))
    };
    let _ = run(&remove_command(product)); // an older entry under the same name, if any
    match run(&add) {
        Ok((st, _, _)) if st.success() => {
            println!("Added the MCP server {SERVER_NAME} to {product}.");
            let name = crate::allow::display(product);
            // Turning approval prompts off is a person's choice: an agent that runs join itself (the
            // environment names its conversation) leaves them as they are and only learns that it can be done.
            if env("CODEX_THREAD_ID").is_some() || env("CLAUDE_CODE_SESSION_ID").is_some() {
                println!(
                    "Asterism's tools will ask for approval in {name} when they are called. This can be turned off with `asterism allow`."
                );
                return true;
            }
            // Not a reason to fail the join: the tools work, only with a prompt the person can answer.
            match crate::allow::allow(product) {
                Ok(()) => println!("{}", crate::allow::ALLOWED.replace("{product}", name)),
                Err(e) => println!(
                    "Asterism's tools could not be allowed to run without asking in {name}: {e}. To allow them, {}.",
                    crate::allow::by_hand(product)
                ),
            }
            true
        }
        Ok((st, out, err)) => {
            let said = if err.trim().is_empty() { out } else { err };
            let tail: String = said.trim().chars().rev().take(400).collect::<Vec<_>>().into_iter().rev().collect();
            let code = st.code().map_or("a signal".into(), |c| c.to_string());
            println!("Adding the MCP server failed (exit {code}): {tail}\nRun this yourself:\n  {shown}");
            false
        }
        Err(e) => {
            println!("`{}` could not be started ({e}), so nothing was added. Run this yourself:\n  {shown}", found.display());
            false
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn links() {
        let l = parse_link("http://127.0.0.1:5000/lab/a/Abc_-9/").unwrap();
        assert_eq!(l.project_url, "http://127.0.0.1:5000/lab");
        assert_eq!(l.link, "http://127.0.0.1:5000/lab/a/Abc_-9");
        let l = parse_link("https://h.example/base/lab/a/x").unwrap();
        assert_eq!(l.project_url, "https://h.example/base/lab");
        assert!(parse_link("https://h.example/lab").is_none());
        assert!(parse_link("https://user@h.example/lab/a/x").is_none());
        assert!(parse_link("ftp://h.example/lab/a/x").is_none());
        assert!(parse_link("https://h.example/Lab/a/x").is_none());
        assert!(parse_link("https://h.example/lab/a/x?y").is_none());
    }

    #[test]
    fn arguments() {
        let a = parse_args(&["L".into(), "--name=piper".into(), "--client".into(), "none".into()]).unwrap();
        assert_eq!((a.link.as_str(), a.name.as_deref(), a.client.as_deref()), ("L", Some("piper"), Some("none")));
        assert!(parse_args(&["--name".into()]).is_err());
    }
}
