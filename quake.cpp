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

#include "quake.h"
#include <MinHook.h>
#include <TlHelp32.h>
#include <Psapi.h>
#include <string>
#include <regex>
#include <vector>
#include <tuple>
#include <queue>
#include "debug_utils.h"
#include "hook_utils.h"
#include "python.h"

const unsigned int LOOPS_BEFORE_SEND = (int)DELAY_SEND_COMMAND / DELAY_MAIN_LOOP;

// Patterns, masks and offsets for our function finder.
const char PATTERN_PARSESERVERMESSAGE[] = "\x55\x8B\xEC\xA1\x00\x00\x00\x00\x8B\x40\x2C\x56\x57\x8B\x7D\x08\x83\xF8\x01\x75\x13";
const char MASK_PARSESERVERMESSAGE[]    = "XXXX----XXXXXXXXXXXXX";
const int OFFSET_PARSESERVERMESSAGE     = 0x0;

const char PATTERN_PARSECOMMANDSTRING[] = "\x55\x8B\xEC\x56\x8B\x75\x08\x6A\x20\x56\xE8\x00\x00\x00\x00\x8B\x4E\x14\x83\xC4\x08\x3B\x4E\x10";
const char MASK_PARSECOMMANDSTRING[]    = "XXXXXXXXXXX----XXXXXXXXX";
const int OFFSET_PARSECOMMANDSTRING     = 0x0;

const char PATTERN_PARSEGAMESTATE[]     = "\x55\x8B\xEC\x81\xEC\x68\x01\x00\x00\xA1\x00\x00\x00\x00\x33\xC5\x89\x45\xFC\x57\x8B\x7D\x08";
const char MASK_PARSEGAMESTATE[]        = "XXXXXXXXXX----XXXXXXXXX";
const int OFFSET_PARSEGAMESTATE         = 0x0;

const char PATTERN_READBIGSTRING[]      = "\x55\x8B\xEC\x53\x56\x57\x8B\x7D\x08\x33\xDB\x33\xF6\x8D\x49\x00\x6A\x08\x57\xE8\x00\x00\x00\x00\x8B\x4F\x14\x83\xC4\x08\x0F\xB6\xC0\x3B\x4F\x10\x7E\x03\x83\xC8\xFF\x83\xF8\xFF\x74\x1D\x3B\xC3\x74\x19\x83\xF8\x25\x75\x05\xB8\x2E\x00\x00\x00";
const char MASK_READBIGSTRING[]         = "XXXXXXXXXXXXXXXXXXXX----XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX";
const int OFFSET_READBIGSTRING          = 0x0;

const char PATTERN_READSHORT[]          = "\x55\x8B\xEC\x56\x8B\x75\x08\x6A\x10\x56\xE8\x00\x00\x00\x00\x8B\x4E\x14\x83\xC4\x08\x3B\x4E\x10\x98\x5E\x7E\x03\x83\xC8\xFF";
const char MASK_READSHORT[]             = "XXXXXXXXXXX----XXXXXXXXXXXXXXXX";
const int OFFSET_READSHORT              = 0x0;

const char PATTERN_ADDRELIABLECOMMAND[] = "\x8B\x55\x08\x40\xA3\x00\x00\x00\x00\x83\xE0\x3F\x68\x00\x04\x00\x00\xC1\xE0\x0A\x52\x05";
const char MASK_ADDRELIABLECOMMAND[]    = "XXXXX----XXXXXXXXXXXXX";
const int OFFSET_ADDRELIABLECOMMAND     = -0x29;

const char PATTERN_ADDCOMMAND[]         = "\x55\x8B\xEC\xA1\x00\x00\x00\x00\x56\x57\x8B\x7D\x08\x8B\xF0\x85\xC0\x74\x34\x8B\x4E\x04\x8B\xC7";
const char MASK_ADDCOMMAND[]            = "XXXX----XXXXXXXXXXXXXXXX";
const int OFFSET_ADDCOMMAND             = 0x0;

const char PATTERN_REMOVECOMMAND[]      = "\x55\x8B\xEC\x56\x8B\x35\x00\x00\x00\x00\x57\xBF\x00\x00\x00\x00\x85\xF6\x74\x60\x53\x8B\x5D\x08";
const char MASK_REMOVECOMMAND[]         = "XXXXXX----XX----XXXXXXXX";
const int OFFSET_REMOVECOMMAND          = 0x0;

const char PATTERN_ARGS[]               = "\x53\xBB\x01\x00\x00\x00\xC6\x05\x00\x00\x00\x00\x00\x39\x1D\x00\x00\x00\x00\x7E\x6E\x56\x57\xEB\x07";
const char MASK_ARGS[]                  = "XXXXXXXX----XXX----XXXXXX";
const int OFFSET_ARGS                   = 0x0;

const char PATTERN_CONSOLEPRINT[]       = "\x55\x8B\xEC\x83\xEC\x54\xA1\x00\x00\x00\x00\x33\xC5\x89\x45\xFC\x53\x57\x8B\x7D\x08\x6A\x0C\x68";
const char MASK_CONSOLEPRINT[]          = "XXXXXXX----XXXXXXXXXXXXX";
const int OFFSET_CONSOLEPRINT           = 0x0;

const char PATTERN_CONFIGSTRINGS[]      = "\x83\x3D\x00\x00\x00\x00\x08\x74\x0E\x68\x00\x00\x00\x00\xE8\x00\x00\x00\x00\x83\xC4\x04\xC3\x56\x33\xF6\x8D\x9B\x00\x00\x00\x00";
const char MASK_CONFIGSTRINGS[]         = "XX----XXXX----X----XXXXXXXXXXXXX";
const int OFFSET_CONFIGSTRINGS          = 0x0;

const char PATTERN_CVARFINDVAR[]        = "\x55\x8B\xEC\x56\x57\x8B\x7D\x08\x8B\xC7\xE8\x00\x00\x00\x00\x8B\x34\x85\x00\x00\x00\x00\x85\xF6\x74\x1D";
const char MASK_CVARFINDVAR[]           = "XXXXXXXXXXX----XXX----XXXX";
const int OFFSET_CVARFINDVAR            = 0x0;

const char PATTERN_EXECUTESTRING[]      = "\x55\x8B\xEC\x53\x8B\x5D\x08\x53\xE8\x00\x00\x00\x00\x83\xC4\x04\x83\x3D\x00\x00\x00\x00\x00\x0F";
const char MASK_EXECUTESTRING[]         = "XXXXXXXXX----XXXXX----XX";
const int OFFSET_EXECUTESTRING          = 0x0;




namespace quake {
clientConnection_t * clc;
void * qlbase;
UINT32 * configstrings;
// The first element in the client static struct is the connection status,
// so we simply assign it the address of the struct. At least until we
// need the client static struct for something else later.
UINT32 * connection_status;

void * parseservermessage_addr;
void * parsecommandstring_addr;
void * parsegamestate_addr;
void * readbigstring_addr;
void * readshort_addr;
void * addreliablecommand_addr;
void * addcommand_addr;
void * removecommand_addr;
void * args_addr;
void * consoleprints_addr;
void * configstrings_addr;
void * cvarfind_addr;
void * executestring_addr;
ParseServerMessage OParseServerMessage;
ParseCommandString OParseCommandString;
ParseGamestate OParseGamestate;
ReadBigString OReadBigString;
ReadShort OReadShort;
AddReliableCommand OAddReliableCommand;
AddCommand OAddCommand;
RemoveCommand ORemoveCommand;
GetArgs OGetArgs;
ConsolePrint OConsolePrint;
CvarFind OCvarFind;
ExecuteString OExecuteString;

bool hooked = false;
int lastSeq; // The sequence of the last acknowledged server command.
bool in_parse_gamestate = false;
int gamestate_configstring_index = 0;

std::vector< std::tuple<std::string, std::string, GenericHandler> > commands;

std::queue< const std::string > message_queue; // Outgoing message queue.
HANDLE command_queue_stop_event;
HANDLE command_queue_mutex;
HANDLE restart_python_event;

DWORD WINAPI MainThread(HMODULE module_handle) {
  // Find functions
  DOUT << "Searching for necessary functions..." << std::endl;
  if (!FindFunctions()) {
    DERR << "Failed to find necessary functions." << std::endl;
    FreeLibraryAndExitThread(module_handle, 1);
  }

  // Init
  DOUT << "Initializing function pointers..." << std::endl;
  if (!Initialize()) {
    DERR << "Failed to initialize function pointers." << std::endl;
    FreeLibraryAndExitThread(module_handle, 1);
  }

  // Run our Python script.
  DOUT << "Initializing Python environment..." << std::endl;
  int pyres = python::Initialize();
  if (pyres) {
    DERR << "Python initialization returned error code: " << pyres << std::endl;
    DOUT << "Finalizing Python and exiting..." << std::endl;
    python::Finalize();
    FreeLibraryAndExitThread(module_handle, 1);
  }

  // Hook
  DOUT << "Hooking functions..." << std::endl;
  if (!HookAll()) {
    DERR << "Failed to hook functions." << std::endl;
    FreeLibraryAndExitThread(module_handle, 1);
  }
  else hooked = true;

  // Add a console command to QL.
  AddConsoleInterface();

  // A small message to the console to confirm injection.
  char welcome_msg[128];
  sprintf_s(welcome_msg,
    "^4minqlbot ^7%s <^4http://minomino.org/^7>\nUse '\\bot help' for a command list\n", GetMinqlbotVersion());
  OConsolePrint(welcome_msg);

  DOUT << "Entering the main loop..." << std::endl;
  command_queue_stop_event = CreateEvent(NULL, TRUE, FALSE, TEXT("command_queue_stop_event"));
  command_queue_mutex = CreateMutex(NULL, FALSE, NULL);
  restart_python_event = CreateEvent(NULL, TRUE, FALSE, TEXT("restart_python_event"));
  MainLoop(command_queue_stop_event, command_queue_mutex, restart_python_event);

  CleanUp();
  FreeLibraryAndExitThread(module_handle, 0);
}

void CleanUp() {
  quake::RemoveConsoleInterface();

  DOUT << "Unhooking functions..." << std::endl;
  if (hooked && !quake::UnhookAll()) {
    DOUT << "Failed to unhook functions." << std::endl;
  }

  if (Py_IsInitialized() && !python::handle_unload.is_none()) {
    DOUT << "Calling Python clean-up function..." << std::endl;
    python::ScopedGILAcquire gil;
    try {
      // Call our Python handler.
      python::handle_unload();
    }
    catch (boost::python::error_already_set &) {
      std::string err = python::get_error_traceback();
      python::output_debug_lines(err);
    }
  }

  DOUT << "Cleanup complete. The module can now be safely unloaded!" << std::endl;
}

bool Initialize() {
  qlbase = GetModuleHandle(NULL);
  if (qlbase == NULL) return false;

  // Get global structs
  void * server_cmds = *((void **)((int)parseservermessage_addr + STRUCT_OFFSET_PSERVERCOMMANDS));
  clc = (clientConnection_t *)((int)server_cmds - OFFDIFF_CLC_SERVERCMDS);
  connection_status = *((UINT32 **)((int)configstrings_addr + STRUCT_OFFSET_PCLIENTSTATIC));
  configstrings = *((UINT32 **)((int)configstrings_addr + STRUCT_OFFSET_PCONFIGSTRINGS));
  lastSeq = clc->serverCommandSequence;

  if (!hooked) { // Might have to recall this function after hooking.
    //parseservermessage_addr = (void *)((int)qlbase + F_PARSESERVERMESSAGE);
    //parsecommandstring_addr = (void *)((int)qlbase + F_PARSECOMMANDSTRING);
    //parsegamestate_addr = (void *)((int)qlbase + F_PARSEGAMESTATE);
    //readbigstring_addr = (void *)((int)qlbase + F_READBIGSTRING);
    //addreliablecommand_addr = (void *)((int)qlbase + F_ADDRELIABLECOMMAND);
  
    //OAddReliableCommand = (AddReliableCommand)addreliablecommand_addr;
    OAddCommand = (AddCommand)addcommand_addr;
    ORemoveCommand = (RemoveCommand)removecommand_addr;
    OGetArgs = (GetArgs)args_addr;
    OCvarFind = (CvarFind)cvarfind_addr;
    OExecuteString = (ExecuteString)executestring_addr;
    //OConsolePrint = (ConsolePrint)consoleprints_addr;
  }

  return true;
}

bool FindFunctions() {
  qlbase = GetModuleHandle(NULL);
  DWORD qlsize = hook_utils::GetImageSize((HMODULE)qlbase);
  bool failed = false;

  if (!qlsize) {
    DERR << "Failed to get image size of Quake Live." << std::endl;
    failed = true;
  }

  parseservermessage_addr =
    (void *)(hook_utils::FindPattern(qlbase, qlsize, PATTERN_PARSESERVERMESSAGE, MASK_PARSESERVERMESSAGE) + OFFSET_PARSESERVERMESSAGE);
  if (!parseservermessage_addr) {
    DERR << "Failed to find CL_ParseServerMessage." << std::endl;
    failed = true;
  }
  else DOUT << "CL_ParseServerMessage: base + " << (void *)((DWORD)parseservermessage_addr - (DWORD)qlbase) << std::endl;

  parsecommandstring_addr =
    (void *)(hook_utils::FindPattern(qlbase, qlsize, PATTERN_PARSECOMMANDSTRING, MASK_PARSECOMMANDSTRING) + OFFSET_PARSECOMMANDSTRING);
  if (!parsecommandstring_addr) {
    DERR << "Failed to find CL_ParseCommandString." << std::endl;
    failed = true;
  }
  else DOUT << "CL_ParseCommandString: base + " << (void *)((DWORD)parsecommandstring_addr - (DWORD)qlbase) << std::endl;

  parsegamestate_addr =
    (void *)(hook_utils::FindPattern(qlbase, qlsize, PATTERN_PARSEGAMESTATE, MASK_PARSEGAMESTATE) + OFFSET_PARSEGAMESTATE);
  if (!parsegamestate_addr) {
    DERR << "Failed to find CL_ParseGamestate." << std::endl;
    failed = true;
  }
  else DOUT << "CL_ParseGamestate: base + " << (void *)((DWORD)parsegamestate_addr - (DWORD)qlbase) << std::endl;

  readbigstring_addr =
    (void *)(hook_utils::FindPattern(qlbase, qlsize, PATTERN_READBIGSTRING, MASK_READBIGSTRING) + OFFSET_READBIGSTRING);
  if (!readbigstring_addr) {
    DERR << "Failed to find MSG_ReadBigString." << std::endl;
    failed = true;
  }
  else DOUT << "MSG_ReadBigString: base + " << (void *)((DWORD)readbigstring_addr - (DWORD)qlbase) << std::endl;

  readshort_addr =
    (void *)(hook_utils::FindPattern(qlbase, qlsize, PATTERN_READSHORT, MASK_READSHORT) + OFFSET_READSHORT);
  if (!readshort_addr) {
    DERR << "Failed to find MSG_ReadShort." << std::endl;
    failed = true;
  }
  else DOUT << "MSG_ReadShort: base + " << (void *)((DWORD)readshort_addr - (DWORD)qlbase) << std::endl;

  addreliablecommand_addr =
    (void *)(hook_utils::FindPattern(qlbase, qlsize, PATTERN_ADDRELIABLECOMMAND, MASK_ADDRELIABLECOMMAND) + OFFSET_ADDRELIABLECOMMAND);
  if (!addreliablecommand_addr) {
    DERR << "Failed to find CL_AddReliableCommand." << std::endl;
    failed = true;
  }
  else DOUT << "CL_AddReliableCommand: base + " << (void *)((DWORD)addreliablecommand_addr - (DWORD)qlbase) << std::endl;

  addcommand_addr =
    (void *)(hook_utils::FindPattern(qlbase, qlsize, PATTERN_ADDCOMMAND, MASK_ADDCOMMAND) + OFFSET_ADDCOMMAND);
  if (!addcommand_addr) {
    DERR << "Failed to find Cmd_AddCommand." << std::endl;
    failed = true;
  }
  else DOUT << "Cmd_AddCommand: base + " << (void *)((DWORD)addcommand_addr - (DWORD)qlbase) << std::endl;

  removecommand_addr =
    (void *)(hook_utils::FindPattern(qlbase, qlsize, PATTERN_REMOVECOMMAND, MASK_REMOVECOMMAND) + OFFSET_REMOVECOMMAND);
  if (!removecommand_addr) {
    DERR << "Failed to find Cmd_RemoveCommand." << std::endl;
    failed = true;
  }
  else DOUT << "Cmd_RemoveCommand: base + " << (void *)((DWORD)removecommand_addr - (DWORD)qlbase) << std::endl;

  args_addr =
    (void *)(hook_utils::FindPattern(qlbase, qlsize, PATTERN_ARGS, MASK_ARGS) + OFFSET_ARGS);
  if (!args_addr) {
    DERR << "Failed to find Cmd_Args." << std::endl;
    failed = true;
  }
  else DOUT << "Cmd_Args: base + " << (void *)((DWORD)args_addr - (DWORD)qlbase) << std::endl;

  consoleprints_addr =
    (void *)(hook_utils::FindPattern(qlbase, qlsize, PATTERN_CONSOLEPRINT, MASK_CONSOLEPRINT) + OFFSET_CONSOLEPRINT);
  if (!consoleprints_addr) {
    DERR << "Failed to find CL_ConsolePrint." << std::endl;
    failed = true;
  }
  else DOUT << "CL_ConsolePrint: base + " << (void *)((DWORD)consoleprints_addr - (DWORD)qlbase) << std::endl;

  configstrings_addr =
    (void *)(hook_utils::FindPattern(qlbase, qlsize, PATTERN_CONFIGSTRINGS, MASK_CONFIGSTRINGS) + OFFSET_CONFIGSTRINGS);
  if (!configstrings_addr) {
    DERR << "Failed to find configstrings (function)." << std::endl;
    failed = true;
  }
  else DOUT << "configstrings (function): base + " << (void *)((DWORD)configstrings_addr - (DWORD)qlbase) << std::endl;

  cvarfind_addr =
    (void *)(hook_utils::FindPattern(qlbase, qlsize, PATTERN_CVARFINDVAR, MASK_CVARFINDVAR) + OFFSET_CVARFINDVAR);
  if (!cvarfind_addr) {
    DERR << "Failed to find Cvar_FindVar." << std::endl;
    failed = true;
  }
  else DOUT << "Cvar_FindVar: base + " << (void *)((DWORD)cvarfind_addr - (DWORD)qlbase) << std::endl;

  executestring_addr =
    (void *)(hook_utils::FindPattern(qlbase, qlsize, PATTERN_EXECUTESTRING, MASK_EXECUTESTRING) + OFFSET_EXECUTESTRING);
  if (!executestring_addr) {
    DERR << "Failed to find ExecuteString." << std::endl;
    failed = true;
  }
  else DOUT << "ExecuteString: base + " << (void *)((DWORD)executestring_addr - (DWORD)qlbase) << std::endl;

  if (failed) return false;

  return true;
}

/* This loop will only stop when signaled. It'll process the outgoing command
   queue, as well as notifying the Python interpreter whenever QL's
   connection status changes.
*/
void MainLoop(HANDLE main_loop_stop_event, HANDLE queue_mutex, HANDLE restart_python_event) {
  UINT32 last_connection_status = CONN_DISCONNECTED;
  UINT32 new_connection_status;
  DWORD res;
  unsigned int loop_count = 0;

  while (WaitForSingleObject(main_loop_stop_event, 0) == WAIT_TIMEOUT) {
    new_connection_status = *connection_status;
    if (new_connection_status != last_connection_status) {
      HandleConnectionStatus(new_connection_status);
      last_connection_status = new_connection_status;
    }

    if (loop_count != LOOPS_BEFORE_SEND) {
      loop_count++;
      Sleep(DELAY_MAIN_LOOP);
      continue;
    }

    if (WaitForSingleObject(restart_python_event, 0) == WAIT_OBJECT_0) {
      //python::Finalize();
      python::Initialize();
      ResetEvent(restart_python_event);
      last_connection_status = CONN_DISCONNECTED; // Make sure bot_connect event triggers after a restart.
    }

    loop_count = 0;
    res = WaitForSingleObject(command_queue_mutex, INFINITE);
    switch (res) {
      // The thread got ownership of the mutex
    case WAIT_OBJECT_0:
      __try {
        if (message_queue.size() > 0) {
          OAddReliableCommand(message_queue.front().c_str());
          message_queue.pop();
        }
      }

      __finally {
        // Release ownership of the mutex object
        if (!ReleaseMutex(command_queue_mutex))
        {
          DERR << "Failed to release message queue mutex!" << std::endl;
        }
      }
      break;

      // The thread got ownership of an abandoned mutex
    case WAIT_ABANDONED:
      DERR << "Abandoned message queue mutex!" << std::endl;
    }
  }

  CloseHandle(main_loop_stop_event);
  CloseHandle(queue_mutex);
  DOUT << "Main loop ended!" << std::endl;
}

bool HookAll() {
  // Initialization.
  if (MH_Initialize() != MH_OK) {
    DERR << "MinHook initialization failed." << std::endl;
    return false;
  }

  // Actual hooks.
  else if (MH_CreateHook(parsecommandstring_addr, &HParseCommandString,
    reinterpret_cast<void **>(&OParseCommandString)) != MH_OK ||
    MH_CreateHook(parsegamestate_addr, &HParseGamestate,
    reinterpret_cast<void **>(&OParseGamestate)) != MH_OK ||
    MH_CreateHook(readbigstring_addr, &HReadBigString,
    reinterpret_cast<void **>(&OReadBigString)) != MH_OK ||
    MH_CreateHook(readshort_addr, &HReadShort,
    reinterpret_cast<void **>(&OReadShort)) != MH_OK ||
    MH_CreateHook(consoleprints_addr, &HConsolePrint,
    reinterpret_cast<void **>(&OConsolePrint)) != MH_OK ||
    MH_CreateHook(addreliablecommand_addr, &HAddReliableCommand,
    reinterpret_cast<void **>(&OAddReliableCommand)) != MH_OK) {
    DERR << "MinHook hooking failed." << std::endl;
    return false;
  }

  // Enables.
  else if (MH_EnableHook(parsecommandstring_addr) != MH_OK) {
    DERR << "MinHook failed to enable hook for ParseCommandString." << std::endl;
    return false;
  }
  else if (MH_EnableHook(parsegamestate_addr) != MH_OK) {
    DERR << "MinHook failed to enable hook for ParseGamestate." << std::endl;
    return false;
  }
  else if (MH_EnableHook(readbigstring_addr) != MH_OK) {
    DERR << "MinHook failed to enable hook for ReadBigString." << std::endl;
    return false;
  }
  else if (MH_EnableHook(readshort_addr) != MH_OK) {
    DERR << "MinHook failed to enable hook for ReadShort." << std::endl;
    return false;
  }
  else if (MH_EnableHook(consoleprints_addr) != MH_OK) {
    DERR << "MinHook failed to enable hook for ConsolePrint." << std::endl;
    return false;
  }
  else if (MH_EnableHook(addreliablecommand_addr) != MH_OK) {
    DERR << "MinHook failed to enable hook for AddReliableCommand." << std::endl;
    return false;
  }

  return true;
}

bool UnhookAll() {
  if (MH_DisableHook(MH_ALL_HOOKS) != MH_OK) {
    DERR << "MinHook failed to disable hooks." << std::endl;
    return false;
  }

  if (MH_Uninitialize() != MH_OK) {
    DERR << "MinHook uninitialization failed." << std::endl;
    return false;
  }

  return true;
}

void AddConsoleInterface() {
	// help
  std::tuple<std::string, std::string, GenericHandler>
    help("help", "Displays this message.", &HandleHelp);
	commands.push_back(help);
	// restart
  std::tuple<std::string, std::string, GenericHandler>
		restart("restart", "Restarts the Python interpreter.", &HandleRestart);
	commands.push_back(restart);
	// exec
  std::tuple<std::string, std::string, GenericHandler>
		exec("py", "Sends a command to the plugins.", &HandlePythonCommand);
	commands.push_back(exec);
	// exit
  std::tuple<std::string, std::string, GenericHandler>
		exit("exit", "Makes the bot clean up and exit safely.", &HandleExit);
	commands.push_back(exit);
	

	OAddCommand("bot", &HandleConsoleCommands);
}

void RemoveConsoleInterface() {
  commands.clear();
	ORemoveCommand("bot");
}

////////////////////////////////////////
//  CONSOLE COMMANDS

void HandleConsoleCommands() {
  std::string args(OGetArgs());

  std::vector<std::string> res = split(args, ' ');
  if (res.size() > 0) {
    for (auto it = commands.begin(); it != commands.end(); ++it) {
      if (!std::get<0>(*it).compare(res[0])) {
        std::get<2>(*it)(res);
        return;
      }
    }
    HandleUnknown(res);
  }
  else {
    HandleUnknown(res);
  }
}

void HandleHelp(const std::vector<std::string> &args) {
  OConsolePrint("^6Available commands:\n");
  char buf[512];
  for (std::vector<std::tuple<std::string, std::string, GenericHandler>>::iterator it = commands.begin(); it != commands.end(); ++it) {
    sprintf_s(buf, "^7%-8s: ^4%s\n", std::get<0>(*it).c_str(), std::get<1>(*it).c_str());
    OConsolePrint(buf);
  }
}

void HandleRestart(const std::vector<std::string> &args) {
  DOUT << "Restarting Python..." << std::endl;
  OConsolePrint("Restarting Python...\n");

  if (Py_IsInitialized() && !python::handle_unload.is_none()) {
    DOUT << "Calling Python clean-up function..." << std::endl;
    python::ScopedGILAcquire gil;
    try {
      // Call our Python handler.
      python::handle_unload();
    }
    catch (boost::python::error_already_set &) {
      std::string err = python::get_error_traceback();
      python::output_debug_lines(err);
    }
  }

  SetEvent(restart_python_event);
  Initialize();
  OConsolePrint("Python restarted!\n");
}

void HandlePythonCommand(const std::vector<std::string> &args) {
  if (python::handle_console_command.is_none()) return;
  else if (args.size() <= 1) {
    OConsolePrint("^6Usage: \\bot exec <command>\n");
    return;
  }

  std::string cmd;

  // Merge arguments into a single string.
  for (std::vector<std::string>::const_iterator it = ++args.begin(); it != args.end(); ++it) {
    cmd += *it + ' ';
  }
  cmd.pop_back(); // Remove extra space.

  python::ScopedGILAcquire gil;
  try {
    // Call our Python handler.
    python::handle_console_command(cmd);
  }
  catch (boost::python::error_already_set &) {
    std::string err = python::get_error_traceback();
    python::output_debug_lines(err);
  }
}

void HandleExit(const std::vector<std::string> &args) {
  OConsolePrint("^6Unloading the bot should be safe now. Good bye!\n");
  DOUT << "Ending message queue thread..." << std::endl;
  SetEvent(command_queue_stop_event);
}

void HandleUnknown(const std::vector<std::string> &args) {
  OConsolePrint("^6Try \\bot help.\n");
}

////////////////////////////////////////
//  HANDLERS

void HandleCommandString(size_t index) {
  if (python::handle_message.is_none()) return;

  std::string msg(clc->serverCommands[index]);

  python::ScopedGILAcquire gil;
  try {
    // Call our Python handler.
    python::handle_message(msg);
  }
  catch(boost::python::error_already_set &) {
    std::string err = python::get_error_traceback();
    python::output_debug_lines(err);
  }
}

void HandleGamestate(int index, const char * configstring) {
  if (python::handle_gamestate.is_none()) return;

  std::string cfg(configstring);

  python::ScopedGILAcquire gil;
  try {
    // Call our Python handler.
    python::handle_gamestate(index, cfg);
  }
  catch(boost::python::error_already_set &) {
    std::string err = python::get_error_traceback();
    python::output_debug_lines(err);
  }
}

void HandleConnectionStatus(UINT32 status) {
  if (python::handle_connection_status.is_none()) return;

  python::ScopedGILAcquire gil;
  try {
    // If it's 0, the game is being closed, so make sure the bot is being unloaded.
    if (status == 0) {
      python::handle_unload();
    }
    else {
      python::handle_connection_status(status);
    }
  }
  catch (boost::python::error_already_set &) {
    std::string err = python::get_error_traceback();
    python::output_debug_lines(err);
  }
}

void HandleConsolePrint(const char * msg) {
  if (python::handle_console_print.is_none()) return;

  std::string msgstr(msg);

  python::ScopedGILAcquire gil;
  try {
    // Call our Python handler.
    python::handle_console_print(msgstr);
  }
  catch (boost::python::error_already_set &) {
    std::string err = python::get_error_traceback();
    python::output_debug_lines(err);
  }
}

////////////////////////////////////////
//  REPLACEMENT FUNCTIONS

void HParseServerMessage(void * msg) {
  DOUT << "HParseServerMessage called!" << std::endl;

}

// Ever since the standalone was released CL_ParseCommandString
// was made into an inline function, so instead of actually hooking
// ParseCommandString, we simply hook a random function I found that
// was called every time ParseCommandString should be called.
int HParseCommandString(void * msg) {
  //DOUT << "HParseCommandString called!" << std::endl;
  int res = OParseCommandString(msg);

  // Avoid parsing the same command several times.
  if (lastSeq < clc->serverCommandSequence) {
    HandleCommandString(clc->serverCommandSequence & (MAX_RELIABLE_COMMANDS - 1));
    lastSeq = clc->serverCommandSequence;
  }

  return res;
}

void HParseGamestate(void * msg) {
  in_parse_gamestate = true;
  // Calling the original ParseGamestate now will do several calls
  // to ReadBigString. The bool makes our ReadBigString aware of where
  // where are in the code flow.
  OParseGamestate(msg);
  in_parse_gamestate = false;
}

char * HReadBigString(void * msg) {
  char * res = OReadBigString(msg);

  if (in_parse_gamestate) {
    HandleGamestate(gamestate_configstring_index, res);
  }

  return res;
}

// MSG_ReadShort is called before MSG_ReadBigString, so we simply save the index for now.
int HReadShort(void * msg) {
  if (in_parse_gamestate) {
    gamestate_configstring_index = OReadShort(msg);
    return gamestate_configstring_index;
  }

  return OReadShort(msg);
}

void HAddReliableCommand(const char * cmd) {
  if (!strcmp(cmd, "disconnect")) {
    OAddReliableCommand(cmd);
    return;
  }
  DOUT << "=> " << cmd << std::endl;
  AddQueuedCommand(cmd);
}

void HConsolePrint(const char * msg) {
  HandleConsolePrint(msg);
  OConsolePrint(msg);
}

////////////////////////////////////////
//  WRAPPER FUNCTIONS

const char * CvarFindWrapper(const char * var_name) {
  cvar_t * res = OCvarFind(var_name);

  if (res == NULL) return NULL;
  else return res->string;
}

void ExecuteStringWrapper(const char * cmd) {
  char cmdbuf[2048];

  sprintf_s(cmdbuf, "alias __minqlbot \"%s\"", cmd);
  OExecuteString(cmdbuf);
  OExecuteString("__minqlbot");
}

////////////////////////////////////////
//  HELPER FUNCTIONS

// Had to make this to avoid Compiler Error C2712.
void AddQueuedCommand(const std::string &cmd) {
  DWORD res = WaitForSingleObject(command_queue_mutex, INFINITE);

  switch (res) {
    // The thread got ownership of the mutex
  case WAIT_OBJECT_0:
    __try {
      message_queue.push(cmd);
    }

    __finally {
      // Release ownership of the mutex object
      if (!ReleaseMutex(command_queue_mutex))
      {
        DERR << "Failed to release message queue mutex!" << std::endl;
      }
    }
    break;

    // The thread got ownership of an abandoned mutex
  case WAIT_ABANDONED:
    DERR << "Abandoned message queue mutex!" << std::endl;
  }
}

UINT32 GetConnectionStatus() {
  return *connection_status;
}

/* Configstrings have an array of 1024 32-bit unsigned integers that
   give the position of the strings that are immediately after the array
   in memory. If there is no string there, the integer is 0.
*/
const char * GetConfigstring(UINT32 i) {
  if (i < 1023 && configstrings[i]) {
    char * cfgstr = ((char *)(configstrings + 1024)) + configstrings[i];
    return cfgstr;
  }

  return "";
}

python::dict GetConfigstringRange(UINT32 i, UINT32 j) {
  python::dict res;
  if (i > 1023 || j > 1023) return res;

  for (UINT32 k = i; k <= j; k++) {
    if (configstrings[k]) {
      char * cfgstr = ((char *)(configstrings + 1024)) + configstrings[k];
      res[k] = std::string(cfgstr);
    }
  }

  return res;
}

}; // namespace quake