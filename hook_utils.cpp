/*
minqlbot - A Quake Live server administrator bot.
Copyright (C) 2015 Mino <mino@minomino.org>

This file is part of minqlbot.

minqlbot is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

minqlbot is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with minqlbot. If not, see <http://www.gnu.org/licenses/>.
*/

#include "hook_utils.h"
#include <Psapi.h>

namespace hook_utils {

// Structs, enums, etc.
struct Protect_ {
  LPVOID lpAddress;
  SIZE_T dwSize;
  DWORD oldProtect;
  BOOL result;
};

DWORD GetImageSize(HMODULE module) {
  MODULEINFO info;
  if (!GetModuleInformation(GetCurrentProcess(), module, &info, sizeof(info))) {
    return 0;
  }

    return info.SizeOfImage;
}

// Memory access, writing, etc.
BOOL WriteMemory(LPVOID lpAddress, LPVOID lpBuffer, SIZE_T dwSize) {
  Protect protect = ProtectRemove(lpAddress, dwSize);
  if (protect.result) {
    memcpy(lpAddress, lpBuffer, dwSize);
    ProtectRestore(&protect);
    return TRUE;
  }

  return FALSE;
}

BOOL WriteMemory(LPVOID lpAddress, DWORD dwBuffer) {
  return WriteMemory(lpAddress, &dwBuffer, sizeof(dwBuffer));
}

Protect ProtectRemove(LPVOID lpAddress, SIZE_T dwSize) {
  Protect oldProt;
  oldProt.lpAddress = lpAddress;
  oldProt.dwSize = dwSize;
  oldProt.result = 
    VirtualProtect(lpAddress, dwSize, PAGE_EXECUTE_READWRITE, &oldProt.oldProtect);

  return oldProt;
}

BOOL ProtectRestore(Protect * oldProt) {
  return VirtualProtect(oldProt->lpAddress,
              oldProt->dwSize,
              oldProt->oldProtect,
              &(oldProt->oldProtect));
}

// Bit searching, comparison, etc.
DWORD FindPattern(void * lpAddress, DWORD dwLength, const char * lpPattern, const char * szMask) {
  for (DWORD i = 0; i < dwLength; i++) {
    for (int j = 0; szMask[j]; j++) {
      if (szMask[j] == 'X' && ((LPBYTE)lpPattern)[j] != ((LPBYTE)lpAddress)[i + j]) {
        break;
      }
      else if (szMask[j + 1]) {
        continue;
      }

      return (DWORD)(((LPBYTE)lpAddress) + i);
    }
  }
  return NULL;
}

// Slower, but will avoid access violations.
DWORD FindPatternSafe(LPVOID lpAddress, DWORD dwLength, LPVOID lpPattern, char * szMask) {
  MEMORY_BASIC_INFORMATION memInfo;
  DWORD dwPatternLength = strlen(szMask);
  DWORD dwFoundPattern = 0;
  VirtualQuery(lpAddress, &memInfo, sizeof(memInfo));
  DWORD dwStart = (DWORD)memInfo.BaseAddress;
  DWORD dwPrev = 0;

  for (DWORD dwCounter = 0; dwCounter < dwLength;) {
    VirtualQuery((void *)(dwStart + dwCounter), &memInfo, sizeof(memInfo));

    if (dwPrev != (DWORD)memInfo.BaseAddress && memInfo.BaseAddress && 
        memInfo.State == MEM_COMMIT && !(memInfo.Protect & PAGE_EXECUTE ||
        memInfo.Protect & PAGE_NOACCESS || memInfo.Protect & PAGE_WRITECOPY ||
        memInfo.Protect & PAGE_GUARD))
    {
      dwFoundPattern = FindPattern((LPBYTE)memInfo.BaseAddress,
        memInfo.RegionSize - dwPatternLength, (char *)lpPattern, szMask);

      if (dwFoundPattern) {
        return dwFoundPattern;
      }

      dwPrev = (DWORD)memInfo.BaseAddress;
      dwCounter = (dwPrev + memInfo.RegionSize) - dwStart;
      continue;
    }

    dwCounter += 0xFFF;
  }

  return NULL;
}

// Miscellaneous functions.
HMODULE WaitForModule(wchar_t * module) {
  HMODULE hModule = GetModuleHandleW(module);

  while (!hModule) {
    Sleep(100);
    hModule = GetModuleHandleW(module);
  }

  return hModule;
}

} // Namespace hook_utils