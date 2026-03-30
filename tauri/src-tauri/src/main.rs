// Prevents an additional console window on Windows in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod ipc;

use ipc::{Sidecar, SidecarState};
use serde_json::Value;
use std::sync::Mutex;
use tauri::Manager;

// ---------------------------------------------------------------------------
// Tauri commands
// ---------------------------------------------------------------------------

/// Bridge command exposed to the frontend.
///
/// The frontend calls `invoke("call_sidecar", { method, params })` and
/// receives either a JSON `Value` result or an error string.
///
/// Returns an error if the sidecar is not running (e.g. binary missing —
/// expected during Task 1 before the Python sidecar is built in Task 2).
#[tauri::command]
async fn call_sidecar(
    state: tauri::State<'_, SidecarState>,
    method: String,
    params: Value,
) -> Result<Value, String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|e| format!("Sidecar mutex poisoned: {}", e))?;

    match guard.as_mut() {
        Some(sidecar) => sidecar.call(&method, params),
        None => Err("Sidecar is not running. Please ensure the sidecar binary exists.".to_string()),
    }
}

// ---------------------------------------------------------------------------
// App entry point
// ---------------------------------------------------------------------------

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .setup(|app| {
            // Resolve the sidecar binary path from the app's resource directory.
            // During development the binary won't exist yet (it's Task 2),
            // but we want the path resolution to be wired up correctly.
            let resource_dir = app
                .path()
                .resource_dir()
                .map_err(|e| format!("Could not resolve resource dir: {}", e))?;

            // The binary is placed at <resourceDir>/binaries/leadflow-sidecar
            // (or leadflow-sidecar.exe on Windows).
            let binary_name = if cfg!(target_os = "windows") {
                "leadflow-sidecar.exe"
            } else {
                "leadflow-sidecar"
            };

            let sidecar_path = resource_dir.join("binaries").join(binary_name);

            let sidecar_path_str = sidecar_path
                .to_str()
                .ok_or("Sidecar path contains non-UTF-8 characters")?
                .to_string();

            // Attempt to spawn the sidecar. If it doesn't exist yet (Task 2
            // not done), store None so the app still starts.
            let maybe_sidecar = match Sidecar::spawn(&sidecar_path_str) {
                Ok(sidecar) => {
                    println!("[LeadFlow] Sidecar spawned at {}", sidecar_path_str);
                    Some(sidecar)
                }
                Err(e) => {
                    eprintln!("[LeadFlow] WARNING: Could not spawn sidecar: {}", e);
                    eprintln!("[LeadFlow] The app will run in degraded mode (no backend).");
                    None
                }
            };

            // Always manage the state — even when sidecar is None — so that
            // the `call_sidecar` command can return a graceful error instead
            // of panicking.
            app.manage(SidecarState(Mutex::new(maybe_sidecar)));

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![call_sidecar])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
