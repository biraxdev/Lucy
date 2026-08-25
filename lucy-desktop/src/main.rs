mod theme;

use eframe::NativeOptions;
use egui::{CentralPanel, Color32, Context, RichText, SidePanel, Ui, Vec2};

#[derive(Default)]
struct LucyApp {
    selected: usize,
}

impl LucyApp {
    fn new(cc: &eframe::CreationContext<'_>) -> Self {
        theme::apply_theme(&cc.egui_ctx);
        Self::default()
    }
}

impl eframe::App for LucyApp {
    fn update(&mut self, ctx: &Context, _frame: &mut eframe::Frame) {
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

                let sections = ["Dashboard", "Agents", "Tasks", "Logs", "Settings"];
                for (index, label) in sections.iter().enumerate() {
                    let selected = self.selected == index;
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
                    let button = egui::Button::new(RichText::new(*label).color(text_color))
                        .fill(fill)
                        .rounding(8.0)
                        .min_size(Vec2::new(180.0, 36.0));
                    if ui.add(button).clicked() {
                        self.selected = index;
                    }
                    ui.add_space(4.0);
                }
            });

        CentralPanel::default().show(ctx, |ui| {
            match self.selected {
                0 => dashboard(ui),
                1 => placeholder(ui, "Agents"),
                2 => placeholder(ui, "Tasks"),
                3 => placeholder(ui, "Logs"),
                _ => placeholder(ui, "Settings"),
            }
        });
    }
}

fn dashboard(ui: &mut Ui) {
    ui.heading("Dashboard");
    ui.add_space(12.0);

    ui.label(
        RichText::new("Vue d'ensemble du système")
            .color(Color32::from_rgb(148, 163, 184))
            .size(12.0),
    );
    ui.add_space(16.0);

    ui.columns(3, |cols| {
        let metrics = [
            ("Agents actifs", "12"),
            ("Tâches en cours", "4"),
            ("Charge moyenne", "18%"),
        ];
        for (col, (label, value)) in cols.iter_mut().zip(metrics.iter()) {
            col.group(|ui| {
                ui.vertical(|ui| {
                    ui.label(
                        RichText::new(*label)
                            .color(Color32::from_rgb(148, 163, 184))
                            .size(12.0),
                    );
                    ui.add_space(4.0);
                    ui.label(RichText::new(*value).size(24.0));
                });
            });
        }
    });

    ui.add_space(24.0);
    ui.heading("Activité récente");
    ui.add_space(8.0);
    egui::Frame::group(ui.style())
        .fill(Color32::from_rgb(30, 41, 59))
        .rounding(8.0)
        .show(ui, |ui| {
            ui.label("Aucun événement récent à afficher.");
        });
}

fn placeholder(ui: &mut Ui, title: &str) {
    ui.heading(title);
    ui.add_space(12.0);
    ui.label("Cette section est en cours de développement.");
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
