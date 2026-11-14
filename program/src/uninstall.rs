//! `asterism uninstall [--forget]`, for a person: stop the resident program, take `asterism-local` out of
//! every product it is in (with the product's own command) and the approval-free entry it may have set in
//! Claude Code, and delete what Asterism keeps in the state folder except `projects/` (the computer stays
//! authorised; `--forget` deletes that too). Only names Asterism itself creates are deleted, so a state folder
//! set by mistake to a folder with other files in it loses none of them.

use crate::allow;
use crate::local;
use crate::push;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, Instant};

const OURS: [&str; 10] = [
    "bin", "daemon.json", "daemon.lock", "daemon.log", "daemon.log.1", "threads.json", "pending.json",
    "state.lock", "update.json", "projects",
];

pub fn run(home: &Path, args: &[String]) -> i32 {
    let forget = match args {
        [] => false,
        [a] if a == "--forget" => true,
        _ => {
            eprintln!("Usage: asterism uninstall [--forget]");
            return 2;
        }
    };
    let mut code = 0;
    let mut did = false;

    // Any version: one from before 0.1.2 does not know the request to stop, and is ended all the same.
    if let Some(info) = local::running(home) {
        match local::stop_resident(&info) {
            Ok(()) => println!("Stopped the resident program (process {}).", info.pid),
            Err(e) => {
                eprintln!(
                    "The resident program (process {pid}) {e}. End process {pid} yourself (in the Task Manager on Windows, with `kill {pid}` elsewhere) and run `asterism uninstall` again.",
                    pid = info.pid
                );
                code = 1;
            }
        }
        did = true;
    }

    let mut removed_from_product = false;
    for p in ["claude", "codex"] {
        if !allow::added(p) {
            continue;
        }
        did = true;
        match remove_from(p) {
            Ok(()) => {
                println!("Removed the MCP server asterism-local from {}.", allow::display(p));
                removed_from_product = true;
            }
            Err(e) => {
                println!("{e}");
                code = 1;
            }
        }
    }
    match allow::disallow_claude() {
        Ok(Some(path)) => {
            println!("Removed mcp__asterism-local from permissions.allow in {} (Claude Code).", path.display());
            did = true;
        }
        Ok(None) => {}
        Err(e) => {
            println!("The approval-free entry of Claude Code was not removed: {e}.");
            code = 1;
        }
    }
    if removed_from_product {
        println!("Agent sessions that are open now keep Asterism's tools until they end.");
    }

    let (deleted, left) = delete_files(home, forget);
    if deleted > 0 {
        did = true;
        if forget {
            println!("Deleted Asterism's files in {}, this computer's credentials included.", home.display());
        } else {
            println!(
                "Deleted Asterism's files in {} except projects/: this computer stays authorised (`asterism uninstall --forget` deletes that too).",
                home.display()
            );
        }
    }
    for l in &left {
        println!("Left: {l}");
    }
    if forget {
        let _ = fs::remove_dir(home); // only when empty
    }
    if !did && left.is_empty() {
        println!("Nothing of Asterism was found to remove.");
    }
    code
}

fn remove_from(product: &str) -> Result<(), String> {
    let cmd = crate::join::remove_command(product);
    let shown = push::shown(&cmd);
    let name = allow::display(product);
    let Some((found, _)) = push::command(product) else {
        return Err(format!("No `{product}` that can be started was found, so asterism-local is still in {name}. Run this yourself:\n  {shown}"));
    };
    let mut c = Command::new(&found);
    c.args(&cmd[1..]);
    match push::run(&mut c, Duration::from_secs(120)) {
        Ok((st, _, _)) if st.success() && !allow::added(product) => Ok(()),
        Ok((st, out, err)) => {
            let said = if err.trim().is_empty() { out } else { err };
            Err(format!(
                "Removing asterism-local from {name} failed (exit {}): {}\nRun this yourself:\n  {shown}",
                st.code().map_or("a signal".into(), |c| c.to_string()),
                said.trim()
            ))
        }
        Err(e) => Err(format!("`{}` could not be started ({e}). Run this yourself:\n  {shown}", found.display())),
    }
}

/// (how many entries were deleted, what is left and why).
fn delete_files(home: &Path, forget: bool) -> (usize, Vec<String>) {
    let me = std::env::current_exe().ok().and_then(|p| fs::canonicalize(p).ok());
    let mut deleted = 0;
    let mut left = Vec::new();
    let Ok(dir) = fs::read_dir(home) else { return (0, left) };
    let mut entries: Vec<PathBuf> = dir.flatten().map(|e| e.path()).collect();
    entries.sort();
    for path in entries {
        let name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
        let ours = OURS.contains(&name.as_str()) || name.ends_with(".part");
        if !ours || (name == "projects" && !forget) {
            continue;
        }
        if path.is_dir() {
            // bin/ may hold the program running this command, or one an open session runs from.
            for f in fs::read_dir(&path).map(|d| d.flatten().map(|e| e.path()).collect::<Vec<_>>()).unwrap_or_default() {
                if let Err(e) = remove(&f) {
                    let running_me = me.is_some() && fs::canonicalize(&f).ok() == me;
                    left.push(if running_me {
                        format!("{} (the program running this command cannot delete itself here; delete it yourself)", f.display())
                    } else {
                        format!("{} ({e}; it may be in use by an open agent session: delete it once that has ended)", f.display())
                    });
                }
            }
            if fs::remove_dir(&path).is_ok() {
                deleted += 1;
            } else if left.is_empty() {
                left.push(format!("{} (not empty)", path.display()));
            }
        } else {
            match remove(&path) {
                Ok(()) => deleted += 1,
                Err(e) => left.push(format!("{} ({e})", path.display())),
            }
        }
    }
    (deleted, left)
}

/// Delete a file; a file the resident program held a moment ago may still be locked for a little while.
fn remove(path: &Path) -> std::io::Result<()> {
    let end = Instant::now() + Duration::from_secs(3);
    loop {
        match fs::remove_file(path) {
            Ok(()) => return Ok(()),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(()),
            Err(_) if Instant::now() < end => std::thread::sleep(Duration::from_millis(100)),
            Err(e) => return Err(e),
        }
    }
}
