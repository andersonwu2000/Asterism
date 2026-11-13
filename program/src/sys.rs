//! The few things that differ per operating system, kept in one place.

use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

/// This computer's name, as the person will see it on the project's pages.
pub fn hostname() -> String {
    #[cfg(windows)]
    let name = std::env::var("COMPUTERNAME").unwrap_or_default();
    #[cfg(unix)]
    let name = {
        let mut buf = [0u8; 256];
        // SAFETY: the buffer is valid for its length; the result is cut at the first NUL below.
        let rc = unsafe { libc::gethostname(buf.as_mut_ptr() as *mut libc::c_char, buf.len()) };
        if rc == 0 {
            let end = buf.iter().position(|&b| b == 0).unwrap_or(buf.len());
            String::from_utf8_lossy(&buf[..end]).into_owned()
        } else {
            String::new()
        }
    };
    let name = name.trim().to_string();
    if name.is_empty() {
        "computer".into()
    } else {
        name
    }
}

/// `n` bytes from the operating system's random source, as hex.
pub fn random_hex(n: usize) -> Result<String, String> {
    let mut buf = vec![0u8; n];
    getrandom::getrandom(&mut buf).map_err(|e| format!("no random numbers from the system ({e})"))?;
    Ok(buf.iter().map(|b| format!("{b:02x}")).collect())
}

pub fn epoch_s() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

/// `YYYY-MM-DDTHH:MM:SSZ` for the current time, as the Python helper writes it.
pub fn utc_iso() -> String {
    let t = epoch_s();
    let (days, rem) = ((t / 86400) as i64, t % 86400);
    // Civil date from days since 1970-01-01 (Howard Hinnant's algorithm).
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = yoe + era * 400 + if m <= 2 { 1 } else { 0 };
    format!("{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}Z", rem / 3600, rem % 3600 / 60, rem % 60)
}

#[cfg(windows)]
mod win {
    use std::ffi::c_void;
    #[link(name = "kernel32")]
    extern "system" {
        pub fn SetHandleInformation(handle: *mut c_void, mask: u32, flags: u32) -> i32;
    }
    pub const HANDLE_FLAG_INHERIT: u32 = 1;
    pub const DETACHED_PROCESS: u32 = 0x0000_0008;
    pub const CREATE_NEW_PROCESS_GROUP: u32 = 0x0000_0200;
    pub const CREATE_BREAKAWAY_FROM_JOB: u32 = 0x0100_0000;
    pub const CREATE_NO_WINDOW: u32 = 0x0800_0000;
}

/// Children of a program without a console (the resident program) would each open a console window.
pub fn no_window(cmd: &mut Command) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(win::CREATE_NO_WINDOW);
    }
    #[cfg(not(windows))]
    let _ = cmd;
}

/// Start `cmd` so that it outlives this process and the session that started it, and holds none of our
/// stdio: the resident program.
pub fn spawn_detached(cmd: &mut Command) -> std::io::Result<()> {
    #[cfg(windows)]
    {
        use std::os::windows::io::AsRawHandle;
        use std::os::windows::process::CommandExt;
        // Windows hands every inheritable handle to a child, not only the ones named as its stdio. Our
        // stdio handles are inheritable (our starter made them so for us); a resident program holding the
        // write end of `join`'s output pipe would keep whoever reads it waiting until it exits.
        for h in [
            std::io::stdin().as_raw_handle(),
            std::io::stdout().as_raw_handle(),
            std::io::stderr().as_raw_handle(),
        ] {
            if !h.is_null() {
                // SAFETY: a handle of this process; failure only means it was not inheritable anyway.
                unsafe { win::SetHandleInformation(h, win::HANDLE_FLAG_INHERIT, 0) };
            }
        }
        let base = win::DETACHED_PROCESS | win::CREATE_NEW_PROCESS_GROUP;
        // Breaking away from the starter's job keeps the program alive when the product closes the job
        // of the session (where the job allows it; otherwise CreateProcess refuses and we go without).
        cmd.creation_flags(base | win::CREATE_BREAKAWAY_FROM_JOB);
        if cmd.spawn().is_ok() {
            return Ok(());
        }
        cmd.creation_flags(base);
        cmd.spawn().map(|_| ())
    }
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        // SAFETY: setsid is async-signal-safe; a new session leaves the terminal's hangup and job control.
        unsafe {
            cmd.pre_exec(|| {
                libc::setsid();
                Ok(())
            });
        }
        let mut child = cmd.spawn()?;
        // Reap it if it exits while we run (a second resident program exits at once), so it does not
        // linger as a zombie.
        std::thread::spawn(move || {
            let _ = child.wait();
        });
        Ok(())
    }
}
