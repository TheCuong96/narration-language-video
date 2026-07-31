mod engine;

use engine::{EngineState, JobOptions};
use serde_json::Value;
use std::sync::Mutex;
use tauri::{AppHandle, State};

#[tauri::command]
async fn pick_videos(app: AppHandle) -> Result<Vec<String>, String> {
    use tauri_plugin_dialog::DialogExt;
    let files = app
        .dialog()
        .file()
        .add_filter("Video", &["mp4", "mkv", "mov", "avi", "webm"])
        .set_title("Chọn video")
        .blocking_pick_files();
    let mut out = Vec::new();
    if let Some(list) = files {
        for f in list {
            if let Ok(path) = f.into_path() {
                out.push(path.to_string_lossy().to_string());
            }
        }
    }
    Ok(out)
}

#[tauri::command]
async fn pick_output_dir(app: AppHandle) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;
    let dir = app
        .dialog()
        .file()
        .set_title("Chọn thư mục đầu ra")
        .blocking_pick_folder();
    Ok(dir.and_then(|d| d.into_path().ok().map(|p| p.to_string_lossy().to_string())))
}

#[tauri::command]
async fn pick_download_dir(app: AppHandle) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;
    let dir = app
        .dialog()
        .file()
        .set_title("Chọn thư mục tải video về")
        .blocking_pick_folder();
    Ok(dir.and_then(|d| d.into_path().ok().map(|p| p.to_string_lossy().to_string())))
}

#[tauri::command]
async fn pick_speaker_wav(app: AppHandle) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;
    let file = app
        .dialog()
        .file()
        .add_filter("Audio WAV", &["wav"])
        .set_title("Chọn file giọng mẫu XTTS (WAV 3–10 giây)")
        .blocking_pick_file();
    Ok(file.and_then(|f| f.into_path().ok().map(|p| p.to_string_lossy().to_string())))
}

#[tauri::command]
async fn list_xtts_speakers() -> Result<Value, String> {
    engine::run_engine_json(&["list-xtts-speakers"]).await
}

#[tauri::command]
async fn open_folder(app: AppHandle, path: String) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    app.opener()
        .open_path(path, None::<&str>)
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn probe_videos(paths: Vec<String>) -> Result<Value, String> {
    let mut args = vec!["probe".to_string()];
    args.extend(paths);
    let str_args: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
    engine::run_engine_json(&str_args).await
}

#[tauri::command]
async fn probe_url(url: String) -> Result<Value, String> {
    engine::run_engine_json(&["probe-url", &url]).await
}

#[tauri::command]
async fn download_url(
    app: AppHandle,
    state: State<'_, Mutex<EngineState>>,
    url: String,
    download_dir: Option<String>,
) -> Result<String, String> {
    engine::download_url(app, state, url, download_dir).await
}

#[tauri::command]
async fn url_help() -> Result<Value, String> {
    engine::run_engine_json(&["url-help"]).await
}

#[tauri::command]
async fn start_job(
    app: AppHandle,
    state: State<'_, Mutex<EngineState>>,
    options: JobOptions,
) -> Result<String, String> {
    engine::start_job(app, state, options).await
}

#[tauri::command]
async fn cancel_job(state: State<'_, Mutex<EngineState>>, job_id: String) -> Result<(), String> {
    engine::cancel_job(state, job_id).await
}

#[tauri::command]
async fn retry_failed(
    app: AppHandle,
    state: State<'_, Mutex<EngineState>>,
    job_id: String,
    stems: Option<Vec<String>>,
) -> Result<(), String> {
    engine::retry_failed(app, state, job_id, stems).await
}

#[tauri::command]
async fn resume_job(
    app: AppHandle,
    state: State<'_, Mutex<EngineState>>,
    job_id: String,
    stems: Option<Vec<String>>,
) -> Result<(), String> {
    engine::resume_job(app, state, job_id, stems).await
}

#[tauri::command]
async fn get_queue(job_id: String) -> Result<Value, String> {
    engine::run_engine_json(&["queue", "--job-id", &job_id]).await
}

#[tauri::command]
async fn review_get(job_id: String, stem: String) -> Result<Value, String> {
    engine::run_engine_json(&["review-get", "--job-id", &job_id, "--stem", &stem]).await
}

#[tauri::command]
async fn review_set(job_id: String, stem: String, segments: Value) -> Result<(), String> {
    engine::review_set(job_id, stem, segments).await
}

#[tauri::command]
async fn continue_after_review(
    app: AppHandle,
    state: State<'_, Mutex<EngineState>>,
    job_id: String,
    stem: String,
) -> Result<(), String> {
    engine::continue_after_review(app, state, job_id, stem).await
}

#[tauri::command]
async fn list_models() -> Result<Value, String> {
    engine::run_engine_json(&["models"]).await
}

#[tauri::command]
async fn download_model(app: AppHandle, state: State<'_, Mutex<EngineState>>, model_id: String) -> Result<(), String> {
    engine::download_model(app, state, model_id).await
}

#[tauri::command]
async fn delete_model(model_id: String) -> Result<(), String> {
    let _ = engine::run_engine_capture(&["models-delete", &model_id, "--yes"])?;
    Ok(())
}

#[tauri::command]
async fn get_settings() -> Result<Value, String> {
    engine::run_engine_json(&["settings-get"]).await
}

#[tauri::command]
async fn save_settings(settings: Value) -> Result<(), String> {
    engine::save_settings(settings).await
}

#[tauri::command]
async fn doctor() -> Result<Value, String> {
    engine::run_engine_json(&["doctor"]).await
}

#[tauri::command]
async fn privacy_notice() -> Result<Value, String> {
    engine::run_engine_json(&["privacy-notice"]).await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .manage(Mutex::new(EngineState::default()))
        .invoke_handler(tauri::generate_handler![
            pick_videos,
            pick_output_dir,
            pick_download_dir,
            pick_speaker_wav,
            open_folder,
            probe_videos,
            probe_url,
            download_url,
            url_help,
            start_job,
            cancel_job,
            retry_failed,
            resume_job,
            get_queue,
            review_get,
            review_set,
            continue_after_review,
            list_models,
            list_xtts_speakers,
            download_model,
            delete_model,
            get_settings,
            save_settings,
            doctor,
            privacy_notice,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Dub VI");
}
