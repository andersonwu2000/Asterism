//! Talking to the Asterism server. Every answer is a JSON object; a refusal is `{error, message}` where
//! `message` is written for the agent, so it is passed on as it is.

use serde_json::{Map, Value};
use std::time::Duration;

#[derive(Debug)]
pub enum Fail {
    /// The server answered with an error.
    Refused { status: u16, message: String },
    /// No answer from the server (down, restarting, a proxy saying 502/503/504, a timeout).
    Unreachable(String),
}

impl Fail {
    pub fn is_revoked(&self) -> bool {
        matches!(self, Fail::Refused { status: 401, .. })
    }
}

pub type Agent = ureq::Agent;

pub fn agent() -> Agent {
    let cfg = ureq::Agent::config_builder()
        // Refusals come back as answers, with the server's sentence in them.
        .http_status_as_error(false)
        // A credential must never follow a redirect anywhere; the server does not redirect its API.
        .max_redirects(0)
        .user_agent(format!("asterism/{}", crate::VERSION))
        .timeout_connect(Some(Duration::from_secs(10)))
        .tls_config(tls());
    cfg.build().new_agent()
}

#[cfg(any(windows, target_os = "macos"))]
fn tls() -> ureq::tls::TlsConfig {
    // SChannel or Security.framework, with the system's trusted roots.
    ureq::tls::TlsConfig::builder()
        .provider(ureq::tls::TlsProvider::NativeTls)
        .root_certs(ureq::tls::RootCerts::PlatformVerifier)
        .build()
}

#[cfg(not(any(windows, target_os = "macos")))]
fn tls() -> ureq::tls::TlsConfig {
    // rustls with ring and the bundled Mozilla roots: no dependency on the system's OpenSSL.
    ureq::tls::TlsConfig::builder()
        .provider(ureq::tls::TlsProvider::Rustls)
        .root_certs(ureq::tls::RootCerts::WebPki)
        .build()
}

/// One request. `body` None sends no body (GET); `headers` and `query` are added as given.
pub fn call(
    agent: &Agent,
    method: &str,
    url: &str,
    body: Option<&Value>,
    headers: &[(&str, &str)],
    query: &[(String, String)],
    timeout: Duration,
) -> Result<Value, Fail> {
    let result = if method == "GET" {
        let mut req = agent.get(url).header("Accept", "application/json");
        for (k, v) in headers {
            req = req.header(*k, *v);
        }
        for (k, v) in query {
            req = req.query(k, v);
        }
        req.config().timeout_global(Some(timeout)).build().call()
    } else {
        let mut req = agent.post(url).header("Accept", "application/json");
        for (k, v) in headers {
            req = req.header(*k, *v);
        }
        for (k, v) in query {
            req = req.query(k, v);
        }
        let text = body.map(Value::to_string).unwrap_or_else(|| "{}".into());
        req.content_type("application/json").config().timeout_global(Some(timeout)).build().send(text.as_bytes())
    };
    let mut res = result.map_err(|e| Fail::Unreachable(describe(&e)))?;
    let status = res.status().as_u16();
    let raw = res.body_mut().read_to_string().map_err(|e| Fail::Unreachable(describe(&e)))?;
    let got: Value = if raw.trim().is_empty() { Value::Object(Map::new()) } else { serde_json::from_str(&raw).unwrap_or(Value::Null) };
    if (200..300).contains(&status) {
        return match got {
            Value::Object(_) => Ok(got),
            _ => Err(Fail::Unreachable(format!("the server answered {status} with something that is not JSON"))),
        };
    }
    // A proxy in front of a server that is down answers 502-504 without the server's error object.
    if matches!(status, 502..=504) && got["error"].as_str().is_none() {
        return Err(Fail::Unreachable(format!("the server answered {status}")));
    }
    Err(Fail::Refused {
        status,
        message: got["message"].as_str().map(String::from).unwrap_or_else(|| format!("HTTP {status}")),
    })
}

/// Fetch a file into `dest`, at most `max` bytes (one more is read, so that a longer file shows).
/// Returns the number of bytes written.
pub fn download(agent: &Agent, url: &str, dest: &std::path::Path, max: u64, timeout: Duration) -> Result<u64, Fail> {
    let mut res = agent.get(url).config().timeout_global(Some(timeout)).build().call().map_err(|e| Fail::Unreachable(describe(&e)))?;
    let status = res.status().as_u16();
    if status != 200 {
        return Err(Fail::Refused { status, message: format!("HTTP {status}") });
    }
    let mut out = std::fs::File::create(dest).map_err(|e| Fail::Unreachable(e.to_string()))?;
    let mut body = std::io::Read::take(res.body_mut().as_reader(), max + 1);
    std::io::copy(&mut body, &mut out).map_err(|e| Fail::Unreachable(e.to_string()))
}

/// A short reason without the address (which may carry an invitation code).
fn describe(e: &ureq::Error) -> String {
    match e {
        ureq::Error::Io(io) => io.to_string(),
        ureq::Error::Timeout(_) => "no answer in time".into(),
        ureq::Error::HostNotFound => "host not found".into(),
        ureq::Error::ConnectionFailed => "connection failed".into(),
        other => other.to_string(),
    }
}
