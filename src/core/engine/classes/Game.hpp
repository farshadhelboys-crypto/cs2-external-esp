#pragma once

class Game {
public:
    Game() {};

    bool Update();
    bool UpdateMatrix();
    bool UpdateEntityList();

public:
    view_matrix_t view_matrix;

    uintptr_t entity_list;
    uintptr_t list_entry;

    Vec3_t local_pos{};
    float local_yaw = 0.f;
    float local_pitch = 0.f;
    int local_hp = 0;
    int positioned = 0;
private:
    uintptr_t address;
};
