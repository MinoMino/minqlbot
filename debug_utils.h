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

#include <ostream>
#include <sstream>
#include <string>
#include <Windows.h>

// Code based on http://www.codeproject.com/Articles/1053/Using-an-output-stream-for-debugging?msg=2841638#xx2841638xx

namespace debug_utils {

template <class CharT, class TraitsT = std::char_traits<CharT> >
class basic_debugbuf : 
  public std::basic_stringbuf<CharT, TraitsT>
{
public:
  virtual ~basic_debugbuf() {
    sync();
  }

protected:
  int sync() {
    output_debug_string(str().c_str());
    str(std::basic_string<CharT>());    // Clear the string buffer

    return 0;
  }

  void output_debug_string(const CharT *text) { }
};

template<class CharT, class TraitsT = std::char_traits<CharT> >
class basic_dostream : 
  public std::basic_ostream<CharT, TraitsT>
{
public:
  basic_dostream() : std::basic_ostream<CharT, TraitsT>
    (new basic_debugbuf<CharT, TraitsT>()) { }

  ~basic_dostream() {
    delete rdbuf(); 
  }
};

template<>
void basic_debugbuf<char>::output_debug_string(const char *text) {
  ::OutputDebugStringA(text);
}

template<>
void basic_debugbuf<wchar_t>::output_debug_string(const wchar_t *text) {
  ::OutputDebugStringW(text);
}

typedef basic_dostream<char>    dostream;
typedef basic_dostream<wchar_t> wdostream;

} // Namespace debug_utils

// Global debug stream.
#define DBG_PREFIX "MINQLBOT: "
#ifdef UNICODE
extern debug_utils::wdostream dbg_stream;
#define DOUT dbg_stream << DBG_PREFIX
#define DERR dbg_stream << DBG_PREFIX << "ERROR @ " << __FUNCTION__ << ": "
#define DOUT_NP dbg_stream
#else
extern debug_utils::dostream dbg_stream;
#define DOUT dbg_stream << DBG_PREFIX
#define DERR dbg_stream << DBG_PREFIX << "ERROR @ " << __FUNCTION__ << ": "
#define DOUT_NP dbg_stream
#endif