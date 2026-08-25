use rusqlite::{Connection, OpenFlags, Result};
use std::path::PathBuf;
use uuid::Uuid;

#[derive(Default, Debug, Clone, Copy)]
pub struct Metrics {
    pub agents: i64,
    pub tasks: i64,
    pub logs: i64,
}

#[derive(Clone, Debug)]
pub struct Agent {
    pub id: String,
    pub hostname: String,
    pub os: String,
    pub username: String,
    pub status: String,
    pub last_seen: String,
}

#[derive(Clone, Debug)]
pub struct Task {
    pub agent_id: String,
    pub module: String,
    pub action: String,
    pub params: String,
    pub status: String,
    pub priority: String,
    pub result: Option<String>,
    pub error: Option<String>,
    pub created_at: String,
}

#[derive(Clone, Debug)]
pub struct LogEntry {
    pub timestamp: String,
    pub level: String,
    pub module: String,
    pub message: String,
}

#[derive(Clone, Debug, Default)]
pub struct DbSnapshot {
    pub metrics: Metrics,
    pub agents: Vec<Agent>,
    pub tasks: Vec<Task>,
    pub logs: Vec<LogEntry>,
}

pub fn lucy_db_path() -> PathBuf {
    if let Ok(exe) = std::env::current_exe() {
        if let Some(root) = exe.ancestors().nth(3) {
            let candidate = root.join("lucy.db");
            if candidate.exists() {
                return candidate;
            }
        }
    }
    PathBuf::from(r"C:\Heybro\PROJECTS\ACTIVE\Lucy\lucy.db")
}

fn fmt_dt(v: &str) -> String {
    v.replace('T', " ").chars().take(16).collect()
}

pub fn load_lucy_data() -> Result<DbSnapshot> {
    let path = lucy_db_path();
    let flags = OpenFlags::SQLITE_OPEN_READ_ONLY;
    let conn = Connection::open_with_flags(path, flags)?;
    conn.busy_timeout(std::time::Duration::from_millis(3000))?;

    let agents_count: i64 = conn.query_row("SELECT COUNT(*) FROM agents", [], |r| r.get(0))?;
    let tasks_count: i64 = conn.query_row("SELECT COUNT(*) FROM tasks", [], |r| r.get(0))?;
    let logs_count: i64 = conn.query_row("SELECT COUNT(*) FROM logs", [], |r| r.get(0))?;

    let mut agents = Vec::new();
    let mut stmt = conn.prepare(
        "SELECT id, hostname, os, username, status, last_seen \
         FROM agents ORDER BY last_seen DESC LIMIT 50",
    )?;
    let rows = stmt.query_map([], |row| {
        Ok(Agent {
            id: row.get(0)?,
            hostname: row.get(1)?,
            os: row.get(2)?,
            username: row.get(3)?,
            status: row.get(4)?,
            last_seen: fmt_dt(&row.get::<_, String>(5)?),
        })
    })?;
    for r in rows {
        agents.push(r?);
    }

    let mut tasks = Vec::new();
    let mut stmt = conn.prepare(
        "SELECT agent_id, module, action, params, status, priority, result, error, created_at \
         FROM tasks ORDER BY created_at DESC LIMIT 50",
    )?;
    let rows = stmt.query_map([], |row| {
        Ok(Task {
            agent_id: row.get(0)?,
            module: row.get(1)?,
            action: row.get(2)?,
            params: row.get(3).unwrap_or_default(),
            status: row.get(4)?,
            priority: row.get(5)?,
            result: row.get(6).ok(),
            error: row.get(7).ok(),
            created_at: fmt_dt(&row.get::<_, String>(8)?),
        })
    })?;
    for r in rows {
        tasks.push(r?);
    }

    let mut logs = Vec::new();
    let mut stmt = conn.prepare(
        "SELECT timestamp, level, module, message \
         FROM logs ORDER BY timestamp DESC LIMIT 50",
    )?;
    let rows = stmt.query_map([], |row| {
        Ok(LogEntry {
            timestamp: fmt_dt(&row.get::<_, String>(0)?),
            level: row.get(1)?,
            module: row.get(2)?,
            message: row.get(3)?,
        })
    })?;
    for r in rows {
        logs.push(r?);
    }

    Ok(DbSnapshot {
        metrics: Metrics {
            agents: agents_count,
            tasks: tasks_count,
            logs: logs_count,
        },
        agents,
        tasks,
        logs,
    })
}

pub fn enqueue_task(agent_id: &str, module: &str, action: &str, params_json: &str) -> Result<String> {
    let path = lucy_db_path();
    let flags = OpenFlags::SQLITE_OPEN_READ_WRITE;
    let conn = Connection::open_with_flags(path, flags)?;
    conn.busy_timeout(std::time::Duration::from_millis(5000))?;

    let id = Uuid::new_v4().to_string();

    conn.execute(
        "INSERT INTO tasks \
         (id, agent_id, module, action, params, status, priority, timeout, created_at, timeline_id) \
         VALUES (?1, ?2, ?3, ?4, ?5, 'queued', 'normal', 60, datetime('now'), '')",
        [&id, agent_id, module, action, params_json],
    )?;

    Ok(id)
}
