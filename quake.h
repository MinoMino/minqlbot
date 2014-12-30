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

#pragma once

#define STRUCT_OFFSET_PSERVERCOMMANDS   0xF7
#define STRUCT_OFFSET_PCLIENTSTATIC     0x2
#define STRUCT_OFFSET_PCONFIGSTRINGS    0x23
#define OFFDIFF_CLC_SERVERCMDS   0x10014 // &servercmds - &clc

#define MAX_RELIABLE_COMMANDS   64
#define MAX_STRING_CHARS        1024
#define MAX_STRING_TOKENS       256

// The bot bottlenecks server commands. This macro defines the delay between each message.
#define DELAY_SEND_COMMAND      600
// The time of the Sleep call in the main loop.
#define DELAY_MAIN_LOOP         20

#include "common.h"
#include "quake_common.h"
#include <string>
#include <vector>
#include <boost/python.hpp>

namespace quake {
  enum CONNECTION_STATUS {
    CONN_CLOSED = 0,
    CONN_DISCONNECTED = 1,
    CONN_CONNECTING = 3,
    CONN_AWAITING_CHALLENGE = 4,
    CONN_AWAITING_GAMESTATE = 5,
    CONN_RECEIVING_GAMESTATE = 6,
    CONN_AWAITING_SNAPSHOT = 7,
    CONN_CONNECTED = 8
  };

// Quake Live base pointer.
extern void * qlbase;

// Original functions.
typedef void (__cdecl * ParseServerMessage)(void * msg);
typedef int (__cdecl * ParseCommandString)(void * msg);
typedef int (__cdecl * ParseGamestate)(void * msg);
typedef char * (__cdecl * ReadBigString)(void * msg);
typedef void (__cdecl * AddReliableCommand)(const char * cmd);
typedef void (__cdecl * AddCommand)(const char * cmd, void * func);
typedef void (__cdecl * RemoveCommand)(const char * cmd);
typedef char * (__cdecl * GetArgs)();
typedef void (__cdecl * ConsolePrint)(const char * msg);


// Original function pointers.
extern ParseServerMessage OParseServerMessage;
extern ParseCommandString OParseCommandString;
extern ParseGamestate OParseGamestate;
extern ReadBigString OReadBigString;
extern AddReliableCommand OAddReliableCommand;
extern AddCommand OAddCommand;
extern RemoveCommand ORemoveCommand;
extern GetArgs OGetArgs;
extern ConsolePrint OConsolePrint;

DWORD WINAPI MainThread(HMODULE hModule);
void CleanUp();
bool Initialize();
bool FindFunctions();
void MainLoop(HANDLE queue_end_event, HANDLE queue_mutex, HANDLE restart_python_event);
bool HookAll();
bool UnhookAll();
void AddConsoleInterface();
void RemoveConsoleInterface();

// Console command handlers.
typedef void (* GenericHandler)(const std::vector<std::string> &args);
void __cdecl HandleConsoleCommands();
void __cdecl HandleHelp(const std::vector<std::string> &args);
void __cdecl HandleRestart(const std::vector<std::string> &args);
void __cdecl HandlePythonCommand(const std::vector<std::string> &args);
void __cdecl HandleExit(const std::vector<std::string> &args);
void __cdecl HandleUnknown(const std::vector<std::string> &args);


void HandleCommandString(size_t index);
void HandleGamestateString(const char * configstring);
void HandleConnectionStatus(UINT32 status);

// Function replacements.
void __cdecl HParseServerMessage(void * msg);
int __cdecl HParseCommandString(void * msg);
void __cdecl HParseGamestate(void * msg);
char * __cdecl HReadBigString(void * msg);
void __cdecl HAddReliableCommand(const char * cmd);

// Helpers
void AddQueuedCommand(const std::string &cmd);
UINT32 GetConnectionStatus();
const char * GetConfigstring(UINT32 i);
boost::python::dict GetConfigstringRange(UINT32 i, UINT32 j);


} // Namespace quake