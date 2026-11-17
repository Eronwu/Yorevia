#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use serde_json::{json, Value};
use std::{collections::HashSet, io::{BufRead, BufReader, Write}, path::PathBuf,
    process::{Child, ChildStdin, ChildStdout, Command, Stdio}, sync::Mutex};
use tauri::Manager;
use tauri_plugin_dialog::DialogExt;

struct Engine { child: Child, input: ChildStdin, output: BufReader<ChildStdout>, sequence: u64 }
impl Engine {
    fn spawn() -> Result<Self, String> {
        let mut command;
        #[cfg(debug_assertions)]
        {
            let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().ok_or("Invalid project root")?.to_path_buf();
            let venv = if cfg!(windows) { root.join(".venv/Scripts/python.exe") } else { root.join(".venv/bin/python") };
            let python = std::env::var_os("YOREVIA_PYTHON").map(PathBuf::from).unwrap_or_else(|| {
                if venv.exists() { venv } else { PathBuf::from(if cfg!(windows) {"python"} else {"python3"}) }
            });
            command = Command::new(python);
            command.arg("-u").arg(root.join("engine/worker.py"));
        }
        #[cfg(not(debug_assertions))]
        {
            let executable = std::env::current_exe().map_err(|e|e.to_string())?;
            let worker = executable.with_file_name(if cfg!(windows) {"yorevia-engine.exe"} else {"yorevia-engine"});
            if !worker.is_file() { return Err("The bundled local engine is missing. Reinstall the complete Yorevia package.".into()); }
            command = Command::new(worker);
        }
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let mut child = command.env("PYTHONUTF8","1").stdin(Stdio::piped()).stdout(Stdio::piped())
            .stderr(Stdio::null()).spawn().map_err(|e|format!("Cannot start the local engine: {e}"))?;
        let input = child.stdin.take().ok_or("Engine stdin unavailable")?;
        let output = BufReader::new(child.stdout.take().ok_or("Engine stdout unavailable")?);
        Ok(Self { child, input, output, sequence: 0 })
    }
    fn call(&mut self, method: &str, params: Value) -> Result<Value, String> {
        self.sequence += 1;
        let request = json!({"id":self.sequence,"method":method,"params":params});
        let line = serde_json::to_vec(&request).map_err(|e|e.to_string())?;
        if line.len() > 2_000_000 { return Err("Request too large".into()); }
        self.input.write_all(&line).and_then(|_|self.input.write_all(b"\n"))
            .and_then(|_|self.input.flush()).map_err(|e|format!("Local engine disconnected: {e}"))?;
        let mut response = String::new();
        if self.output.read_line(&mut response).map_err(|e|e.to_string())? == 0 {
            return Err("Local engine stopped. Reopen the application; committed records are preserved.".into());
        }
        let value: Value = serde_json::from_str(&response).map_err(|_|"Local engine returned an invalid response")?;
        if value["id"].as_u64() != Some(self.sequence) { return Err("Local engine response ID mismatch".into()); }
        if let Some(error) = value.get("error") {
            return Err(error["message"].as_str().unwrap_or("Local engine error").to_string());
        }
        Ok(value["result"].clone())
    }
}
impl Drop for Engine { fn drop(&mut self) { let _ = self.child.kill(); let _ = self.child.wait(); } }
#[derive(Default)]
struct AppState { engine: Mutex<Option<Engine>>, granted_roots: Mutex<HashSet<PathBuf>> }

fn allowed_method(method: &str) -> bool {
    matches!(method, "status"|"vault.open"|"summary"|"source.add"|"scan.start"|"faces.start"|"job.status"|"job.cancel"|
        "timeline"|"people"|"graph"|"image"|"asset.detail"|"asset.date"|"person.rename"|"person.merge"|
        "person.faces"|"face.split"|"relationship.add"|"story.save"|"stories"|"export"|"biometrics.erase"|"baidu.auth.start"|"baidu.auth.poll"|"baidu.auth.cancel"|"baidu.status"|"baidu.connect"|"baidu.disconnect"|"baidu.list"|"baidu.import")
}
fn engine_call(app: &tauri::AppHandle, method: &str, params: Value) -> Result<Value, String> {
    let state = app.state::<AppState>();
    let mut guard = state.engine.lock().map_err(|_|"Local engine lock failed")?;
    if guard.is_none() { *guard = Some(Engine::spawn()?); }
    guard.as_mut().ok_or("Local engine unavailable")?.call(method,params)
}
#[tauri::command]
async fn choose_folder(app: tauri::AppHandle, title: String) -> Result<Option<String>, String> {
    tauri::async_runtime::spawn_blocking(move || -> Result<Option<String>, String> {
        let selected = app.dialog().file().set_title(title).blocking_pick_folder();
        match selected {
            None => Ok(None),
            Some(file) => {
                let path = file.into_path().map_err(|e|e.to_string())?.canonicalize().map_err(|e|e.to_string())?;
                app.state::<AppState>().granted_roots.lock().map_err(|_|"Folder permission lock failed")?.insert(path.clone());
                Ok(Some(path.to_string_lossy().into_owned()))
            }
        }
    }).await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn rpc(app: tauri::AppHandle, method: String, params: Value) -> Result<Value, String> {
    if !allowed_method(&method) { return Err("Operation is not permitted".into()); }
    if !params.is_object() { return Err("Parameters must be an object".into()); }
    if method == "vault.open" || method == "source.add" || method == "baidu.import" {
        let field = if method == "baidu.import" { "destination" } else { "path" };
        let raw = params[field].as_str().ok_or("Missing folder path")?;
        let selected = PathBuf::from(raw).canonicalize().map_err(|e|e.to_string())?;
        if !app.state::<AppState>().granted_roots.lock().map_err(|_|"Permission lock failed")?.contains(&selected) {
            return Err("Please choose this directory using the native folder dialog first.".into());
        }
    }
    tauri::async_runtime::spawn_blocking(move || engine_call(&app,&method,params)).await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn reveal_asset(app: tauri::AppHandle, asset_id: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || -> Result<(), String> {
        let value = engine_call(&app,"asset.path",json!({"asset_id":asset_id}))?;
        let path = PathBuf::from(value["path"].as_str().ok_or("Missing asset path")?);
        if !path.is_file() { return Err("Original media is offline".into()); }
        #[cfg(target_os="macos")]
        { Command::new("open").arg("-R").arg(&path).spawn().map_err(|e|e.to_string())?; }
        #[cfg(target_os="windows")]
        { Command::new("explorer.exe").arg(format!("/select,{}",path.display())).spawn().map_err(|e|e.to_string())?; }
        #[cfg(not(any(target_os="macos",target_os="windows")))]
        { Command::new("xdg-open").arg(path.parent().ok_or("Missing parent")?).spawn().map_err(|e|e.to_string())?; }
        Ok(())
    }).await.map_err(|e|e.to_string())?
}
fn main() {
    let app = tauri::Builder::default().plugin(tauri_plugin_dialog::init()).manage(AppState::default())
        .invoke_handler(tauri::generate_handler![rpc,choose_folder,reveal_asset])
        .build(tauri::generate_context!()).expect("Unable to initialize Yorevia desktop");
    app.run(|app,event| { if let tauri::RunEvent::Exit = event {
        let state = app.state::<AppState>();
        if let Ok(mut engine) = state.engine.lock() { engine.take(); };
    }});
}
#[cfg(test)] mod tests {
    use super::*;
    #[test] fn dangerous_commands_are_not_exposed() { assert!(!allowed_method("shell"));assert!(!allowed_method("asset.path"));assert!(allowed_method("timeline")); }
}
