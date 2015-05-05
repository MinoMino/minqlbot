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

#include <boost\python.hpp>
#include <string>
#include <queue>
#include "common.h"

namespace quake {
namespace python {
using namespace boost::python;

// Pointers to our message handler in Python
extern object handle_message;
extern object handle_gamestate;
extern object handle_connection_status;
extern object handle_console_command;
extern object handle_console_print;
extern object handle_unload;

// Starts the Python interpreter and executes our main scripts.
int Initialize();

// Finalizes our Python interpreter.
void Finalize();

// Debug output for Python.
void PyDebug(char * msg);
void PyDebugEx(char * msg, bool newline);

/* Can't use fopen for some reason. Put file into string instead. Thanks, Stack Overflow. */
std::string get_file_contents(const char * filename);

/* After countless hours of not being able to see errors, I finally found a function
   to successfully grab the traceback into a string without raising exceptions.
   Thanks, Stack Overflow. Again. */
std::string get_error_traceback();

/* Outputs lines of text (delimited by newlines) as a debug string. */
void output_debug_lines(const std::string & lines);

char * get_script_from_resource(HMODULE instance, int resource_id);

// Automatic GIL state ensure. Needs to be used when you want to do Python calls from other threads.
class ScopedGILAcquire
{
public:
  inline ScopedGILAcquire(){
    state = PyGILState_Ensure();
  }

  inline ~ScopedGILAcquire(){
    PyGILState_Release(state);
  }
private:
  PyGILState_STATE state;
};

} // namespace quake::python
} // namespace quake

/* String splitting with a delimiter, copied verbatim. Please marry me, Stack Overflow. */
std::vector<std::string> &split(const std::string &s, char delim, std::vector<std::string> &elems);
std::vector<std::string> split(const std::string &s, char delim);