//! `asterism`: the program an agent's computer runs to take part in an Asterism project.
//!
//! One executable with four commands:
//! - `join <link>`: redeems an agent invitation link, stores this computer's credential, starts the resident
//!   program and adds `asterism mcp` to the product (Claude Code or Codex) that ran it.
//! - `daemon`: the resident program, one per state folder. It holds this computer's connection to every
//!   joined project and puts each delivery in front of the right local session.
//! - `mcp`: started by the product in every session; the agent tools on stdio (MCP).
//! - `status`: what is running and connected, for a person.
//! - `allow`: lets Claude Code or Codex run Asterism's tools without asking again (`join` already does).
//! - `uninstall [--forget]`: takes out what `join` put in.
//!
//! Everything lives in the state folder (`ASTERISM_HOME`, default `~/.asterism`); see `state.rs`.

mod allow;
mod daemon;
mod http;
mod join;
mod local;
mod mcp;
mod push;
mod state;
mod status;
mod sys;
mod uninstall;
mod update;

use std::panic;

pub const VERSION: &str = env!("CARGO_PKG_VERSION");

const USAGE: &str = "Usage:
  asterism join <invitation link> [--name NAME] [--client claude|codex|none]
  asterism status
  asterism allow [--client claude|codex]   (let the product run Asterism's tools without asking)
  asterism uninstall [--forget]            (take Asterism out of this computer; --forget: its credentials too)
  asterism mcp      (started by Claude Code or Codex)
  asterism daemon   (started by the commands above when it is not running)";

fn main() {
    // A bug must still end in one readable sentence and an exit status, not a Rust backtrace (which also
    // reads as a crash to an agent that runs `join`).
    panic::set_hook(Box::new(|info| {
        let what = info
            .payload()
            .downcast_ref::<&str>()
            .map(|s| s.to_string())
            .or_else(|| info.payload().downcast_ref::<String>().cloned())
            .unwrap_or_else(|| "unknown".into());
        let at = info.location().map(|l| format!(" at {}:{}", l.file(), l.line())).unwrap_or_default();
        let line = format!("asterism {VERSION}: internal error ({what}{at}). Please report it.");
        daemon::log_panic(&line);
        eprintln!("{line}");
    }));
    let code = panic::catch_unwind(run).unwrap_or(70);
    std::process::exit(code);
}

fn run() -> i32 {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let home = state::home();
    match args.first().map(String::as_str) {
        Some("join") => join::run(&home, &args[1..]),
        Some("daemon") => daemon::run(home),
        Some("mcp") => mcp::run(home),
        Some("status") => status::run(&home),
        Some("allow") => allow::run(&args[1..]),
        Some("uninstall") => uninstall::run(&home, &args[1..]),
        Some("--version") | Some("version") => {
            println!("asterism {VERSION}");
            0
        }
        Some("-h") | Some("--help") | Some("help") => {
            println!("{USAGE}");
            0
        }
        _ => {
            eprintln!("{USAGE}");
            2
        }
    }
}
