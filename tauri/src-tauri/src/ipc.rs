use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use serde_json::Value;

// ---------------------------------------------------------------------------
// JSON-RPC types
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub id: u64,
    pub method: String,
    pub params: Value,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    pub id: u64,
    pub result: Option<Value>,
    pub error: Option<JsonRpcError>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct JsonRpcError {
    pub code: i64,
    pub message: String,
    pub data: Option<Value>,
}

// ---------------------------------------------------------------------------
// Sidecar — wraps the child process and manages stdin/stdout I/O
// ---------------------------------------------------------------------------

pub struct Sidecar {
    _child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
    next_id: u64,
}

impl Sidecar {
    /// Spawn the sidecar binary at `binary_path`.
    pub fn spawn(binary_path: &str) -> Result<Self, String> {
        let mut child = Command::new(binary_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit()) // let sidecar stderr flow to console for debugging
            .spawn()
            .map_err(|e| format!("Failed to spawn sidecar '{}': {}", binary_path, e))?;

        let stdin = child
            .stdin
            .take()
            .ok_or("Failed to capture sidecar stdin")?;
        let stdout = child
            .stdout
            .take()
            .ok_or("Failed to capture sidecar stdout")?;

        Ok(Self {
            _child: child,
            stdin,
            stdout: BufReader::new(stdout),
            next_id: 1,
        })
    }

    /// Send a JSON-RPC request to the sidecar and return the response.
    ///
    /// Each call is synchronous (blocking the calling thread). The frontend
    /// invokes this via a Tauri `async` command so it won't block the UI.
    pub fn call(&mut self, method: &str, params: Value) -> Result<Value, String> {
        let id = self.next_id;
        self.next_id += 1;

        let request = JsonRpcRequest {
            jsonrpc: "2.0".to_string(),
            id,
            method: method.to_string(),
            params,
        };

        // --- write request line to sidecar stdin ---
        let mut line =
            serde_json::to_string(&request).map_err(|e| format!("Serialize error: {}", e))?;
        line.push('\n');

        self.stdin
            .write_all(line.as_bytes())
            .map_err(|e| format!("Stdin write error: {}", e))?;

        self.stdin
            .flush()
            .map_err(|e| format!("Stdin flush error: {}", e))?;

        // --- read response line from sidecar stdout ---
        let mut response_line = String::new();
        self.stdout
            .read_line(&mut response_line)
            .map_err(|e| format!("Stdout read error: {}", e))?;

        if response_line.is_empty() {
            return Err("Sidecar closed stdout unexpectedly".to_string());
        }

        let response: JsonRpcResponse = serde_json::from_str(response_line.trim())
            .map_err(|e| format!("Deserialize error: {} (raw: {})", e, response_line.trim()))?;

        // Validate the response ID matches the request ID
        if response.id != id {
            return Err(format!(
                "Response ID mismatch: expected {}, got {}",
                id, response.id
            ));
        }

        // Return result or propagate error
        if let Some(error) = response.error {
            return Err(format!(
                "Sidecar error [{}]: {}",
                error.code, error.message
            ));
        }

        response
            .result
            .ok_or_else(|| "Sidecar returned neither result nor error".to_string())
    }
}

// ---------------------------------------------------------------------------
// Tauri state wrapper
// ---------------------------------------------------------------------------

/// Wraps an optional `Sidecar` in a `Mutex` so Tauri can share it safely
/// across multiple command invocations. `None` when the sidecar binary has
/// not been built yet (before Task 2 is complete).
pub struct SidecarState(pub Mutex<Option<Sidecar>>);
