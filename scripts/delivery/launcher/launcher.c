/* 密证 CredProof launcher (DUIDUI队).
 *
 * A thin, auditable wrapper: it runs start-credproof.cmd from its own folder in
 * the same console window and returns its exit code. It does not contain the
 * program, download anything, change settings or require administrator rights.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wchar.h>

static BOOL WINAPI keep_waiting(DWORD event)
{
    /* Ctrl+C / Ctrl+Break reach the server too; it shuts down and cleans up.
       The launcher only waits for it (handlers are not inherited by children). */
    return event == CTRL_C_EVENT || event == CTRL_BREAK_EVENT;
}

int wmain(void)
{
    wchar_t self[MAX_PATH * 4], folder[MAX_PATH * 4], script[MAX_PATH * 4], command[MAX_PATH * 4 + 64];
    DWORD length = GetModuleFileNameW(NULL, self, (DWORD)(sizeof self / sizeof self[0]));
    if (length == 0 || length >= sizeof self / sizeof self[0]) return 2;
    wcscpy(folder, self);
    wchar_t *slash = wcsrchr(folder, L'\\');
    if (!slash) return 2;
    *slash = L'\0';
    _snwprintf(script, sizeof script / sizeof script[0], L"%ls\\start-credproof.cmd", folder);
    if (GetFileAttributesW(script) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL, L"没有找到 start-credproof.cmd。\n请先把压缩包完整解压，再从解压后的文件夹中运行本程序。",
                    L"密证 CredProof", MB_OK | MB_ICONWARNING);
        return 2;
    }
    SetConsoleTitleW(L"密证 CredProof（关闭本窗口或按 Ctrl+C 停止）");
    SetConsoleCtrlHandler(keep_waiting, TRUE);
    _snwprintf(command, sizeof command / sizeof command[0], L"cmd.exe /d /c \"\"%ls\"\"", script);
    STARTUPINFOW startup = { sizeof startup };
    PROCESS_INFORMATION process;
    if (!CreateProcessW(NULL, command, NULL, NULL, FALSE, 0, NULL, folder, &startup, &process)) {
        MessageBoxW(NULL, L"无法启动 start-credproof.cmd，请直接双击该文件运行。", L"密证 CredProof", MB_OK | MB_ICONERROR);
        return 2;
    }
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return (int)code;
}
