use egui::{Color32, Context, Rounding, Stroke, Vec2, Visuals};

#[inline]
const fn hex_rgb(hex: u32) -> Color32 {
    Color32::from_rgb(
        ((hex >> 16) & 0xFF) as u8,
        ((hex >> 8) & 0xFF) as u8,
        (hex & 0xFF) as u8,
    )
}

pub fn apply_theme(ctx: &Context) {
    let slate_950 = hex_rgb(0x0F172A);
    let slate_900 = hex_rgb(0x1E293B);
    let _slate_400 = hex_rgb(0x94A3B8);
    let white = hex_rgb(0xF8FAFC);
    let indigo = hex_rgb(0x6366F1);
    let blue = hex_rgb(0x3B82F6);

    let mut visuals = Visuals::dark();
    visuals.panel_fill = slate_950;
    visuals.window_fill = slate_950;
    visuals.menu_rounding = Rounding::same(8.0);

    visuals.widgets.noninteractive.bg_fill = slate_900;
    visuals.widgets.noninteractive.fg_stroke = Stroke::new(1.0, white);
    visuals.widgets.noninteractive.bg_stroke = Stroke::NONE;

    visuals.widgets.inactive.bg_fill = slate_900;
    visuals.widgets.inactive.fg_stroke = Stroke::new(1.0, white);
    visuals.widgets.inactive.rounding = Rounding::same(8.0);

    visuals.widgets.hovered.bg_fill = hex_rgb(0x334155);
    visuals.widgets.hovered.fg_stroke = Stroke::new(1.0, white);
    visuals.widgets.hovered.rounding = Rounding::same(8.0);

    visuals.widgets.active.bg_fill = indigo;
    visuals.widgets.active.fg_stroke = Stroke::new(1.0, white);
    visuals.widgets.active.rounding = Rounding::same(8.0);

    visuals.widgets.open.bg_fill = indigo;
    visuals.widgets.open.fg_stroke = Stroke::new(1.0, white);
    visuals.widgets.open.rounding = Rounding::same(8.0);

    visuals.selection.bg_fill = indigo;
    visuals.selection.stroke = Stroke::new(1.0, blue);
    visuals.hyperlink_color = blue;
    visuals.warn_fg_color = hex_rgb(0xF59E0B);
    visuals.error_fg_color = hex_rgb(0xEF4444);

    ctx.set_visuals(visuals);

    let mut style = (*ctx.style()).clone();
    style.spacing.button_padding = Vec2::new(12.0, 8.0);
    style.spacing.item_spacing = Vec2::new(10.0, 8.0);
    style.spacing.menu_margin = egui::Margin::same(8.0);
    ctx.set_style(style);
}
