//! Scan folders for videos and match `{stem}_vi.srt` even when files are interleaved.

use serde::Serialize;
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

const VIDEO_EXT: &[&str] = &["mp4", "mkv", "mov", "avi", "webm"];
const SUB_EXT: &[&str] = &["srt", "vtt"];
const FOLDER_MAX_DEPTH: u32 = 2;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SubtitleMatch {
    pub video: String,
    pub subtitle: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MediaScan {
    pub folder: String,
    pub videos: Vec<String>,
    pub subtitles: Vec<String>,
    pub matches: Vec<SubtitleMatch>,
}

fn ext_lower(path: &Path) -> String {
    path.extension()
        .and_then(|e| e.to_str())
        .map(|s| s.to_ascii_lowercase())
        .unwrap_or_default()
}

fn display_path(path: &Path) -> String {
    path.to_string_lossy().to_string()
}

/// `Lesson 01_vi.srt` → `Lesson 01` (Udemy / user convention).
fn stem_from_vi_subtitle(file_name: &str) -> Option<&str> {
    let lower = file_name.to_ascii_lowercase();
    for suffix in ["_vi.srt", "_vi.vtt"] {
        if lower.ends_with(suffix) && file_name.len() > suffix.len() {
            return Some(&file_name[..file_name.len() - suffix.len()]);
        }
    }
    None
}

fn walk_files(dir: &Path, depth: u32, max_depth: u32, out: &mut Vec<PathBuf>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let Ok(meta) = entry.metadata() else {
            continue;
        };
        if meta.is_dir() {
            if depth >= max_depth {
                continue;
            }
            let name = entry.file_name().to_string_lossy().to_string();
            if name.starts_with('.') {
                continue;
            }
            walk_files(&path, depth + 1, max_depth, out);
        } else if meta.is_file() {
            out.push(path);
        }
    }
}

fn index_vi_subs(files: &[PathBuf]) -> HashMap<String, Vec<PathBuf>> {
    let mut map: HashMap<String, Vec<PathBuf>> = HashMap::new();
    for path in files {
        let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
            continue;
        };
        let Some(stem) = stem_from_vi_subtitle(name) else {
            continue;
        };
        map.entry(stem.to_ascii_lowercase())
            .or_default()
            .push(path.clone());
    }
    map
}

fn pick_sub_for_video(video: &Path, index: &HashMap<String, Vec<PathBuf>>) -> Option<PathBuf> {
    let stem = video.file_stem()?.to_string_lossy().to_ascii_lowercase();
    let cands = index.get(&stem)?;
    let parent = video.parent();
    if let Some(dir) = parent {
        if let Some(same) = cands.iter().find(|c| c.parent() == Some(dir)) {
            return Some(same.clone());
        }
    }
    cands.first().cloned()
}

fn unique_push(list: &mut Vec<String>, seen: &mut HashSet<String>, value: String) {
    let key = value.to_ascii_lowercase();
    if seen.insert(key) {
        list.push(value);
    }
}

/// Expand folders, list videos, and pair each with `{stem}_vi.srt`.
pub fn expand_and_match(paths: &[String]) -> MediaScan {
    let mut videos: Vec<String> = Vec::new();
    let mut subtitles: Vec<String> = Vec::new();
    let mut index_files: Vec<PathBuf> = Vec::new();
    let mut seen_vid: HashSet<String> = HashSet::new();
    let mut seen_sub: HashSet<String> = HashSet::new();
    let mut folder = String::new();

    for raw in paths {
        let path = PathBuf::from(raw);
        if path.is_dir() {
            if folder.is_empty() {
                folder = display_path(&path);
            }
            let mut found = Vec::new();
            walk_files(&path, 0, FOLDER_MAX_DEPTH, &mut found);
            index_files.extend(found.iter().cloned());
            for file in found {
                let ext = ext_lower(&file);
                let shown = display_path(&file);
                if VIDEO_EXT.contains(&ext.as_str()) {
                    unique_push(&mut videos, &mut seen_vid, shown);
                } else if SUB_EXT.contains(&ext.as_str()) {
                    unique_push(&mut subtitles, &mut seen_sub, shown);
                }
            }
            continue;
        }
        if !path.is_file() {
            continue;
        }
        let ext = ext_lower(&path);
        let shown = display_path(&path);
        if VIDEO_EXT.contains(&ext.as_str()) {
            unique_push(&mut videos, &mut seen_vid, shown);
            if let Some(parent) = path.parent() {
                if folder.is_empty() {
                    folder = display_path(parent);
                }
                walk_files(parent, 0, 1, &mut index_files);
                if let Some(up) = parent.parent() {
                    walk_files(up, 0, 0, &mut index_files);
                }
            }
        } else if SUB_EXT.contains(&ext.as_str()) {
            unique_push(&mut subtitles, &mut seen_sub, shown);
            index_files.push(path);
        }
    }

    videos.sort_by(|a, b| a.to_ascii_lowercase().cmp(&b.to_ascii_lowercase()));
    let index = index_vi_subs(&index_files);
    let mut matches = Vec::new();
    for video in &videos {
        let vp = PathBuf::from(video);
        if let Some(sub) = pick_sub_for_video(&vp, &index) {
            let sub_s = display_path(&sub);
            unique_push(&mut subtitles, &mut seen_sub, sub_s.clone());
            matches.push(SubtitleMatch {
                video: video.clone(),
                subtitle: sub_s,
            });
        }
    }
    MediaScan {
        folder,
        videos,
        subtitles,
        matches,
    }
}

pub fn scan_folder(dir: &Path) -> Result<MediaScan, String> {
    if !dir.is_dir() {
        return Err(format!("Không phải thư mục: {}", dir.display()));
    }
    Ok(expand_and_match(&[display_path(dir)]))
}
