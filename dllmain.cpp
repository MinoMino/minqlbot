/*
minqlbot - A Quake Live server administrator bot.
Copyright (C) Mino <mino@minomino.org>

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

// dllmain.cpp : Defines the entry point for the DLL application.
#include "common.h"
#include "debug_utils.h"
#include "hook_utils.h"
#include "quake.h"
#include "python.h"

void HandleAttach(HMODULE hModule);
void HandleDetach();

HANDLE main_thread;
HMODULE this_module;

BOOL APIENTRY DllMain( HMODULE hModule,
                       DWORD  ul_reason_for_call,
                       LPVOID lpReserved )
{
  switch (ul_reason_for_call) {
  case DLL_PROCESS_ATTACH:
    HandleAttach(hModule);
    break;
  case DLL_THREAD_ATTACH:
    break;
  case DLL_THREAD_DETACH:
    break;
  case DLL_PROCESS_DETACH:
    HandleDetach();
    break;
  }

  return TRUE;
}

void HandleAttach(HMODULE hModule) {
  this_module = hModule;
  main_thread = CreateThread(NULL, NULL, (LPTHREAD_START_ROUTINE)quake::MainThread, hModule, NULL, NULL);
  HMODULE hmod;
  GetModuleHandleEx(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS, (LPCTSTR)hModule, &hmod);
}

void HandleDetach() {
  if (Py_IsInitialized()) {
    DOUT << "Finalizing Python environment..." << std::endl;
    quake::python::Finalize();
    DOUT << "Python finalized!" << std::endl;
  }
  DOUT << "Module unloaded!" << std::endl;
}

DLLEXPORT const char * GetMinqlbotVersion() {
  return MINQLBOT_VERSION;
}