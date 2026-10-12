# ClientMod ESP (این فورک)

این فورک برای **CMLauncher / clientmod_game.dll** تنظیم شده.

## EXE (C++ / اورلی روی بازی)

- پروسه: `CMLauncher.exe` که `clientmod_game.dll` دارد
- منوی ImGui همان پروژه (باکس، HP، اسم، کالیبره FOV/EyeZ/Yaw/Pitch)
- ماتریس از yaw/pitch + موقعیت خودت ساخته می‌شود
- بازیکن‌ها از PlayerResource + آرایه `0x26B2364`

ساخت: Actions → آخرین بیلد Release، یا Visual Studio `x64 | Release`.

**Run as Administrator** · بازی Windowed / Borderless · داخل مپ

## پایتون (تست)

[`python/clientmod_esp.py`](python/clientmod_esp.py)

---

# 🕹️ CS2 External ESP | Recode

Simple external ESP for Counter-Strike 2. After years of development the codebase has been modernized for clarity and ease of use, featuring a redesigned interface, noticeable performance improvements, several quality-of-life additions, and automatic offset scanning to help maintain compatibility through game updates.

## Showcase

> Click the picture below to go to the showcase video

[![cs2esp](.github/showcase.png)](https://youtu.be/3WHHLUyHyzA)

## 🌳 Simple Use

- You can download it from [**Releases**](https://github.com/IMXNOOBX/cs2-external-esp/releases) tab or **build it yourself** by following [developers instructions](#-developer-instructions).
- Open the game & the `cs2-external-esp.exe`, and thats it!
- **Star** the repository **if** you **like the project**! ⭐⭐⭐

> If the app crashes on startup, you may be missing the latest [Windows Visual C++ redistributables](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170#latest-supported-redistributable-version). Install the appropriate package for your system:
>
> - [64-bit Windows](https://aka.ms/vc14/vc_redist.x64.exe) *for most modern systems*
> - [32-bit](https://aka.ms/vc14/vc_redist.x86.exe) *for older devices*


> [!IMPORTANT]
> Make sure your game is in full screen windowed❗

## 💡 Important

> This project is provided *'as is'* for learning purposes with no warranties or responsibility from the developers/contributors. Use it at your own risk; you are the only one accountable for your actions

* **Detection Status:** This project is intended solely for single-player use. That said, no ban reports have been raised for other modes.
* **Anti-Virus Alerts:** This software may resemble malware in behavior because it accesses other processes memory, so it is commonly flagged by anti‑virus programs. I strongly encourage you to read the source code and build it yourself by following the [developers instructions](#-developer-instructions). All provided binaries are compiled via the [GitHub workflow](.github/workflows/auto_build.yml) from the repository source.

## 🕹️ Previous Versions

> This project has been reworked **3 times**, the current one been the third!

* [Discord Overlay (2023)](https://github.com/IMXNOOBX/cs2-external-esp/tree/discord-overlay) is the first and the **simplest** version of all, great to start learning.
* [Gdi Overlay (2023-2025)](https://github.com/IMXNOOBX/cs2-external-esp/tree/gdi-overlay) is an **improved version**, featuring automatic offset updating & configurations
* [Modern Version (Today)](https://github.com/IMXNOOBX/cs2-external-esp/tree/main) is the current and the **latest version**, with a click ui, automatic offset scanning and more!

## 📘 Developer Instructions

> - This project is mirrored in the following locations.
>	 - **GitHub**: [*github.com/IMXNOOBX/cs2-external-esp*](https://github.com/IMXNOOBX/cs2-external-esp) (main)
>	 - **GitLab**: [*gitlab.com/IMXNOOBX/cs2-external-esp*](https://gitlab.com/IMXNOOBX/cs2-external-esp) (mirror)
>	 - **CodeBerg**: [*codeberg.org/IMXNOOBX/cs2-external-esp*](https://codeberg.org/IMXNOOBX/cs2-external-esp) (mirror)

1. Clone repository. Make sure you copy the command below to clone dependencies too

```sh
git clone --recursive https://github.com/IMXNOOBX/cs2-external-esp
```

* If you cloned the repository before submodules were added, run this command `git submodule update --init --recursive`

2. Build the app using **Visual Studio 2022** (or later)
	- Build: **`x64 - Release`**

3. Locate your binary file in the folder `<arch>/<configuration>`, e.g., `x64/Release`.
