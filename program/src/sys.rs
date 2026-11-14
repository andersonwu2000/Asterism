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
    pub const CREATE_UNICODE_ENVIRONMENT: u32 = 0x0000_0400;
    const STARTF_USESTDHANDLES: u32 = 0x0000_0100;

    #[repr(C)]
    struct StartupInfoW {
        cb: u32,
        reserved: *mut u16,
        desktop: *mut u16,
        title: *mut u16,
        x: u32,
        y: u32,
        x_size: u32,
        y_size: u32,
        x_count_chars: u32,
        y_count_chars: u32,
        fill_attribute: u32,
        flags: u32,
        show_window: u16,
        reserved2_size: u16,
        reserved2: *mut u8,
        std_input: *mut c_void,
        std_output: *mut c_void,
        std_error: *mut c_void,
    }

    #[repr(C)]
    struct ProcessInformation {
        process: *mut c_void,
        thread: *mut c_void,
        process_id: u32,
        thread_id: u32,
    }

    #[link(name = "kernel32")]
    extern "system" {
        fn CreateProcessW(
            application: *const u16,
            command_line: *mut u16,
            process_attributes: *mut c_void,
            thread_attributes: *mut c_void,
            inherit_handles: i32,
            creation_flags: u32,
            environment: *mut c_void,
            current_directory: *const u16,
            startup_info: *mut StartupInfoW,
            process_information: *mut ProcessInformation,
        ) -> i32;
        fn CloseHandle(handle: *mut c_void) -> i32;
    }

    fn wide(s: &std::ffi::OsStr) -> Vec<u16> {
        use std::os::windows::ffi::OsStrExt;
        s.encode_wide().chain(std::iter::once(0)).collect()
    }

    /// CreateProcessW with no handle inherited and no stdio (the program has none; Rust's stdio then
    /// discards what is written to it).
    pub fn create_process(
        exe: &std::path::Path,
        args: &[&str],
        env: &[(&str, &std::ffi::OsStr)],
        dir: &std::path::Path,
        flags: u32,
    ) -> std::io::Result<()> {
        use std::os::windows::ffi::OsStrExt;
        let exe_s = exe.as_os_str();
        if exe_s.encode_wide().any(|c| c == u16::from(b'"')) || args.iter().any(|a| a.contains(['"', ' ', '\t'])) {
            return Err(std::io::Error::other("a path or argument that cannot be quoted simply"));
        }
        // The program path quoted (it may hold spaces), then the plain arguments.
        let mut line: Vec<u16> = Vec::new();
        line.push(u16::from(b'"'));
        line.extend(exe_s.encode_wide());
        line.push(u16::from(b'"'));
        for a in args {
            line.push(u16::from(b' '));
            line.extend(a.encode_utf16());
        }
        line.push(0);
        // Our environment with `env` set over it, as "k=v\0...\0\0".
        let mut vars: Vec<(std::ffi::OsString, std::ffi::OsString)> =
            std::env::vars_os().filter(|(k, _)| !env.iter().any(|(e, _)| k.eq_ignore_ascii_case(e))).collect();
        vars.extend(env.iter().map(|(k, v)| (std::ffi::OsString::from(k), v.to_os_string())));
        vars.sort_by_key(|(k, _)| k.to_ascii_uppercase());
        let mut block: Vec<u16> = Vec::new();
        for (k, v) in &vars {
            block.extend(k.encode_wide());
            block.push(u16::from(b'='));
            block.extend(v.encode_wide());
            block.push(0);
        }
        block.push(0);
        let dir_w = wide(dir.as_os_str());
        // SAFETY: all-zero is a valid STARTUPINFOW / PROCESS_INFORMATION (null pointers, zero numbers).
        let mut si: StartupInfoW = unsafe { std::mem::zeroed() };
        si.cb = std::mem::size_of::<StartupInfoW>() as u32;
        si.flags = STARTF_USESTDHANDLES; // with the three handles null: no stdio at all
        let mut pi: ProcessInformation = unsafe { std::mem::zeroed() };
        // SAFETY: every buffer is NUL-terminated and lives across the call; the handles returned are closed.
        let ok = unsafe {
            CreateProcessW(
                std::ptr::null(),
                line.as_mut_ptr(),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                0,
                flags,
                block.as_mut_ptr() as *mut c_void,
                dir_w.as_ptr(),
                &mut si,
                &mut pi,
            )
        };
        if ok == 0 {
            return Err(std::io::Error::last_os_error());
        }
        unsafe {
            CloseHandle(pi.thread);
            CloseHandle(pi.process);
        }
        Ok(())
    }
}

/// Keep a socket of ours out of the programs we start. On Windows a socket accepted from a listener can be
/// inherited; a resident program that starts its successor would otherwise hand it the sessions'
/// connections, and the sessions would not see them end when it exits.
#[cfg(windows)]
pub fn no_inherit<S: std::os::windows::io::AsRawSocket>(s: &S) {
    // SAFETY: a socket handle of this process; failure only means it stays as it was.
    unsafe { win::SetHandleInformation(s.as_raw_socket() as *mut std::ffi::c_void, win::HANDLE_FLAG_INHERIT, 0) };
}

/// Elsewhere Rust opens every socket close-on-exec already.
#[cfg(unix)]
pub fn no_inherit<S>(_: &S) {}

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

/// Start `exe args` in `dir`, with `env` added to ours, so that it outlives this process and the session that
/// started it and holds nothing of ours: the resident program.
///
/// Nothing of ours means no handle at all, not only our stdio. Whoever started us may have handed us more
/// inheritable handles than our stdio (PowerShell gives a native command the pipe of its own caller, for
/// one); a resident program that inherits the write end of such a pipe keeps the agent's shell tool, which
/// waits for the end of that pipe, hanging for as long as the resident program runs.
pub fn spawn_detached(exe: &std::path::Path, args: &[&str], env: &[(&str, &std::ffi::OsStr)], dir: &std::path::Path) -> std::io::Result<()> {
    #[cfg(windows)]
    {
        // std's Command always lets the child inherit every inheritable handle; CreateProcessW with
        // bInheritHandles = FALSE is the only way to give it none.
        let base = win::DETACHED_PROCESS | win::CREATE_NEW_PROCESS_GROUP | win::CREATE_UNICODE_ENVIRONMENT;
        // Breaking away from the starter's job keeps the program alive when the product closes the job
        // of the session (where the job allows it; otherwise CreateProcess refuses and we go without).
        win::create_process(exe, args, env, dir, base | win::CREATE_BREAKAWAY_FROM_JOB)
            .or_else(|_| win::create_process(exe, args, env, dir, base))
    }
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        let mut cmd = Command::new(exe);
        cmd.args(args).current_dir(dir).stdin(std::process::Stdio::null()).stdout(std::process::Stdio::null()).stderr(std::process::Stdio::null());
        for (k, v) in env {
            cmd.env(k, v);
        }
        // SAFETY: setsid and fcntl are async-signal-safe. A new session leaves the terminal's hangup and job
        // control; every descriptor above stdio that we inherited open closes at exec.
        unsafe {
            cmd.pre_exec(|| {
                libc::setsid();
                for fd in 3..1024 {
                    libc::fcntl(fd, libc::F_SETFD, libc::FD_CLOEXEC);
                }
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
