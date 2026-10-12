#include "Cache.hpp"

#include "core/engine/Engine.hpp"
#include "core/offsets/Dumper.hpp"

#include <cmath>
#include <cstring>
#include <cstdio>
#include <cctype>
#include <algorithm>
#include <unordered_map>
#include <string>
#include <vector>

static bool GoodPos(const Vec3_t& v) {
    if (v.zero())
        return false;
    if (v.x != v.x || v.y != v.y || v.z != v.z)
        return false;
    if (fabsf(v.x) > 20000.f || fabsf(v.y) > 20000.f || fabsf(v.z) > 20000.f)
        return false;
    if (fabsf(v.x) < 0.5f && fabsf(v.y) < 0.5f && fabsf(v.z) < 0.5f)
        return false;
    return true;
}

static float Dist2(const Vec3_t& a, const Vec3_t& b) {
    float dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
    return dx * dx + dy * dy + dz * dz;
}

struct CmLayout {
    int stride;
    int serial;
    int obj;
    int hp;
    int team;
    int pos;
    bool check_serial;
};

static const CmLayout kLayouts[] = {
    { 0x14, 0x04, 0x0C, 0x11C, 0xD4, 0x290, true },
    { 0x28, 0x00, 0x20, 0x11C, 0xD4, 0x290, false },
    { 0x14, 0x04, 0x0C, 0x11C, 0xD4, 0x170, true },
    { 0x28, 0x00, 0x20, 0x11C, 0xD4, 0x170, false },
    { 0x14, 0x00, 0x0C, 0x11C, 0xD4, 0x290, false },
};

struct CmOrigin {
    Vec3_t pos{};
    bool ok = false;
};

static int g_layout = -1;
static uint32_t g_array_base = 0;

static int ScoreLayout(std::shared_ptr<pProcess> p, uint32_t base, const CmLayout& lay, CmOrigin out[64]) {
    if (!base)
        return 0;
    const int bytes = 64 * lay.stride;
    std::vector<uint8_t> raw(bytes);
    if (!p->read_raw(base, raw.data(), raw.size()))
        return 0;

    int hits = 0;
    for (int i = 0; i < 64; i++) {
        out[i] = {};
        const uint8_t* e = raw.data() + i * lay.stride;
        if (lay.check_serial) {
            uint32_t serial = *reinterpret_cast<const uint32_t*>(e + lay.serial);
            if ((serial >> 16) != (uint32_t)i && (serial & 0xFFFF) != (uint32_t)i)
                continue;
        }
        uint32_t obj = *reinterpret_cast<const uint32_t*>(e + lay.obj);
        if (obj < 0x10000)
            continue;
        int hp = p->read<int>(obj + lay.hp);
        int team = p->read<int>(obj + lay.team);
        if (hp < 1 || hp > 150 || team < 1 || team > 5)
            continue;
        Vec3_t pos = p->read<Vec3_t>(obj + lay.pos);
        if (!GoodPos(pos))
            continue;
        out[i].pos = pos;
        out[i].ok = true;
        hits++;
    }
    return hits;
}

static void ReadOrigins(std::shared_ptr<pProcess> p, uintptr_t game, CmOrigin out[64]) {
    for (int i = 0; i < 64; i++)
        out[i] = {};

    uint32_t ptr = p->read<uint32_t>(game + offsets::cm::player_array);
    uint32_t bases[2] = { ptr > 0x10000 ? ptr : 0, (uint32_t)(game + offsets::cm::player_array) };

    if (g_layout >= 0 && g_array_base) {
        CmOrigin trial[64]{};
        int hits = ScoreLayout(p, g_array_base, kLayouts[g_layout], trial);
        if (hits > 0) {
            std::memcpy(out, trial, sizeof(trial));
            return;
        }
        g_layout = -1;
    }

    int best = 0;
    for (uint32_t base : bases) {
        if (!base)
            continue;
        for (int li = 0; li < (int)(sizeof(kLayouts) / sizeof(kLayouts[0])); li++) {
            CmOrigin trial[64]{};
            int hits = ScoreLayout(p, base, kLayouts[li], trial);
            if (hits > best) {
                best = hits;
                g_layout = li;
                g_array_base = base;
                std::memcpy(out, trial, sizeof(trial));
            }
        }
    }
}

static bool ReadName(std::shared_ptr<pProcess> p, uint32_t res, int slot, char* name) {
    std::snprintf(name, 32, "P%d", slot);
    for (int stride : { 8, 4 }) {
        uint32_t np = p->read<uint32_t>(res + offsets::cm::res_name + slot * stride);
        if (np < 0x10000)
            continue;
        char buf[32]{};
        if (!p->read_raw(np, buf, sizeof(buf) - 1))
            continue;
        buf[31] = 0;
        bool ok = buf[0] && std::strlen(buf) < 28;
        for (char* c = buf; ok && *c; c++) {
            if ((unsigned char)*c < 32)
                ok = false;
        }
        if (!ok)
            continue;
        if (std::strstr(buf, "unconnected"))
            continue;
        std::snprintf(name, 32, "%s", buf);
        return true;
    }
    return false;
}

static std::vector<Player> ReadClientMod(std::shared_ptr<pProcess> p, uintptr_t game, const Vec3_t& me, int my_hp) {
    std::vector<Player> list;
    uint32_t res = p->read<uint32_t>(game + offsets::cm::player_res);
    CmOrigin origins[64]{};
    ReadOrigins(p, game, origins);

    if (res > 0x10000) {
        for (int i = 0; i < 64; i++) {
            int hp = p->read<int>(res + offsets::cm::res_hp + i * 4);
            int team = p->read<int>(res + offsets::cm::res_team + i * 4);
            if (hp < 2 || hp > 150 || team < 1 || team > 5)
                continue;
            Player pl;
            pl.index = (int8_t)i;
            pl.health = hp;
            pl.team = team;
            pl.alive = origins[i].ok;
            pl.bot = false;
            ReadName(p, res, i, pl.name);
            if (origins[i].ok)
                pl.pos = origins[i].pos;
            list.push_back(pl);
        }
    }

    std::unordered_map<std::string, size_t> best;
    std::vector<Player> unique;
    for (auto& pl : list) {
        std::string key = pl.name;
        for (char& c : key)
            c = (char)tolower((unsigned char)c);
        bool placeholder = key.size() > 1 && key[0] == 'p'
            && std::all_of(key.begin() + 1, key.end(), [](char ch) { return std::isdigit((unsigned char)ch) != 0; });
        if (placeholder) {
            unique.push_back(pl);
            continue;
        }
        auto it = best.find(key);
        if (it == best.end()) {
            best[key] = unique.size();
            unique.push_back(pl);
        } else if (pl.health > unique[it->second].health) {
            unique[it->second] = pl;
        }
    }

    int local_i = -1;
    float best_d = 150.f * 150.f;
    if (GoodPos(me)) {
        for (int i = 0; i < (int)unique.size(); i++) {
            if (!GoodPos(unique[i].pos))
                continue;
            float d = Dist2(unique[i].pos, me);
            if (d < best_d) {
                best_d = d;
                local_i = i;
            }
        }
    }
    if (local_i < 0 && my_hp > 1) {
        int matches = 0;
        int found = -1;
        for (int i = 0; i < (int)unique.size(); i++) {
            if (unique[i].health == my_hp) {
                matches++;
                found = i;
            }
        }
        if (matches == 1)
            local_i = found;
    }
    if (local_i >= 0)
        unique[local_i].localplayer = true;

    return unique;
}

bool Cache::Refresh() {
    return Get().RefreshImpl();
}

Snapshot Cache::CopySnapshot() {
    std::lock_guard<std::mutex> lock(Get().mtx);
    return {
        Get().game,
        Get().bomb,
        Get().local,
        Get().globals,
        Get().players
    };
}

bool Cache::RefreshImpl() {
    auto p = Engine::GetProcess();
    auto client = Engine::GetClient();

    if (!p || !client.base)
        return false;

    auto now = steady_clock::now();

    if (!game.Update())
        return false;

#ifdef _DEBUG
    if (now - last < (cfg::dev::cache_refresh_rate * 1ms))
        return true;
#else
    if (now - last < 5ms)
        return true;
#endif

    // ClientMod path: resource + array origins (no CS2 entity list)
    auto scan = ReadClientMod(p, client.base, game.local_pos, game.local_hp);

    Player local_pl{};
    for (auto& pl : scan) {
        if (pl.localplayer) {
            local_pl = pl;
            break;
        }
    }

    {
        std::lock_guard<std::mutex> lock(mtx);
        players = std::move(scan);
        local = local_pl;
        duration = duration_cast<std::chrono::milliseconds>(last - now);
        last = now;
    }

    return true;
}
