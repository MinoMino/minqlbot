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

#pragma once

#include "common.h"

namespace hook_utils {

// Structs, enums, etc.
typedef struct Protect_ Protect;

DWORD GetImageSize(HMODULE module);

// Memory access, writing, etc.
BOOL WriteMemory(LPVOID address, LPVOID buffer, SIZE_T size);
BOOL WriteMemory(LPVOID address, DWORD buffer);
Protect ProtectRemove(LPVOID address, SIZE_T size);
BOOL ProtectRestore(Protect * old_protect);

// Bit searching, comparison, etc.
DWORD FindPattern(void * address, DWORD search_length, const char * pattern, const char * mask);
DWORD FindPatternSafe(LPVOID address, DWORD search_length, LPVOID pattern, char * mask);

// Function detouring, hot patching, etc.

// Miscellaneous functions.
HMODULE WaitForModule(wchar_t * module);

} // Namespace hook_utils
