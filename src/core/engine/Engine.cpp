#include "Engine.hpp"

#include "core/offsets/Dumper.hpp"
#include "core/engine/cache/Cache.hpp"

#include <TlHelp32.h>

static DWORD FindClientModPid()
{
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE)
        return 0;

    PROCESSENTRY32W pe{};
    pe.dwSize = sizeof(pe);
    DWORD found = 0;

    if (Process32FirstW(snap, &pe)) {
        do {
            if (_wcsicmp(pe.szExeFile, L"CMLauncher.exe") != 0)
                continue;

            HANDLE mods = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pe.th32ProcessID);
            if (mods == INVALID_HANDLE_VALUE)
                continue;

            MODULEENTRY32W me{};
            me.dwSize = sizeof(me);
            bool ok = false;
            if (Module32FirstW(mods, &me)) {
                do {
                    if (!_wcsicmp(me.szModule, L"clientmod_game.dll")) {
                        ok = true;
                        break;
                    }
                } while (Module32NextW(mods, &me));
            }
            CloseHandle(mods);
            if (ok) {
                found = pe.th32ProcessID;
                break;
            }
        } while (Process32NextW(snap, &pe));
    }

    CloseHandle(snap);
    return found;
}

bool Engine::Init() {
    return GetInstance().InitImpl();
}

ProcessModule Engine::GetClient() {
    return GetInstance().client;
}

ProcessModule Engine::GetEngine() {
    return GetInstance().engine;
}

std::shared_ptr<pProcess> Engine::GetProcess() {
    return GetInstance().process;
}

bool Engine::InitImpl() {
    process = std::make_shared<pProcess>();

    if (!this->AwaitProcess()) {
        LOGF(FATAL, "Could not find process, please make sure the game is open");
        return false;
    }

    if (!this->AwaitModules()) {
        LOGF(FATAL, "Game took too long to load, please open me again once its fully loaded");
        return false;
    }

    if (!Dumper::Init()) {
        LOGF(FATAL, "Failed to dump game offsets");
        return false;
    }

    if (!Config::Read())
        LOGF(WARNING, "Failed to parse config, using default values");

#ifdef _DEBUG
    if (!cfg::dev::console)
        LogHelper::Free();
#endif

    std::thread(&Engine::Thread, this).detach();

    LOGF(INFO, "Successfully initialized engine (ClientMod)...");
    return true;
}

void Engine::Thread() {
    while (true) {
        auto start = steady_clock::now();

        Cache::Refresh();

        if (cfg::settings::free_cpu)
            std::this_thread::sleep_until(start + 1ms);
    }
}

bool Engine::AwaitProcess() {
    if (!process || process->handle_)
        return false;

    do {
        DWORD pid = FindClientModPid();
        if (pid && process->AttachPid(pid))
            break;

        if (pid && !process->handle_) {
            LOGF(FATAL, "Insufficient permissions to open CMLauncher. Run as Administrator.");
            return false;
        }

        static int attempts = 0;

        if (!attempts)
            LOGF(INFO, "Waiting 50s for CMLauncher (clientmod_game.dll) ...");

        if (attempts > 10)
            return false;
        attempts++;

        std::this_thread::sleep_for(5s);
    } while (true);

    return true;
}

bool Engine::AwaitModules() {
    if (!process || !process->handle_)
        return false;

    LOGF(INFO, "Waiting for clientmod modules...");

    do {
        this->client = process->GetModule("clientmod_game.dll");
        this->engine = process->GetModule("clientmod_client.dll");
        if (!this->engine.base)
            this->engine = this->client;

        if (this->client.base)
            break;

        static int attempts = 0;
        if (attempts > 10)
            return false;
        attempts++;

        std::this_thread::sleep_for(5s);
    } while (true);

    LOGF(INFO, "clientmod_game.dll @ 0x{:X}", this->client.base);
    return true;
}
