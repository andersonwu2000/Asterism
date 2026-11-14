//! The resident program keeps itself up to date: it asks the server of its first project for the manifest of
//! builds (`/dl/manifest.json`), and when that offers a version it has not acted on yet, it fetches the build
//! for this platform, checks its size and SHA-256, puts it in place of `<state folder>/bin/asterism[.exe]` and
//! starts it as the resident program before it exits.
//!
//! Only a program running from that very file does this; a development build elsewhere never replaces itself.
//! The version last acted on (installed, or fetched and found impossible to install) is remembered in
//! `update.json`, so the same offer is not fetched again and again. A failed download or a wrong checksum is
//! not remembered: the next check tries again.

use crate::daemon::{log_line as log, release_lock, take_lock, write_daemon_again};
use crate::http;
use crate::local;
use crate::state;
use serde_json::json;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

const FIRST_CHECK: Duration = Duration::from_secs(3);

pub fn installed(home: &Path) -> PathBuf {
    home.join("bin").join(if cfg!(windows) { "asterism.exe" } else { "asterism" })
}

fn platform() -> Option<String> {
    let system = if cfg!(windows) {
        "windows"
    } else if cfg!(target_os = "macos") {
        "macos"
    } else if cfg!(target_os = "linux") {
        "linux"
    } else {
        return None;
    };
    let arch = if cfg!(target_arch = "x86_64") {
        "x64"
    } else if cfg!(target_arch = "aarch64") {
        "arm64"
    } else {
        return None;
    };
    Some(format!("{system}-{arch}"))
}

fn same_file(a: &Path, b: &Path) -> bool {
    matches!((fs::canonicalize(a), fs::canonicalize(b)), (Ok(x), Ok(y)) if x == y)
}

/// Start checking, if this program runs from the state folder's `bin/`.
pub fn start(home: PathBuf) {
    let Ok(me) = std::env::current_exe() else { return };
    if !same_file(&me, &installed(&home)) {
        return;
    }
    let every = std::env::var("ASTERISM_UPDATE_CHECK_S")
        .ok()
        .and_then(|v| v.trim().parse::<u64>().ok())
        .filter(|s| *s > 0)
        .unwrap_or(86400);
    std::thread::spawn(move || {
        std::thread::sleep(FIRST_CHECK);
        loop {
            clean_leftovers(&home);
            // A bug here must not end the resident program; the next check tries again.
            let _ = std::panic::catch_unwind(|| check(&home));
            std::thread::sleep(Duration::from_secs(every));
        }
    });
}

/// Files of earlier updates: the program moved aside (on Windows a running file can be moved, not deleted,
/// so it is removed once nothing runs from it any more) and an unfinished download.
fn clean_leftovers(home: &Path) {
    let Ok(dir) = fs::read_dir(home.join("bin")) else { return };
    for e in dir.flatten() {
        let name = e.file_name().to_string_lossy().into_owned();
        if name.starts_with("asterism") && (name.contains(".old-") || name.ends_with(".new")) {
            let _ = fs::remove_file(e.path());
        }
    }
}

fn last_acted(home: &Path) -> Option<String> {
    state::read_json(&home.join("update.json"))?["version"].as_str().map(String::from)
}

fn remember(home: &Path, version: &str) {
    let _ = state::write_private(&home.join("update.json"), json!({"version": version}).to_string().as_bytes());
}

fn check(home: &Path) {
    let Some(project) = state::load_projects(home).into_iter().next() else { return };
    let Some((server, _)) = project.url.rsplit_once('/') else { return };
    let agent = http::agent();
    let manifest = match http::call(&agent, "GET", &format!("{server}/dl/manifest.json"), None, &[], &[], Duration::from_secs(30)) {
        Ok(m) => m,
        Err(e) => {
            log(&format!("update check failed: {e:?}"));
            return;
        }
    };
    let Some(version) = manifest["version"].as_str().filter(|v| !v.is_empty()) else { return };
    if version == crate::VERSION || last_acted(home).as_deref() == Some(version) {
        return;
    }
    let Some(file) = platform().and_then(|p| manifest["files"].get(&p).cloned()) else {
        log(&format!("version {version} is offered, but not for this platform"));
        remember(home, version);
        return;
    };
    let (Some(name), Some(sha), Some(size)) = (file["name"].as_str(), file["sha256"].as_str(), file["size"].as_u64()) else {
        log(&format!("update to {version} failed: the manifest's entry is incomplete"));
        return;
    };
    let url = file["url"].as_str().map(String::from).unwrap_or_else(|| format!("{server}/dl/{name}"));
    let target = installed(home);
    let new = target.with_file_name(format!("{}.new", target.file_name().unwrap_or_default().to_string_lossy()));
    let fetched = http::download(&agent, &url, &new, size, Duration::from_secs(600));
    let ok = match fetched {
        Err(e) => Err(format!("the download failed ({e:?})")),
        Ok(n) if n != size => Err(format!("the download has {n} bytes, the manifest says {size}")),
        Ok(_) => match fs::read(&new) {
            Ok(bytes) if hex(&Sha256::digest(&bytes)) == sha.to_ascii_lowercase() => Ok(()),
            Ok(_) => Err("the download does not match its SHA-256".into()),
            Err(e) => Err(format!("the download cannot be read ({e})")),
        },
    };
    if let Err(e) = ok {
        log(&format!("update to {version} failed: {e}"));
        let _ = fs::remove_file(&new);
        return;
    }
    // From here on the offer counts as acted on, whether it takes or not: no fetching it again and again.
    remember(home, version);
    install(home, &target, &new, version);
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// Move the running program aside, put the new one in its place, and hand over to it. If it does not answer
/// in time, put the old file back and go on as before.
fn install(home: &Path, target: &Path, new: &Path, version: &str) {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(new, fs::Permissions::from_mode(0o755));
    }
    let aside = target.with_file_name(format!(
        "{}.old-{}",
        target.file_name().unwrap_or_default().to_string_lossy(),
        std::process::id()
    ));
    if let Err(e) = fs::rename(target, &aside) {
        log(&format!("update to {version} failed: the program cannot be moved aside ({e})"));
        let _ = fs::remove_file(new);
        return;
    }
    if let Err(e) = fs::rename(new, target) {
        let _ = fs::rename(&aside, target);
        log(&format!("update to {version} failed: the new program cannot be put in place ({e})"));
        return;
    }
    release_lock();
    let env = [("ASTERISM_HOME", home.as_os_str()), ("ASTERISM_REPLACING", std::ffi::OsStr::new("1"))];
    let started = crate::sys::spawn_detached(target, &["daemon"], &env, home).is_ok();
    let end = Instant::now() + Duration::from_secs(20);
    while started && Instant::now() < end {
        if local::running(home).is_some_and(|info| info.pid != std::process::id()) {
            log(&format!("updated from {} to {version}", crate::VERSION));
            // The sessions' `mcp` see our connections end and find the new program through daemon.json.
            std::process::exit(0);
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    // It did not come up: the old program goes back in place and keeps serving.
    let failed = target.with_file_name(format!("{}.new", target.file_name().unwrap_or_default().to_string_lossy()));
    let _ = fs::rename(target, &failed);
    let _ = fs::rename(&aside, target);
    match take_lock(home) {
        Ok(true) => {}
        _ => log("after a failed update the lock could not be taken back"),
    }
    write_daemon_again(home);
    log(&format!("update to {version} failed: the new program did not start; still running {}", crate::VERSION));
}
