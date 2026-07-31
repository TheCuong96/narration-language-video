use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use tauri::{AppHandle, Emitter, Manager, State};

#[derive(Default)]
pub struct EngineState {
    pub current_job_id: Option<String>,
    pub child_pid: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JobOptions {
    pub files: Vec<String>,
    pub output_dir: String,
    pub voice: String,
    pub model: String,
    pub audio_mode: String,
    pub mix_db: f64,
    pub review: bool,
    pub force: bool,
    pub prefer_gpu: bool,
    #[serde(default = "default_translate_provider")]
    pub translate_provider: String,
    #[serde(default = "default_tts_provider")]
    pub tts_provider: String,
    #[serde(default)]
    pub xtts_speaker_wav: String,
}

fn default_translate_provider() -> String {
    "deep-translator".into()
}

fn default_tts_provider() -> String {
    "edge-tts".into()
}

fn repo_engine_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("engine")
}

fn is_cargo_target_exe() -> bool {
    std::env::current_exe()
        .ok()
        .map(|p| {
            let s = p.to_string_lossy();
            // tauri/cargo local runs; installed apps live under Program Files / AppData.
            s.contains("target\\debug")
                || s.contains("target/debug")
                || s.contains("target\\release")
                || s.contains("target/release")
        })
        .unwrap_or(false)
}

pub fn engine_command() -> (PathBuf, Vec<String>) {
    if let Ok(p) = std::env::var("DUBVI_ENGINE") {
        return (PathBuf::from(p), vec![]);
    }
    // During `tauri dev` / cargo runs, prefer live Python so engine source edits apply
    // without rebuilding the stale PyInstaller sidecar next to dubvi.exe.
    let engine_pkg = repo_engine_dir().join("dubvi").join("__init__.py");
    if is_cargo_target_exe() && engine_pkg.is_file() {
        let py = which_python();
        return (py, vec!["-u".into(), "-m".into(), "dubvi".into()]);
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            let side = dir.join("DubVIEngine.exe");
            if side.is_file() {
                return (side, vec![]);
            }
        }
    }
    let py = which_python();
    (py, vec!["-u".into(), "-m".into(), "dubvi".into()])
}

fn which_python() -> PathBuf {
    let path = std::env::var_os("PATH").unwrap_or_default();
    for dir in std::env::split_paths(&path) {
        for name in ["python.exe", "python", "py.exe"] {
            let candidate = dir.join(name);
            if candidate.is_file() {
                return candidate;
            }
        }
    }
    PathBuf::from("python")
}

fn spawn_env() -> Vec<(String, String)> {
    let mut env: Vec<(String, String)> = std::env::vars().collect();
    env.push(("PYTHONUNBUFFERED".into(), "1".into()));
    env.push(("PYTHONUTF8".into(), "1".into()));
    env.push(("PYTHONIOENCODING".into(), "utf-8".into()));
    let engine = repo_engine_dir();
    if engine.is_dir() {
        let existing = std::env::var("PYTHONPATH").unwrap_or_default();
        let joined = if existing.is_empty() {
            engine.display().to_string()
        } else {
            format!("{};{}", engine.display(), existing)
        };
        env.push(("PYTHONPATH".into(), joined));
    }
    env
}

fn emit_line(app: &AppHandle, line: &str) {
    if let Ok(v) = serde_json::from_str::<Value>(line) {
        let _ = app.emit("engine-event", v);
    } else if !line.trim().is_empty() {
        let _ = app.emit(
            "engine-event",
            serde_json::json!({ "type": "log", "message": line }),
        );
    }
}

fn spawn_streaming(
    app: AppHandle,
    state: Arc<Mutex<EngineState>>,
    args: Vec<String>,
    job_id: String,
) -> Result<(), String> {
    let (bin, prefix) = engine_command();
    let mut env = spawn_env();
    // Point engine at bundled FFmpeg from Tauri resources when present
    if let Ok(rd) = app.path().resource_dir() {
        let candidates = [rd.join("bin"), rd.clone(), rd.join("resources").join("bin")];
        for c in candidates {
            if c.join("ffmpeg.exe").is_file() || c.join("ffmpeg").is_file() {
                env.push(("DUBVI_FFMPEG_DIR".into(), c.to_string_lossy().to_string()));
                break;
            }
        }
    }
    let mut cmd = Command::new(&bin);
    cmd.args(&prefix)
        .args(&args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::null())
        .env_clear()
        .envs(env)
        .current_dir(repo_engine_dir());

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    let mut child = cmd.spawn().map_err(|e| format!("Không chạy engine: {e}"))?;
    {
        let mut st = state.lock().map_err(|e| e.to_string())?;
        st.current_job_id = Some(job_id.clone());
        st.child_pid = Some(child.id());
    }

    let stdout = child.stdout.take().ok_or("no stdout")?;
    let stderr = child.stderr.take().ok_or("no stderr")?;
    let app_out = app.clone();
    thread::spawn(move || {
        for line in BufReader::new(stdout).lines().flatten() {
            emit_line(&app_out, &line);
        }
    });
    let app_err = app.clone();
    thread::spawn(move || {
        for line in BufReader::new(stderr).lines().flatten() {
            let _ = app_err.emit(
                "engine-event",
                serde_json::json!({"type":"log","level":"warn","message": line}),
            );
        }
    });

    let state2 = Arc::clone(&state);
    let app_done = app;
    let job_for_exit = job_id.clone();
    thread::spawn(move || {
        let status = child.wait();
        if let Ok(mut st) = state2.lock() {
            st.child_pid = None;
            if st.current_job_id.as_deref() == Some(job_for_exit.as_str()) {
                st.current_job_id = None;
            }
        }
        let code = status.ok().and_then(|s| s.code()).unwrap_or(-1);
        let _ = app_done.emit(
            "engine-event",
            serde_json::json!({"type":"log","message": format!("Engine kết thúc (code {code})")}),
        );
        // Always notify UI so busy state clears even if engine crashed before JSONL events.
        let _ = app_done.emit(
            "engine-event",
            serde_json::json!({
                "type": "engine_exited",
                "code": code,
                "job_id": job_for_exit,
                "message": format!("Engine kết thúc (code {code})")
            }),
        );
    });
    Ok(())
}

fn state_arc(state: &State<'_, Mutex<EngineState>>) -> Result<Arc<Mutex<EngineState>>, String> {
    // We cannot extract Arc from State; clone fields into a shared wrapper via once_cell pattern.
    // Instead: store process handles only in managed mutex and pass a clone of pid updates.
    // For streaming threads we use a dedicated Arc kept in once_cell.
    use std::sync::OnceLock;
    static SHARED: OnceLock<Arc<Mutex<EngineState>>> = OnceLock::new();
    let shared = SHARED.get_or_init(|| Arc::new(Mutex::new(EngineState::default())));
    if let Ok(src) = state.lock() {
        if let Ok(mut dst) = shared.lock() {
            dst.current_job_id = src.current_job_id.clone();
            dst.child_pid = src.child_pid;
        }
    }
    Ok(Arc::clone(shared))
}

pub async fn start_job(
    app: AppHandle,
    state: State<'_, Mutex<EngineState>>,
    options: JobOptions,
) -> Result<String, String> {
    let job_id = uuid::Uuid::new_v4().simple().to_string()[..12].to_string();
    let mut args = vec![
        "run".into(),
        "-o".into(),
        options.output_dir,
        "--job-id".into(),
        job_id.clone(),
        "--voice".into(),
        options.voice,
        "--model".into(),
        options.model,
        "--audio-mode".into(),
        options.audio_mode,
        "--mix-db".into(),
        options.mix_db.to_string(),
    ];
    if !options.files.is_empty() {
        args.push("--files".into());
        args.extend(options.files);
    }
    if options.review {
        args.push("--review".into());
    }
    if options.force {
        args.push("--force".into());
    }
    if options.prefer_gpu {
        args.push("--gpu".into());
    } else {
        args.push("--cpu".into());
    }
    if !options.translate_provider.is_empty() {
        args.push("--translate-provider".into());
        args.push(options.translate_provider);
    }
    if !options.tts_provider.is_empty() {
        args.push("--tts-provider".into());
        args.push(options.tts_provider);
    }
    if !options.xtts_speaker_wav.is_empty() {
        args.push("--xtts-speaker".into());
        args.push(options.xtts_speaker_wav);
    }

    {
        let mut st = state.lock().map_err(|e| e.to_string())?;
        st.current_job_id = Some(job_id.clone());
    }
    let shared = state_arc(&state)?;
    spawn_streaming(app, shared.clone(), args, job_id.clone())?;
    if let Ok(g) = shared.lock() {
        if let Ok(mut st) = state.lock() {
            st.child_pid = g.child_pid;
        }
    }
    Ok(job_id)
}

fn write_cancel_flag(job_id: &str) -> Result<(), String> {
    let base = if cfg!(windows) {
        std::env::var("LOCALAPPDATA").unwrap_or_else(|_| {
            format!(
                "{}\\AppData\\Local",
                std::env::var("USERPROFILE").unwrap_or_default()
            )
        })
    } else {
        format!(
            "{}/.local/share",
            std::env::var("HOME").unwrap_or_else(|_| ".".into())
        )
    };
    let dir = PathBuf::from(base).join("DubVI").join("jobs").join(job_id);
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    std::fs::write(dir.join("cancel.flag"), "1").map_err(|e| e.to_string())?;
    Ok(())
}

fn kill_pid(pid: u32) {
    #[cfg(windows)]
    {
        let _ = Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
    #[cfg(not(windows))]
    {
        let _ = Command::new("kill")
            .args(["-TERM", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
}

pub async fn cancel_job(state: State<'_, Mutex<EngineState>>, job_id: String) -> Result<(), String> {
    // Soft-fail: engine CLI may be broken; still write flag + kill process.
    let _ = run_engine_capture(&["cancel", &job_id]);
    let _ = write_cancel_flag(&job_id);

    let pid = state.lock().ok().and_then(|st| st.child_pid);
    if let Some(pid) = pid {
        kill_pid(pid);
    }
    // Also kill via shared Arc used by streaming threads
    if let Ok(shared) = state_arc(&state) {
        if let Ok(mut st) = shared.lock() {
            if let Some(pid) = st.child_pid.take() {
                kill_pid(pid);
            }
            if st.current_job_id.as_deref() == Some(job_id.as_str()) {
                st.current_job_id = None;
            }
        }
    }
    if let Ok(mut st) = state.lock() {
        st.child_pid = None;
        if st.current_job_id.as_deref() == Some(job_id.as_str()) {
            st.current_job_id = None;
        }
    }
    Ok(())
}

pub async fn retry_failed(
    app: AppHandle,
    state: State<'_, Mutex<EngineState>>,
    job_id: String,
    stems: Option<Vec<String>>,
) -> Result<(), String> {
    let mut args = vec!["retry".into(), "--job-id".into(), job_id.clone()];
    if let Some(s) = stems {
        if !s.is_empty() {
            args.push("--stem".into());
            args.extend(s);
        }
    }
    {
        let mut st = state.lock().map_err(|e| e.to_string())?;
        st.current_job_id = Some(job_id.clone());
    }
    let shared = state_arc(&state)?;
    spawn_streaming(app, shared, args, job_id)
}

pub async fn resume_job(
    app: AppHandle,
    state: State<'_, Mutex<EngineState>>,
    job_id: String,
    stems: Option<Vec<String>>,
) -> Result<(), String> {
    let mut args = vec!["resume".into(), "--job-id".into(), job_id.clone()];
    if let Some(s) = stems {
        if !s.is_empty() {
            args.push("--stem".into());
            args.extend(s);
        }
    }
    {
        let mut st = state.lock().map_err(|e| e.to_string())?;
        st.current_job_id = Some(job_id.clone());
    }
    let shared = state_arc(&state)?;
    spawn_streaming(app, shared, args, job_id)
}

pub async fn continue_after_review(
    app: AppHandle,
    state: State<'_, Mutex<EngineState>>,
    job_id: String,
    stem: String,
) -> Result<(), String> {
    let args = vec![
        "continue".into(),
        "--job-id".into(),
        job_id.clone(),
        "--stem".into(),
        stem,
    ];
    {
        let mut st = state.lock().map_err(|e| e.to_string())?;
        st.current_job_id = Some(job_id.clone());
    }
    let shared = state_arc(&state)?;
    spawn_streaming(app, shared, args, job_id)
}

pub async fn review_set(job_id: String, stem: String, segments: Value) -> Result<(), String> {
    let dir = std::env::temp_dir().join(format!("dubvi-review-{job_id}-{stem}.json"));
    {
        let mut f = std::fs::File::create(&dir).map_err(|e| e.to_string())?;
        f.write_all(segments.to_string().as_bytes())
            .map_err(|e| e.to_string())?;
    }
    let path = dir.to_string_lossy().to_string();
    let _ = run_engine_capture(&[
        "review-set",
        "--job-id",
        &job_id,
        "--stem",
        &stem,
        "--file",
        &path,
    ])?;
    let _ = std::fs::remove_file(dir);
    Ok(())
}

pub async fn run_engine_json(args: &[&str]) -> Result<Value, String> {
    let out = run_engine_capture(args)?;
    serde_json::from_str(&out).map_err(|e| format!("JSON parse: {e}; out={out}"))
}

pub async fn download_model(
    app: AppHandle,
    state: State<'_, Mutex<EngineState>>,
    model_id: String,
) -> Result<(), String> {
    let args = vec!["models-download".into(), model_id.clone()];
    {
        let mut st = state.lock().map_err(|e| e.to_string())?;
        st.current_job_id = Some(format!("model-{model_id}"));
    }
    let shared = state_arc(&state)?;
    spawn_streaming(app, shared, args, format!("model-{model_id}"))
}

pub async fn download_url(
    app: AppHandle,
    state: State<'_, Mutex<EngineState>>,
    url: String,
    download_dir: Option<String>,
) -> Result<String, String> {
    let job_id = format!("url-{}", &uuid::Uuid::new_v4().simple().to_string()[..12]);
    let mut args = vec!["download-url".into(), url];
    if let Some(dir) = download_dir {
        let trimmed = dir.trim();
        if !trimmed.is_empty() {
            args.push("--output-dir".into());
            args.push(trimmed.to_string());
        }
    }
    {
        let mut st = state.lock().map_err(|e| e.to_string())?;
        st.current_job_id = Some(job_id.clone());
    }
    let shared = state_arc(&state)?;
    spawn_streaming(app, shared, args, job_id.clone())?;
    Ok(job_id)
}

pub async fn save_settings(settings: Value) -> Result<(), String> {
    let dir = std::env::temp_dir().join(format!("dubvi-settings-{}.json", uuid::Uuid::new_v4()));
    {
        let mut f = std::fs::File::create(&dir).map_err(|e| e.to_string())?;
        f.write_all(settings.to_string().as_bytes())
            .map_err(|e| e.to_string())?;
    }
    let path = dir.to_string_lossy().to_string();
    let _ = run_engine_capture(&["settings-set", "--file", &path])?;
    let _ = std::fs::remove_file(dir);
    Ok(())
}

pub fn run_engine_capture(args: &[&str]) -> Result<String, String> {
    let (bin, prefix) = engine_command();
    let mut cmd = Command::new(&bin);
    cmd.args(&prefix)
        .args(args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env_clear()
        .envs(spawn_env())
        .current_dir(repo_engine_dir());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let output = cmd.output().map_err(|e| e.to_string())?;
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("engine failed: {stderr} {stdout}"));
    }
    Ok(stdout)
}
