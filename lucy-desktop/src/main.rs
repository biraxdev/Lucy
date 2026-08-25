mod theme;
mod db;

use db::{load_lucy_data, DbSnapshot};
use eframe::NativeOptions;
use egui::{
    CentralPanel, Color32, Context, Frame, Grid, RichText, ScrollArea, SidePanel, Ui, Vec2,
};
use egui_phosphor::regular as icon;
use serde_json::json;
use tokio::runtime::Runtime;
use tokio::sync::oneshot;

#[derive(Default, Clone, Copy, PartialEq, Eq)]
enum Section {
    #[default]
    Dashboard,
    Agents,
    Tasks,
    Logs,
    Chat,
    Settings,
}

impl Section {
    fn label(self) -> &'static str {
        match self {
            Section::Dashboard => "Dashboard",
            Section::Agents => "Agents",
            Section::Tasks => "Tasks",
            Section::Logs => "Logs",
            Section::Chat => "Chat",
            Section::Settings => "Settings",
        }
    }

    fn icon(self) -> &'static str {
        match self {
            Section::Dashboard => icon::CHART_BAR,
            Section::Agents => icon::USERS,
            Section::Tasks => icon::LIST,
            Section::Logs => icon::NOTEBOOK,
            Section::Chat => icon::CHAT_TEARDROP,
            Section::Settings => icon::GEAR,
        }
    }
}

struct LucyApp {
    selected: Section,
    data: DbSnapshot,
    data_rx: Option<oneshot::Receiver<Result<DbSnapshot, rusqlite::Error>>>,
    rt: Runtime,
    chat_input: String,
    selected_agent_id: Option<String>,
}

impl LucyApp {
    fn new(cc: &eframe::CreationContext<'_>) -> Self {
        theme::apply_theme(&cc.egui_ctx);

        let mut fonts = egui::FontDefinitions::default();
        egui_phosphor::add_to_fonts(&mut fonts, egui_phosphor::Variant::Regular);
        cc.egui_ctx.set_fonts(fonts);

        let rt = Runtime::new().expect("tokio runtime");
        let (tx, rx) = oneshot::channel();
        rt.spawn_blocking(move || {
            let _ = tx.send(load_lucy_data());
        });

        Self {
            selected: Section::Dashboard,
            data: DbSnapshot::default(),
            data_rx: Some(rx),
            rt,
            chat_input: String::new(),
            selected_agent_id: None,
        }
    }

    fn try_receive_data(&mut self) {
        if let Some(rx) = &mut self.data_rx {
            match rx.try_recv() {
                Ok(Ok(snapshot)) => {
                    self.data = snapshot;
                    self.data_rx = None;
                }
                Ok(Err(_)) | Err(_) => {}
            }
        }
    }

    fn refresh_data(&mut self) {
        let (tx, rx) = oneshot::channel();
        self.rt.spawn_blocking(move || {
            let _ = tx.send(load_lucy_data());
        });
        self.data_rx = Some(rx);
    }
}

impl eframe::App for LucyApp {
    fn update(&mut self, ctx: &Context, _frame: &mut eframe::Frame) {
        self.try_receive_data();

        SidePanel::left("sidebar")
            .resizable(false)
            .default_width(220.0)
            .show(ctx, |ui| {
                ui.vertical_centered(|ui| {
                    ui.heading(
                        RichText::new("Lucy")
                            .color(Color32::from_rgb(99, 102, 241))
                            .size(24.0),
                    );
                });
                ui.add_space(16.0);

                let sections = [
                    Section::Dashboard,
                    Section::Agents,
                    Section::Tasks,
                    Section::Logs,
                    Section::Chat,
                    Section::Settings,
                ];
                for section in sections {
                    let selected = self.selected == section;
                    let text_color = if selected {
                        Color32::WHITE
                    } else {
                        Color32::from_rgb(148, 163, 184)
                    };
                    let fill = if selected {
                        Color32::from_rgb(99, 102, 241)
                    } else {
                        Color32::TRANSPARENT
                    };

                    let label = format!("{}  {}", section.icon(), section.label());
                    let button = egui::Button::new(RichText::new(label).color(text_color))
                        .fill(fill)
                        .rounding(8.0)
                        .min_size(Vec2::new(180.0, 36.0));
                    if ui.add(button).clicked() {
                        self.selected = section;
                    }
                    ui.add_space(4.0);
                }
            });

        CentralPanel::default().show(ctx, |ui| {
            match self.selected {
                Section::Dashboard => dashboard(ui, &self.data),
                Section::Agents => agents_section(ui, &self.data),
                Section::Tasks => tasks_section(ui, &self.data),
                Section::Logs => logs_section(ui, &self.data),
                Section::Chat => {
                    let data = self.data.clone();
                    chat_section(ui, self, &data);
                }
                Section::Settings => settings_section(ui, self),
            }
        });
    }
}

fn level_color(level: &str) -> Color32 {
    match level.to_lowercase().as_str() {
        "error" | "critical" => Color32::from_rgb(239, 68, 68),
        "warn" | "warning" => Color32::from_rgb(245, 158, 11),
        "info" => Color32::from_rgb(59, 130, 246),
        _ => Color32::from_rgb(148, 163, 184),
    }
}

fn status_color(status: &str) -> Color32 {
    match status.to_lowercase().as_str() {
        "active" | "online" | "success" | "completed" | "running" => Color32::from_rgb(34, 197, 94),
        "idle" | "pending" | "waiting" | "queued" => Color32::from_rgb(245, 158, 11),
        "offline" | "failed" | "error" | "dead" => Color32::from_rgb(239, 68, 68),
        _ => Color32::from_rgb(148, 163, 184),
    }
}

fn truncate(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        s.chars().take(max).collect::<String>() + "…"
    }
}

fn dashboard(ui: &mut Ui, data: &DbSnapshot) {
    ui.heading("Dashboard");
    ui.add_space(12.0);

    ui.label(
        RichText::new("Vue d'ensemble du système Lucy")
            .color(Color32::from_rgb(148, 163, 184))
            .size(12.0),
    );
    ui.add_space(16.0);

    ui.columns(3, |cols| {
        let items = [
            ("Agents actifs", data.metrics.agents),
            ("Tâches en cours", data.metrics.tasks),
            ("Entrées log", data.metrics.logs),
        ];
        for (col, (label, value)) in cols.iter_mut().zip(items.iter()) {
            Frame::group(col.style())
                .fill(Color32::from_rgb(30, 41, 59))
                .rounding(8.0)
                .inner_margin(egui::Margin::same(12.0))
                .show(col, |ui| {
                    ui.vertical(|ui| {
                        ui.label(
                            RichText::new(*label)
                                .color(Color32::from_rgb(148, 163, 184))
                                .size(12.0),
                        );
                        ui.add_space(4.0);
                        ui.label(RichText::new(value.to_string()).size(24.0));
                    });
                });
        }
    });

    ui.add_space(24.0);
    ui.heading("Logs récents");
    ui.add_space(8.0);
    Frame::group(ui.style())
        .fill(Color32::from_rgb(30, 41, 59))
        .rounding(8.0)
        .show(ui, |ui| {
            ScrollArea::vertical().max_height(200.0).show(ui, |ui| {
                Grid::new("dash_logs_grid")
                    .num_columns(4)
                    .spacing(Vec2::new(12.0, 6.0))
                    .striped(true)
                    .show(ui, |ui| {
                        for log in data.logs.iter().take(10) {
                            ui.label(RichText::new(&log.timestamp).monospace().size(11.0));
                            ui.label(
                                RichText::new(&log.level)
                                    .color(level_color(&log.level))
                                    .size(11.0),
                            );
                            ui.label(RichText::new(&log.module).size(11.0));
                            ui.label(RichText::new(truncate(&log.message, 60)).size(11.0));
                            ui.end_row();
                        }
                    });
            });
        });
}

fn agents_section(ui: &mut Ui, data: &DbSnapshot) {
    ui.heading("Agents");
    ui.add_space(12.0);
    Frame::group(ui.style())
        .fill(Color32::from_rgb(30, 41, 59))
        .rounding(8.0)
        .show(ui, |ui| {
            ScrollArea::vertical().max_height(520.0).show(ui, |ui| {
                Grid::new("agents_grid")
                    .num_columns(5)
                    .spacing(Vec2::new(16.0, 8.0))
                    .striped(true)
                    .show(ui, |ui| {
                        ui.label(RichText::new("Hostname").strong());
                        ui.label(RichText::new("OS").strong());
                        ui.label(RichText::new("User").strong());
                        ui.label(RichText::new("Status").strong());
                        ui.label(RichText::new("Last seen").strong());
                        ui.end_row();

                        for a in &data.agents {
                            ui.label(truncate(&a.hostname, 24));
                            ui.label(&a.os);
                            ui.label(truncate(&a.username, 16));
                            ui.label(
                                RichText::new(&a.status).color(status_color(&a.status)),
                            );
                            ui.label(&a.last_seen);
                            ui.end_row();
                        }
                    });
            });
        });
}

fn tasks_section(ui: &mut Ui, data: &DbSnapshot) {
    ui.heading("Tâches");
    ui.add_space(12.0);
    Frame::group(ui.style())
        .fill(Color32::from_rgb(30, 41, 59))
        .rounding(8.0)
        .show(ui, |ui| {
            ScrollArea::vertical().max_height(520.0).show(ui, |ui| {
                Grid::new("tasks_grid")
                    .num_columns(6)
                    .spacing(Vec2::new(16.0, 8.0))
                    .striped(true)
                    .show(ui, |ui| {
                        ui.label(RichText::new("Time").strong());
                        ui.label(RichText::new("Agent").strong());
                        ui.label(RichText::new("Module").strong());
                        ui.label(RichText::new("Action").strong());
                        ui.label(RichText::new("Status").strong());
                        ui.label(RichText::new("Priority").strong());
                        ui.end_row();

                        for t in &data.tasks {
                            ui.label(RichText::new(&t.created_at).monospace().size(11.0));
                            ui.label(truncate(&t.agent_id, 8));
                            ui.label(&t.module);
                            ui.label(&t.action);
                            ui.label(
                                RichText::new(&t.status).color(status_color(&t.status)),
                            );
                            ui.label(&t.priority);
                            ui.end_row();
                        }
                    });
            });
        });
}

fn logs_section(ui: &mut Ui, data: &DbSnapshot) {
    ui.heading("Logs");
    ui.add_space(12.0);
    Frame::group(ui.style())
        .fill(Color32::from_rgb(30, 41, 59))
        .rounding(8.0)
        .show(ui, |ui| {
            ScrollArea::vertical().max_height(520.0).show(ui, |ui| {
                Grid::new("logs_grid")
                    .num_columns(4)
                    .spacing(Vec2::new(12.0, 8.0))
                    .striped(true)
                    .show(ui, |ui| {
                        ui.label(RichText::new("Time").strong());
                        ui.label(RichText::new("Level").strong());
                        ui.label(RichText::new("Module").strong());
                        ui.label(RichText::new("Message").strong());
                        ui.end_row();

                        for l in &data.logs {
                            ui.label(RichText::new(&l.timestamp).monospace().size(11.0));
                            ui.label(
                                RichText::new(&l.level)
                                    .color(level_color(&l.level))
                                    .size(11.0),
                            );
                            ui.label(RichText::new(&l.module).size(11.0));
                            ui.label(RichText::new(truncate(&l.message, 80)).size(11.0));
                            ui.end_row();
                        }
                    });
            });
        });
}

fn chat_section(ui: &mut Ui, app: &mut LucyApp, data: &DbSnapshot) {
    ui.heading("Chat agent");
    ui.add_space(12.0);

    let selected_text: String = app
        .selected_agent_id
        .as_ref()
        .and_then(|id| data.agents.iter().find(|a| &a.id == id).map(|a| a.hostname.clone()))
        .unwrap_or_else(|| "Sélectionner un agent".to_string());

    if data.agents.is_empty() {
        ui.label("Aucun agent connecté.");
        return;
    }

    egui::ComboBox::new("agent_chat_selector", "")
        .selected_text(selected_text)
        .show_ui(ui, |ui| {
            for a in &data.agents {
                ui.selectable_value(&mut app.selected_agent_id, Some(a.id.clone()), &a.hostname);
            }
        });

    ui.add_space(8.0);
    Frame::group(ui.style())
        .fill(Color32::from_rgb(15, 23, 42))
        .rounding(8.0)
        .inner_margin(egui::Margin::same(12.0))
        .show(ui, |ui| {
            ScrollArea::vertical().max_height(380.0).show(ui, |ui| {
                if let Some(agent_id) = app.selected_agent_id.clone() {
                    let mut has = false;
                    for t in data.tasks.iter().filter(|t| t.agent_id == agent_id).rev() {
                        has = true;

                        Frame::group(ui.style())
                            .fill(Color32::from_rgb(99, 102, 241))
                            .rounding(8.0)
                            .inner_margin(egui::Margin::same(8.0))
                            .show(ui, |ui| {
                                ui.horizontal(|ui| {
                                    ui.label(RichText::new(">").size(11.0).color(Color32::WHITE));
                                    ui.label(RichText::new(format!("{} / {}", t.module, t.action)).size(11.0));
                                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                        ui.label(RichText::new(&t.created_at).size(10.0).color(Color32::from_rgb(210, 211, 255)));
                                    });
                                });
                                ui.label(RichText::new(truncate(&t.params, 120)).size(12.0).color(Color32::WHITE));
                            });

                        if let Some(r) = &t.result {
                            Frame::group(ui.style())
                                .fill(Color32::from_rgb(30, 41, 59))
                                .rounding(8.0)
                                .inner_margin(egui::Margin::same(8.0))
                                .show(ui, |ui| {
                                    ui.label(RichText::new(truncate(r, 120)).size(12.0).color(Color32::from_rgb(148, 163, 184)));
                                });
                        } else if let Some(e) = &t.error {
                            Frame::group(ui.style())
                                .fill(Color32::from_rgb(60, 30, 30))
                                .rounding(8.0)
                                .inner_margin(egui::Margin::same(8.0))
                                .show(ui, |ui| {
                                    ui.label(RichText::new(truncate(e, 120)).size(12.0).color(Color32::from_rgb(239, 68, 68)));
                                });
                        } else {
                            ui.label(RichText::new("… en attente …").size(11.0).color(Color32::from_rgb(148, 163, 184)));
                        }

                        ui.add_space(10.0);
                    }
                    if !has {
                        ui.label("Aucun message pour cet agent.");
                    }
                } else {
                    ui.label("Sélectionnez un agent pour voir la conversation.");
                }
            });
        });

    ui.add_space(8.0);
    ui.horizontal(|ui| {
        ui.text_edit_singleline(&mut app.chat_input);
        if ui
            .button(RichText::new("Envoyer").color(Color32::WHITE))
            .clicked()
            && !app.chat_input.is_empty()
        {
            if let Some(agent) = app.selected_agent_id.clone() {
                let cmd = app.chat_input.clone();
                app.chat_input.clear();
                let params = json!({"cmd": cmd}).to_string();
                let handle = app.rt.spawn_blocking(move || db::enqueue_task(&agent, "shell", "exec", &params));
                if let Ok(Ok(_)) = app.rt.block_on(handle) {
                    app.refresh_data();
                }
            }
        }
    });
}

fn settings_section(ui: &mut Ui, app: &mut LucyApp) {
    ui.heading("Settings");
    ui.add_space(12.0);
    ui.label(RichText::new("Lucy Desktop v0.1.0").size(14.0));
    ui.add_space(8.0);
    ui.label(
        RichText::new(format!("Base connectée : {}", db::lucy_db_path().display()))
            .color(Color32::from_rgb(148, 163, 184))
            .size(12.0),
    );
    ui.add_space(16.0);

    if ui
        .add(
            egui::Button::new(RichText::new("Rafraîchir les données").color(Color32::WHITE))
                .fill(Color32::from_rgb(99, 102, 241))
                .rounding(8.0)
                .min_size(Vec2::new(160.0, 36.0)),
        )
        .clicked()
    {
        app.refresh_data();
    }

    if app.data_rx.is_some() {
        ui.add_space(8.0);
        ui.label(
            RichText::new("Chargement...")
                .color(Color32::from_rgb(148, 163, 184))
                .size(12.0),
        );
    }
}

fn main() -> eframe::Result {
    let options = NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1280.0, 800.0])
            .with_title("Lucy Desktop"),
        ..Default::default()
    };
    eframe::run_native(
        "Lucy Desktop",
        options,
        Box::new(|cc| Ok(Box::new(LucyApp::new(cc)))),
    )
}
