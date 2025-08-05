#include <windows.h>
#include <tlhelp32.h>
#include <vector>
#include <iostream>
#include <thread>

std::vector<BYTE> pattern = {
    0x00, 0x00, 0x80, 0x3F, 0x00, 0x00, 0x00, 0x3F,
    0x6F, 0x12, 0x83, 0x3A, 0x00
};

DWORD GetProcessIdByName(const wchar_t* processName) {
    PROCESSENTRY32W entry = {};
    entry.dwSize = sizeof(entry);
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snapshot == INVALID_HANDLE_VALUE) return 0;

    if (Process32FirstW(snapshot, &entry)) {
        do {
            if (_wcsicmp(entry.szExeFile, processName) == 0) {
                CloseHandle(snapshot);
                return entry.th32ProcessID;
            }
        } while (Process32NextW(snapshot, &entry));
    }

    CloseHandle(snapshot);
    return 0;
}

uintptr_t ScanMemory(HANDLE hProcess, const std::vector<BYTE>& pattern) {
    SYSTEM_INFO sysInfo;
    GetSystemInfo(&sysInfo);

    MEMORY_BASIC_INFORMATION mbi;
    uintptr_t addr = (uintptr_t)sysInfo.lpMinimumApplicationAddress;

    while (addr < (uintptr_t)sysInfo.lpMaximumApplicationAddress) {
        if (VirtualQueryEx(hProcess, (LPCVOID)addr, &mbi, sizeof(mbi))) {
            if (mbi.State == MEM_COMMIT && (mbi.Protect & PAGE_READWRITE)) {
                std::vector<BYTE> buffer(mbi.RegionSize);
                SIZE_T bytesRead;
                if (ReadProcessMemory(hProcess, mbi.BaseAddress, buffer.data(), mbi.RegionSize, &bytesRead)) {
                    for (SIZE_T i = 0; i < bytesRead - pattern.size(); ++i) {
                        if (memcmp(buffer.data() + i, pattern.data(), pattern.size()) == 0) {
                            return (uintptr_t)mbi.BaseAddress + i;
                        }
                    }
                }
            }
            addr += mbi.RegionSize;
        } else {
            break;
        }
    }

    return 0;
}

int main() {
    const wchar_t* processName = L"Minecraft.Windows.exe";

    DWORD pid = GetProcessIdByName(processName);
    if (!pid) {
        std::cerr << "[-] Process not found.\n";
        return 1;
    }

    HANDLE hProcess = OpenProcess(PROCESS_ALL_ACCESS, FALSE, pid);
    if (!hProcess || hProcess == INVALID_HANDLE_VALUE) {
        std::cerr << "[-] Failed to open process.\n";
        return 1;
    }

    std::cout << "[*] Press K to apply fullbright...\n";

    while (true) {
        if (GetAsyncKeyState('K') & 1) {
            uintptr_t addr = ScanMemory(hProcess, pattern);
            if (addr) {
                float newValue = 100.0f;
                SIZE_T written;
                if (WriteProcessMemory(hProcess, (LPVOID)addr, &newValue, sizeof(newValue), &written)) {
                    std::cout << "[+] Patched value at: " << std::hex << addr << "\n";
                } else {
                    std::cerr << "[-] Write failed.\n";
                }
            } else {
                std::cerr << "[-] Pattern not found.\n";
            }
        }
    }

    CloseHandle(hProcess);
    return 0;
}
