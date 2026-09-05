// the Rust baseline: the same three routes on axum.
//
// it does the same work the Laurel and Go programs do: route, decode a typed
// path parameter, parse a urlencoded form, set the same five security headers,
// and write a small JSON body.

use std::net::SocketAddr;

use axum::{
    extract::{Form, Path},
    http::{header, HeaderValue, StatusCode},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::{get, post},
    Router,
};
use axum::extract::Request;
use serde::Deserialize;

const CSP: &str =
    "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'";
const REFERRER_POLICY: &str = "strict-origin-when-cross-origin";
const PERMISSIONS_POLICY: &str =
    "camera=(), microphone=(), geolocation=(), payment=(), usb=()";

// the same headers Laurel's security policy applies, set by hand
async fn secure(request: Request, next: Next) -> Response {
    let mut response = next.run(request).await;
    let headers = response.headers_mut();
    headers.insert("content-security-policy", HeaderValue::from_static(CSP));
    headers.insert("referrer-policy", HeaderValue::from_static(REFERRER_POLICY));
    headers.insert(
        "permissions-policy",
        HeaderValue::from_static(PERMISSIONS_POLICY),
    );
    headers.insert("x-frame-options", HeaderValue::from_static("DENY"));
    headers.insert("x-content-type-options", HeaderValue::from_static("nosniff"));
    response
}

fn json_body(body: String) -> Response {
    (
        StatusCode::OK,
        [(
            header::CONTENT_TYPE,
            HeaderValue::from_static("application/json; charset=utf-8"),
        )],
        body,
    )
        .into_response()
}

async fn handle_json() -> Response {
    json_body(String::from(r#"{"message":"hello"}"#))
}

// the u64 in the path type is the whole parameter decoder; a value that does
// not parse never reaches this function
async fn handle_echo(Path(id): Path<u64>) -> Response {
    json_body(format!(r#"{{"id":{}}}"#, id))
}

#[derive(Deserialize)]
struct Submission {
    name: String,
}

async fn handle_submit(form: Option<Form<Submission>>) -> Response {
    match form {
        Some(Form(submission)) if !submission.name.is_empty() => {
            json_body(format!(r#"{{"name":"{}"}}"#, escape_json(&submission.name)))
        }
        Some(_) => (StatusCode::BAD_REQUEST, "name is required").into_response(),
        None => (StatusCode::BAD_REQUEST, "malformed form").into_response(),
    }
}

fn escape_json(value: &str) -> String {
    let mut out = String::with_capacity(value.len() + 8);
    for c in value.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out
}

fn app() -> Router {
    Router::new()
        .route("/json", get(handle_json))
        .route("/echo/:id", get(handle_echo))
        .route("/submit", post(handle_submit))
        .layer(middleware::from_fn(secure))
}

fn address() -> SocketAddr {
    std::env::var("BENCH_ADDR")
        .unwrap_or_else(|_| String::from("127.0.0.1:8083"))
        .parse()
        .expect("BENCH_ADDR must be host:port")
}

async fn serve() {
    let addr = address();
    let listener = tokio::net::TcpListener::bind(addr).await.expect("bind");
    eprintln!("axum-bench: listening on {}", addr);
    axum::serve(listener, app()).await.expect("serve");
}

// BENCH_THREADS=1 selects the single-threaded runtime, so the server can be
// compared against a single-threaded one on equal terms
fn main() {
    let single = std::env::var("BENCH_THREADS")
        .map(|value| value == "1")
        .unwrap_or(false);
    if single {
        tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("runtime")
            .block_on(serve());
    } else {
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .expect("runtime")
            .block_on(serve());
    }
}
