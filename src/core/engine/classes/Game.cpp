#include "Game.hpp"

#include "core/engine/Engine.hpp"
#include "core/offsets/Dumper.hpp"

#include <cmath>
#include <cstring>

static float Dot3(const Vec3_t& a, const Vec3_t& b) {
	return a.x * b.x + a.y * b.y + a.z * b.z;
}

bool Game::Update() {
	if (!Engine::GetProcess())
		return false;

	UpdateMatrix();
	return true;
}

bool Game::UpdateMatrix() {
	auto p = Engine::GetProcess();
	auto client = Engine::GetClient();
	if (!p || !client.base)
		return false;

	this->local_pos = Vec3_t(
		p->read<float>(client.base + offsets::cm::pos_x),
		p->read<float>(client.base + offsets::cm::pos_y),
		p->read<float>(client.base + offsets::cm::pos_z));
	this->local_yaw = p->read<float>(client.base + offsets::cm::yaw);
	this->local_pitch = p->read<float>(client.base + offsets::cm::pitch);

	this->local_hp = 0;
	uint32_t hp1 = p->read<uint32_t>(client.base + offsets::cm::hp_ptr);
	if (hp1 > 0x10000) {
		uint32_t hp2 = p->read<uint32_t>(hp1 + offsets::cm::hp_off1);
		if (hp2 > 0x10000)
			this->local_hp = p->read<int>(hp2 + offsets::cm::hp_off2);
	}

	float aspect = 1280.f / 900.f;
	if (p->hwnd_) {
		RECT rc{};
		if (GetClientRect(p->hwnd_, &rc) && rc.right > 64 && rc.bottom > 64)
			aspect = (float)rc.right / (float)rc.bottom;
	}

	const float yaw = this->local_yaw * cfg::cm::yaw_sign * (3.14159265f / 180.f);
	const float pitch = this->local_pitch * cfg::cm::pitch_sign * (3.14159265f / 180.f);
	const float cy = cosf(yaw), sy = sinf(yaw), cp = cosf(pitch), sp = sinf(pitch);
	Vec3_t fwd(cp * cy, cp * sy, -sp);
	Vec3_t right(sy, -cy, 0.f);
	Vec3_t up(sp * cy, sp * sy, cp);
	Vec3_t eye = this->local_pos;
	eye.z += cfg::cm::eye_z;

	float tan_half = tanf(cfg::cm::fov * (3.14159265f / 180.f) * 0.5f);
	if (tan_half < 0.05f)
		tan_half = 0.05f;
	const float fx = 1.f / (aspect * tan_half);
	const float fy = 1.f / tan_half;

	std::memset(&this->view_matrix, 0, sizeof(this->view_matrix));
	this->view_matrix.matrix[3][0] = fwd.x;
	this->view_matrix.matrix[3][1] = fwd.y;
	this->view_matrix.matrix[3][2] = fwd.z;
	this->view_matrix.matrix[3][3] = -Dot3(eye, fwd);
	this->view_matrix.matrix[0][0] = right.x * fx;
	this->view_matrix.matrix[0][1] = right.y * fx;
	this->view_matrix.matrix[0][2] = right.z * fx;
	this->view_matrix.matrix[0][3] = -Dot3(eye, right) * fx;
	this->view_matrix.matrix[1][0] = up.x * fy;
	this->view_matrix.matrix[1][1] = up.y * fy;
	this->view_matrix.matrix[1][2] = up.z * fy;
	this->view_matrix.matrix[1][3] = -Dot3(eye, up) * fy;
	return true;
}

bool Game::UpdateEntityList() {
	auto p = Engine::GetProcess();
	auto client = Engine::GetClient();

	this->entity_list = p->read<DWORD64>(client.base + offsets::entityList);
	this->list_entry = p->read<DWORD64>(this->entity_list + 0x10);

	return true;
}
