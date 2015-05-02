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

#include "python.h"
#include "debug_utils.h"
#include "quake.h"
#include "common.h"
#include "resource.h"
#include <fstream>
#include <string>
#include <cerrno>
#include <queue>

// Assigned in dllmain.cpp as soon this module is loaded.
extern HMODULE this_module;

namespace quake {
namespace python {

PyThreadState * thread_state;

object handle_message;
object handle_gamestate;
object handle_connection_status;
object handle_console_command;
object handle_console_print;
object handle_unload;

using namespace boost::python;

BOOST_PYTHON_MODULE(minqlbot)
{
  PyEval_InitThreads();
  // Add regular functions to the module.
  def("debug",                  PyDebug);
  def("debug_ex",               PyDebugEx);
  def("send_command",           quake::HAddReliableCommand);
  def("console_print",          quake::HConsolePrint);
  def("_configstring",          quake::GetConfigstring);
  def("_configstring_range",    quake::GetConfigstringRange);
  def("version",                GetMinqlbotVersion);
  def("reinitialize",           quake::Initialize);
  def("connection_status",      quake::GetConnectionStatus);
  def("get_cvar",               quake::CvarFindWrapper);
  def("console_command",        quake::ExecuteStringWrapper);
}

int Initialize() {
  // Initialize handlers right away to avoid memory access errors.
  handle_message = object();
  handle_gamestate = object();
  handle_connection_status = object();
  handle_console_command = object();
  handle_console_print = object();
  handle_unload = object();

// DEV SETUP
#ifdef _DEBUG
  std::string minql_s = get_file_contents("python/minqlbot.py");
  std::string plugin_s = get_file_contents("python/plugin.py");
#else
  const char * main_script;
  const char * plugin_base;
  main_script = get_script_from_resource(this_module, IDR_MAIN_SCRIPT);
  plugin_base = get_script_from_resource(this_module, IDR_PLUGIN_BASE);


  if (main_script == NULL) {
    DOUT << "ERROR: Reading main Python script from resource failed!" << std::endl;
    return 1;
  }
  else if (plugin_base == NULL) {
    DOUT << "ERROR: Reading Python plugin base from resource failed!" << std::endl;
    return 1;
  }
#endif

  PyImport_AppendInittab("minqlbot", &PyInit_minqlbot);
  if (!Py_IsInitialized()) {
    Py_Initialize();
    PyEval_InitThreads();
  }
  else {
    PyEval_RestoreThread(thread_state);
  }

  try {
    object main_module = import("__main__");
    object main_namespace = main_module.attr("__dict__");
    object minqlbot_module = import("minqlbot");
    main_namespace["minqlbot"] = minqlbot_module;

    // Let Python know if this is a debug build or not.
#ifdef _DEBUG
    minqlbot_module.attr("IS_DEBUG") = true;
    exec(plugin_s.c_str(), main_namespace, main_namespace);
    exec(minql_s.c_str(), main_namespace, main_namespace);
#else
    minqlbot_module.attr("IS_DEBUG") = false;
    exec(plugin_base, main_namespace, main_namespace);
    exec(main_script, main_namespace, main_namespace);
#endif

    handle_message = main_namespace["handle_message"];
    handle_gamestate = main_namespace["handle_gamestate"];
    handle_connection_status = main_namespace["handle_connection_status"];
    handle_console_command = main_namespace["handle_console_command"];
    handle_console_print = main_namespace["handle_console_print"];
    handle_unload = main_namespace["handle_unload"];
    thread_state = PyEval_SaveThread();
  } 
  catch(error_already_set &) {
    std::string err = get_error_traceback();
    output_debug_lines(err);

    thread_state = PyEval_SaveThread();
    return 2;
  }

  return 0;
}

void Finalize() {
  PyEval_RestoreThread(thread_state);
  Py_Finalize();
}

void PyDebug(char * msg) {
  DOUT << "(PY) " << msg << std::endl;
}

void PyDebugEx(char * msg, bool newline) {
  if (newline) DOUT << "(PY) " << msg << std::endl;
  else DOUT << "(PY) " << msg;
}


////////////////////////////////
///       HELPERS
/* Can't use fopen for some reason. Put file into string instead. */
std::string get_file_contents(const char * filename) {
  std::ifstream ifs(filename);
  std::string content( (std::istreambuf_iterator<char>(ifs) ),
                       (std::istreambuf_iterator<char>()    ) );
  return content;
}

// decode a Python exception into a string
std::string get_error_traceback() {
  try {
    PyObject *exc,*val,*tb;
    PyErr_Fetch(&exc,&val,&tb);
    PyErr_NormalizeException(&exc,&val,&tb);
    handle<> hexc(exc),hval(allow_null(val)),htb(allow_null(tb));
    if (!hval) {
      return extract<std::string>(str(hexc));
    }
    else {
      object traceback(import("traceback"));
      object format_exception(traceback.attr("format_exception"));
      object formatted_list(format_exception(hexc,hval,htb));
      object formatted(str("").join(formatted_list));
      return extract<std::string>(formatted);
    }
  }
  catch (error_already_set &) {
    return std::string("PYTHON ERROR: Failed to get a traceback.");
  }
}

void output_debug_lines(const std::string & lines) {
  using namespace std;
  vector<string> split_str = split(lines, '\n');

  for (vector<string>::iterator it = split_str.begin(); it != split_str.end(); ++it) {
    DOUT << (*it).c_str() << endl;
  }
}

char * get_script_from_resource(HMODULE instance, int resource_id) {
  HGLOBAL res_handle;
  HRSRC res;

  res = FindResource(instance, MAKEINTRESOURCE(resource_id), RT_RCDATA);
  if (!res) {
    DOUT << "ERROR: Can't find resource with ID '" << resource_id <<
      "' on module with handle '" << instance << "'!" << std::endl;
    return NULL;
  }

  res_handle = LoadResource(instance, res);
  if (!res_handle) {
    DOUT << "ERROR: Can't load resource with ID '" << resource_id <<
      "' on module with handle '" << instance << "'!" << std::endl;
    return NULL;
  }

  return (char *)LockResource(res_handle);
}

} // namespace quake::python
} // namespace quake


// TODO: Refactor. Not really related to Python.
std::vector<std::string> &split(const std::string &s, char delim, std::vector<std::string> &elems) {
  std::stringstream ss(s);
  std::string item;
  while (std::getline(ss, item, delim)) {
    elems.push_back(item);
  }
  return elems;
}


std::vector<std::string> split(const std::string &s, char delim) {
  std::vector<std::string> elems;
  split(s, delim, elems);
  return elems;
}