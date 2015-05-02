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

namespace quake {

typedef int qboolean;
#define qtrue 1
#define qfalse 2

typedef struct cvar_s {
  char		  *name;
  char		  *string;
  char		  *resetString;		// cvar_restart will reset to this value
  char		  *latchedString;		// for CVAR_LATCH vars
  int			  flags;
  qboolean  modified;			// set each time the cvar is changed
  int			  modificationCount;	// incremented each time the cvar is changed
  float		  value;				// atof( string )
  int			  integer;			// atoi( string )
  struct cvar_s *next;
  struct cvar_s *hashNext;
} cvar_t;

typedef enum {
  NA_BOT,
  NA_BAD, // an address lookup failed
  NA_LOOPBACK,
  NA_BROADCAST,
  NA_IP,
  NA_IPX,
  NA_BROADCAST_IPX
} netadrtype_t;

typedef enum {
  NS_CLIENT,
  NS_SERVER
} netsrc_t;

typedef struct {
  netadrtype_t type;
  char ip[4];
  char ipx[10];
  unsigned short port;
} netadr_t;

typedef struct {
  //int                         clientNum;
  //int                         lastPacketSentTime; // for retransmits during connection
  //int                         lastPacketTime; // for timeouts

  //netadr_t                    serverAddress;
  //int                         connectTime; // for connection retransmits
  //int                         connectPacketCount; // for display on connection dialog
  //char                        serverMessage[MAX_STRING_TOKENS]; // for display on connection dialog

  //int                         challenge; // from the server to use for connecting
  //int                         checksumFeed; // from the server for checksum calculations

  // these are our reliable messages that go to the server
  int                         reliableSequence;
  int                         reliableAcknowledge; // the last one the server has executed
  char                        reliableCommands[MAX_RELIABLE_COMMANDS][MAX_STRING_CHARS];

  // server message (unreliable) and command (reliable) sequence
  // numbers are NOT cleared at level changes, but continue to
  // increase as long as the connection is valid

  // message sequence is used by both the network layer and the
  // delta compression layer
  int                         serverMessageSequence;

  // reliable messages received from server
  int                         serverCommandSequence;
  int                         lastExecutedServerCommand; // last server command grabbed or executed with CL_GetServerCommand
  char                        serverCommands[MAX_RELIABLE_COMMANDS][MAX_STRING_CHARS];

  //// file transfer from server
  //fileHandle_t                download;
  //char                        downloadTempName[MAX_OSPATH];
  //char                        downloadName[MAX_OSPATH];
  //int                         downloadNumber;
  //int                         downloadBlock;      // block we are waiting for
  //int                         downloadCount;      // how many bytes we got
  //int                         downloadSize;       // how many bytes we got
  //char                        downloadList[MAX_INFO_STRING]; // list of paks we need to download
  //qboolean                    downloadRestart;    // if true, we need to do another FS_Restart because we downloaded a pak

  //// demo information
  //char                        demoName[MAX_QPATH];
  //qboolean                    spDemoRecording;
  //qboolean                    demorecording;
  //qboolean                    demoplaying;
  //qboolean                    demowaiting;       // don't record until a non-delta message is received
  //qboolean                    firstDemoFrameSkipped;
  //fileHandle_t                demofile;

  //int                         timeDemoFrames;    // counter of rendered frames
  //int                         timeDemoStart;     // cls.realtime before first frame
  //int                         timeDemoBaseTime;  // each frame will be at this time + frameNum * 50

  //// big stuff at end of structure so most offsets are 15 bits or less
  //netchan_t        netchan;
} clientConnection_t;

// CLC
extern clientConnection_t * clc;

}