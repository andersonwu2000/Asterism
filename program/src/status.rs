//! `asterism status`: what runs and what is connected, for a person. It does not start anything.

use crate::local;
use crate::state;
use serde_json::json;
use std::path::Path;

pub fn run(home: &Path) -> i32 {
    let code = connection(home);
    // Read only: whether each product has the tools, and whether it runs them without asking.
    for p in ["claude", "codex"] {
        let name = crate::allow::display(p);
        if !crate::allow::added(p) {
            println!("{name}: Asterism's tools are not added.");
        } else if crate::allow::allowed(p) {
            println!("{name}: Asterism's tools are added and run without asking.");
        } else {
            println!("{name}: Asterism's tools are added and ask for approval (turn that off with `asterism allow`).");
        }
    }
    code
}

fn connection(home: &Path) -> i32 {
    let projects = state::load_projects(home);
    let got = local::running(home).and_then(|info| local::request(&info, json!({"op": "status"})).ok());
    let Some(st) = got else {
        println!("The resident program is not running (it starts with the next agent session, or with `asterism join`).");
        if projects.is_empty() {
            println!("This computer has not joined any project.");
        }
        for p in &projects {
            println!("Project {} ({}), as {}: not connected.", p.slug, p.url, p.person);
        }
        return 0;
    };
    println!(
        "The resident program runs (process {}, version {}).",
        st["pid"].as_u64().unwrap_or(0),
        st["version"].as_str().unwrap_or("?")
    );
    let shown = st["projects"].as_array().cloned().unwrap_or_default();
    if shown.is_empty() {
        println!("This computer has not joined any project.");
    }
    for p in &shown {
        println!(
            "Project {} ({}), as {}: {}.",
            p["slug"].as_str().unwrap_or("?"),
            p["url"].as_str().unwrap_or("?"),
            p["person"].as_str().unwrap_or("?"),
            p["state"].as_str().unwrap_or("?")
        );
    }
    let sessions = st["sessions"].as_array().cloned().unwrap_or_default();
    if sessions.is_empty() {
        println!("No session can be woken right now.");
    } else {
        println!("Sessions it can wake:");
        for s in &sessions {
            let agent = s["agent"].as_str().map(|a| format!("agent {a}")).unwrap_or_else(|| "no agent known yet".into());
            println!(
                "  {} {} ({agent})",
                s["product"].as_str().unwrap_or("?"),
                s["session"].as_str().unwrap_or("?")
            );
        }
    }
    0
}
