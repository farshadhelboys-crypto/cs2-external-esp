#include "Overlays.hpp"
#include <cmath>

#include "updater/Updater.hpp"
#include "gui/renderer/Renderer.hpp" // Circular dependency
#include "gui/frontend/menu/Menu.hpp" // Circular dependency
#include "assets/fonts/WeaponIcons.h"

bool Overlays::Init() {
    return GetInstance().InitImpl();
}

void Overlays::Render() {
    return GetInstance().RenderImpl();
}

bool Overlays::InitImpl() {
    auto& io = ImGui::GetIO();

    ImFontConfig cfg{};
    cfg.FontDataOwnedByAtlas = false;

	this->font = io.Fonts->AddFontFromFileTTF("C:\\Windows\\Fonts\\consola.ttf", 12.0f, &cfg);
	this->font_alt = io.Fonts->AddFontFromFileTTF("C:\\Windows\\Fonts\\arial.ttf", 14.0f, &cfg);
    this->font_icons = io.Fonts->AddFontFromMemoryTTF(weapon_icon_font, weapon_icon_font_len, 16.0f,  &cfg);
	
	ImFontConfig merge_icon_cfg{};
	merge_icon_cfg.FontDataOwnedByAtlas = false;
	merge_icon_cfg.MergeMode = true;

	static const ImWchar icon_ranges[] = { 0xE000, 0xE046, 0 };
	io.Fonts->AddFontFromMemoryTTF(weapon_icon_font, weapon_icon_font_len, 12.f, &merge_icon_cfg, icon_ranges);

    this->vel_buffer.resize(static_cast<size_t>(cfg::world::velocity::sample_rate * cfg::world::velocity::sample_length));

    return true;
}

void Overlays::RenderImpl() {
    ImGui::PushFont(this->font);
    {
        RenderWatermark();
        RenderNotice();
        RenderEspStatus();
    #ifdef _DEBUG
        RenderDebugWindow();
    #endif
    }
    ImGui::PopFont();

    ImGui::PushFont(this->font_alt);
    {
        RenderSpectatorList();
        RenderSpeedChart();
        RenderRadar();
        RenderBomb();
    }
    ImGui::PopFont();
}

void Overlays::RenderWatermark() {
    if (!cfg::settings::watermark)
        return;

    auto& io = ImGui::GetIO();
    auto d = ImGui::GetBackgroundDrawList();

    float t = (float)ImGui::GetTime();
    float pulse = 0.35f + 0.65f * (0.5f + 0.5f * sinf(t * 2.2f));
    int alpha = (int)(pulse * 255.f);
    if (alpha < 40) alpha = 40;

    static int margin = 12;
    static int padding = 8;
    const char* watermark_string = "feri pm.esp";

    auto size = ImGui::CalcTextSize(watermark_string);

    auto rect_start = ImVec2(io.DisplaySize.x * 0.5f - size.x * 0.5f - padding, (float)margin);
    auto rect_end = ImVec2(io.DisplaySize.x * 0.5f + size.x * 0.5f + padding, (float)margin + size.y + padding);
    auto pos = ImVec2(rect_start.x + padding, rect_start.y + padding * 0.5f);

    d->AddRectFilled(rect_start, rect_end, IM_COL32(0, 0, 0, (alpha * 120) / 255), 6.f);
    d->AddRect(rect_start, rect_end, IM_COL32(80, 220, 120, alpha), 6.f);
    d->AddText(pos, IM_COL32(120, 255, 160, alpha), watermark_string);
}

void Overlays::RenderNotice() {
    static auto status = Updater::GetStatus();
    if (status.notice.empty()) return;
    if (!Renderer::IsOpen()) return;
    auto& io = ImGui::GetIO();
    auto d = ImGui::GetBackgroundDrawList();
    static int margin = 10;
    static int padding = 10;
    auto menu_pos = Menu::GetPos();
    auto menu_size = Menu::GetSize();
    auto max_width = menu_size.x - padding * 2;
    auto size = ImGui::CalcTextSize(status.notice.data(), nullptr, false, max_width);
    auto rect_start = ImVec2(menu_pos.x, menu_pos.y - margin - padding * 2 - size.y);
    auto rect_end = ImVec2(menu_pos.x + menu_size.x, menu_pos.y - margin);
    auto pos = ImVec2(rect_start.x + padding, rect_start.y + padding);
    d->AddRectFilled(rect_start, rect_end, IM_COL32(0, 0, 0, 200), 10.f);
    d->AddRect(rect_start, rect_end, IM_COL32(100, 100, 100, 200), 10.f);
    d->AddText(pos - ImVec2(0, padding + padding * 0.5f), IM_COL32(255, 200, 0, 255), "Notice");
    d->AddText(this->font, this->font->LegacySize, pos, IM_COL32(255, 255, 255, 255), status.notice.data(), nullptr, max_width);
}

void Overlays::RenderEspStatus() {}
void Overlays::RenderSpectatorList() {}
void Overlays::RenderSpeedChart() {}
#ifdef _DEBUG
void Overlays::RenderDebugWindow() {}
#endif
void Overlays::RenderRadar() {}
void Overlays::RenderBomb() {}
