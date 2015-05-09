# minqlbot - A Quake Live server administrator bot.
# Copyright (C) 2015 Mino <mino@minomino.org>

# This file is part of minqlbot.

# minqlbot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# minqlbot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with minqlbot. If not, see <http://www.gnu.org/licenses/>.

"""Just about everything except for some core class definitions. Both this
and plugin.py could use some serious refactoring.

"""

import os
import sys
import configparser
import re
import traceback
import importlib
import minqlbot

# ====================================================================
#                             CONSTANTS
#      Technically not constants, but yeah. Don't change these.
# ====================================================================

setattr(minqlbot, "__version__", minqlbot.version())

# QL keeps track of teams in terms for integers. The integer = the tuple's index.
setattr(minqlbot, "TEAMS", ("default", "red", "blue", "spectator"))
# Gametypes. The integer = the tuple's index.
setattr(minqlbot, "GAMETYPES", ("Free for All", "Duel", "Race", "Team Deathmatch", "Clan Arena",
    "Capture the Flag", "Overload", "Harvester", "Freeze Tag", "Domination", "Attack and Defend", "Red Rover"))
setattr(minqlbot, "GAMETYPES_SHORT", ("ffa", "duel", "race", "tdm", "ca", "ctf", "ob", "har", "ft", "dom", "ad", "rr"))
# Rulesets. The integer = the tuple's index.
setattr(minqlbot, "RULESETS", ("", "classic", "turbo", "ql"))

# Possible return values for plugins callbacks that control the flow of succeeding callbacks.
setattr(minqlbot, "RET_NONE", 0)
setattr(minqlbot, "RET_STOP", 1)
setattr(minqlbot, "RET_USAGE", 2)

# ====================================================================
#                         LOW-LEVEL HANDLERS
#       These are all called by the C++ code, not within Python.  
# ====================================================================

# Regex to catch "cs" commands.
re_cs = re.compile(r'cs (?P<index>[^ ]+) "(?P<cvars>.*)"$')
# Regex to get the current vote and its arguments.
re_vote = re.compile('(?P<vote>.+) "*(?P<args>.*?)"*')
# Regex to catch colors.
re_color_tag = re.compile(r"\^.")

def handle_message(msg):
    msg = msg.replace("\n", "")

    # Cache configstrings.
    res = re_cs.match(msg)
    if res:
        index = int(res.group("index"))
        cvars = res.group("cvars")
        with minqlbot._CS_CACHE_LOCK:
            minqlbot._CS_CACHE[index] = cvars

    parse(msg)
    event_handlers["raw"].trigger(msg)
    
def handle_gamestate(index, configstring):
    configstring = configstring.replace("\n", "")
    with minqlbot._CS_CACHE_LOCK:  # Cache the gamestate.
        minqlbot._CS_CACHE[index] = configstring
    event_handlers["gamestate"].trigger(index, configstring)
    
    if index == 3:
        event_handlers["map"].trigger(configstring)
    
connected = False

def handle_connection_status(status):
    global connected
    if status < 6 and connected:
        connected = False
        with minqlbot._CS_CACHE_LOCK:
            minqlbot._CS_CACHE.clear()
        debug("Reinitializing struct pointers...")
        minqlbot.reinitialize()
    if status == 0: # Game closed
        pass
    elif status == 1: # Disconnect
        event_handlers["bot_disconnect"].trigger()
    elif status == 3: # Connecting
        pass
    elif status == 4: # Awaiting challenge
        pass
    elif status == 5: # Awaiting gamestate
        pass
    elif status == 6: # Receiving gamestate
        pass
    elif status == 7: # Awaiting snapshot
        with minqlbot._CS_CACHE_LOCK:
            minqlbot._CS_CACHE.clear()
    elif status == 8: # Connected
        if not connected:
            connected = True
            event_handlers["bot_connect"].trigger()
    else:
        debug("Unknown connection status: {}".format(status))

    setattr(minqlbot, "CONNECTION", status)
    
def handle_console_print(cmd):
    event_handlers["console"].trigger(cmd.rstrip("\n"))

def handle_console_command(cmd):
    commands.handle_input(minqlbot.DummyPlayer(minqlbot.NAME), cmd, minqlbot.CONSOLE_CHANNEL, prefix=False)

unloaded = False
    
def handle_unload():
    global unloaded
    if not unloaded:
        unloaded = True
    for plugin in minqlbot.Plugin._Plugin__loaded_plugins.copy():
        unload_plugin(plugin)

# ====================================================================
#                         EVENTS & COMMANDS
# ====================================================================

class EventError(Exception):
    """Generic custom exception for event handlers.

    """
    pass

class EventHandlerError(Exception):
    """Generic custom exception for event handlers.

    """
    pass

class CommandError(Exception):
    """Generic custom exception for commands.

    """
    pass

class AbstractChannel:
    """An abstract class of a chat channel. A chat channel being a source of a message.

    Chat channels must implement reply(), since that's the whole point of having a chat channel
    as a class. Makes it quite convenient when dealing with commands and such, while allowing
    people to implement their own channels, opening the possibilites for communication with the
    bot through other means than just chat and console (e.g. web interface).

    Say "ChatChannelA" and "ChatChannelB" are both subclasses of this, and "cca" and "ccb" are instances,
    the default implementation of "cma == cmb" is comparing __repr__(). However, when you register
    a command and list what channels you want it to work with, it'll use this class' __str__(). It's
    important to keep this in mind if you make a subclass. Say you have a web interface that
    supports multiple users on it simulaneously. The right way would be to set "name" to something
    like "webinterface", and then implement a __repr__() to return something like "webinterface user1".
    """
    def __init__(self, name):
        self.__name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return str(self)

    # Equal.
    def __eq__(self, other):
        if isinstance(other, str):
            # If the other is a string, we don't want to do repr() on it.
            return repr(self) == other
        else:
            return repr(self) == repr(other)

    # Not equal.
    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def name(self):
        return self.__name

    def reply(self):
        raise NotImplementedError()

    def split_long_msg(self, msg, limit=100, delimiter=" "):
        """Split a message into several pieces for channels with limtations."""
        if len(msg) < limit:
            return [msg]
        out = []
        index = limit
        for i in reversed(range(limit)):
            if msg[i:i + len(delimiter)] == delimiter:
                index = i
                out.append(msg[0:index])
                # Keep going, but skip the delimiter.
                rest = msg[index + len(delimiter):]
                if rest:
                    out.extend(self.split_long_msg(rest, limit, delimiter))
                return out

        out.append(msg[0:index])
        # Keep going.
        rest = msg[index:]
        if rest:
            out.extend(self.split_long_msg(rest, limit, delimiter))
        return out

# Export the abstract.
setattr(minqlbot, "AbstractChannel", AbstractChannel)

class ChatChannel(AbstractChannel):
    """A channel for in-game chat, excluding team chat.

    """
    def __init__(self):
        super().__init__("chat")
        self.command = "say"
        

    def reply(self, msg):
        last_color = ""
        for s in self.split_long_msg(msg, limit=100):
            minqlbot.send_command('{} "{}{}"'.format(self.command, last_color, s))
            find = re_color_tag.findall(s)
            if find:
                last_color = find[-1]

# Static chat channel.
chat_channel = ChatChannel()
setattr(minqlbot, "CHAT_CHANNEL", chat_channel)

class TeamChatChannel(ChatChannel):
    """A channel for in-game team chat.

    """
    def __init__(self):
        super(ChatChannel, self).__init__("team_chat")
        self.command = "say_team"

    def reply(self, msg):
        super().reply(msg)

# Static team chat channel.
team_chat_channel = TeamChatChannel()
setattr(minqlbot, "TEAM_CHAT_CHANNEL", team_chat_channel)

class TellChannel(ChatChannel):
    """A channel for in-game tells (private messages).

    """
    def __init__(self, player):
        super(ChatChannel, self).__init__("tell")
        if not isinstance(player, minqlbot.Player):
            raise TypeError("'player' must be an instance of minqlbot.Player or a subclass of it.")

        self.__player = player

    @property
    def player(self):
        return self.__player

    def __repr__(self):
        return "{} {}".format(self.name, self.player.clean_name)

    def reply(self, msg):
        self.command = 'tell {}'.format(self.player.id)
        super().reply(msg)

class ConsoleChannel(AbstractChannel):
    """A channel for the console.

    """
    def __init__(self):
        super().__init__("console")

    def reply(self, msg):
        minqlbot.console_print("{}\n".format(msg))

# Static console channel.
console_channel = ConsoleChannel()
setattr(minqlbot, "CONSOLE_CHANNEL", console_channel)

class Command:
    """A class representing a chat-triggered command.

    Has information about the command itself, its usage, when and who to call when
    action should be taken.

    """
    def __init__(self, plugin, name, handler, permission=0, channels=minqlbot.CMD_ALL_CHANNELS, exclude_channels=(), usage=""):
        if not (isinstance(channels, list) or isinstance(channels, tuple) or channels == minqlbot.CMD_ALL_CHANNELS):
            raise CommandError("'channels' must be a tuple or a list.")
        elif not (isinstance(exclude_channels, list) or isinstance(exclude_channels, tuple)):
            raise CommandError("'exclude_channels' must be a tuple or a list.")
        self.plugin = plugin # Instance of the owner.

        # Allow a command to have alternative names.
        if isinstance(name, list) or isinstance(name, tuple):
            self.name = [n.lower() for n in name]
        else:
            self.name = [name]
        self.handler = handler
        self.permission = permission
        self.channels = channels
        self.exclude_channels = exclude_channels
        self.usage = usage

    def execute(self, player, msg, channel):
        debug("[EXECUTE] {} @ {} -> {}".format(self.name[0], self.plugin.name, channel), only_debug=True)
        return self.handler(player, msg.split(), channel)

    def is_eligible_name(self, name):
        return name.lower() in self.name

    def is_eligible_channel(self, channel):
        """Check if a chat channel is one this command should execute in.

        Exclude takes precedence.
        """
        if channel in self.exclude_channels:
            return False
        elif self.channels == minqlbot.CMD_ALL_CHANNELS or channel.name in self.channels:
            return True
        else:
            return False

    def is_eligible_player(self, player):
        """Check if a player has the rights to execute the command.

        """
        if self.plugin.has_permission(player, self.permission):
            return True
        else:
            return False

# Export.
setattr(minqlbot, "Command", Command)

class CommandManager:
    """Holds all commands and executes them whenever we get input and should execute.

    """
    def __init__(self):
        self.__commands = ([], [], [], [], [])

    @property
    def commands(self):
        c = []
        for cmds in self.__commands:
            c.extend(cmds)

        return c

    def add_command(self, command, priority):
        if self.is_registered(command):
            raise CommandError("Attempted to add an already registered command.")
        
        #debug("Adding command: {}".format(command.name), only_debug=True)
        self.__commands[priority].append(command)

    def remove_command(self, command):
        if not self.is_registered(command):
            raise CommandError("Attempted to remove a command that was never added.")
        else:
            for priority_level in self.__commands:
                for cmd in priority_level:
                    if cmd == command:
                        #debug("Removing command: {}".format(command.name), only_debug=True)
                        priority_level.remove(cmd)
                        return

        debug("Weird behavior when removing: ".format(command.name), only_debug=True)

    def is_registered(self, command):
        """Check if a command is already registed.

        Commands are unique by (command.name, command.handler).

        """
        for priority_level in self.__commands:
            for cmd in priority_level:
                if command.name == cmd.name and command.handler == cmd.handler:
                    return True

        return False

    def handle_input(self, player, msg, channel, prefix=True):
        # Check if it's just a couple of spaces and return if so.
        if not msg.strip() or (prefix and not msg.startswith(minqlbot.COMMAND_PREFIX)):
            return

        ms = msg.split(" ", 1)
        if prefix:
            name = ms[0].lower().lstrip(minqlbot.COMMAND_PREFIX)
        else:
            name = ms[0].lower()

        for priority_level in self.__commands:
            for cmd in priority_level:
                if cmd.is_eligible_name(name) and cmd.is_eligible_channel(channel) and cmd.is_eligible_player(player):
                    res = cmd.execute(player, msg, channel)
                    if res == minqlbot.RET_STOP:
                        return
                    elif res == minqlbot.RET_USAGE:
                        channel.reply("^7Usage: ^6{}{} {}".format(minqlbot.COMMAND_PREFIX, name, cmd.usage))
                    elif res != None and res != minqlbot.RET_NONE:
                        debug("[Warning] Command '{}' with handler '{}' returned an unknown return value: {}"
                            .format(cmd.name, cmd.handler.__name__, res))

# Export the class.
setattr(minqlbot, "CommandManager", CommandManager)

# Get a global instance.
commands = CommandManager()

# Export the manager instance.
setattr(minqlbot, "COMMANDS", commands)


class EventHandler:
    """An event handler, allowing functions to "hook" any events.

    Provides methods for hooking and dehooking the event. When an event takes place,
    the method 'trigger' should be called, which will take care of calling hooked functions.

    """
    no_debug = ("raw", "console", "scores", "gamestate")
    
    def __init__(self, name):
        self.name = name
        self.plugins = {}
    
    def trigger(self, *args, **kwargs):
        """Registered hooks for this event are called from highest to lowest priority.
        
        """

        if minqlbot.IS_DEBUG and self.name not in EventHandler.no_debug:
            minqlbot.debug("{}{}".format(self.name, args))

        plugins = self.plugins.copy()
        for i in range(5):
            for plugin in plugins:
                for handler in plugins[plugin][i]:
                    try:
                        retval = handler(*args, **kwargs)
                        if retval == minqlbot.RET_NONE or retval == None:
                            continue
                        elif retval == minqlbot.RET_STOP:
                            return
                        else:
                            debug("{}: unexpected return value '{}'".format(self.name, retval))
                    except:
                        e = traceback.format_exc().rstrip("\n")
                        debug("========== ERROR: {}@{} ==========".format(handler.__name__, plugin))
                        for line in e.split("\n"):
                            debug(line)
                        continue
                    
    
    def add_hook(self, plugin, handler, priority=minqlbot.PRI_NORMAL):
        """Add a single hook.
        
        """
        if not (priority >= minqlbot.PRI_HIGHEST and priority <= minqlbot.PRI_LOWEST):
            raise EventHandlerError("Plugin '{}' attempted to hook '{}' with an invalid priority level."
                            .format(plugin, self.name))
        
        if plugin not in self.plugins:
            # Initialize tuple.
            self.plugins[plugin] = ([], [], [], [], []) # 5 priority levels.
        else:
            # Check if we've already registered this handler.
            for i in range(len(self.plugins[plugin])):
                for hook in self.plugins[plugin][i]:
                    if handler == hook:
                        raise EventHandlerError("Plugin '{}' attempted to hook an already hooked event, '{}'."
                            .format(plugin, self.name))
        
        self.plugins[plugin][priority].append(handler)
        
    def remove_hook(self, plugin, handler, priority=minqlbot.PRI_NORMAL):
        """Remove a single hook.
        
        """
        for hook in self.plugins[plugin][priority]:
            if handler == hook:
                self.plugins[plugin][priority].remove(handler)
                return
        
        raise EventHandlerError("Plugin '{}' attempted to remove a hook from '{}', an unhooked event."
                            .format(plugin, self.name))

# Export the class.
setattr(minqlbot, "EventHandler", EventHandler)

class ConsoleEventHandler(EventHandler):
    def __init__(self):
        super().__init__("console")
    
    def trigger(self, cmd):
        super().trigger(cmd)

class BotConnectEventHandler(EventHandler):
    def __init__(self):
        super().__init__("bot_connect")
    
    def trigger(self):
        super().trigger()

class BotDisonnectEventHandler(EventHandler):
    def __init__(self):
        super().__init__("bot_disconnect")
    
    def trigger(self):
        super().trigger()

class PlayerConnectEventHandler(EventHandler):
    def __init__(self):
        super().__init__("player_connect")
    
    def trigger(self, player):
        super().trigger(player)

class PlayerDisonnectEventHandler(EventHandler):
    def __init__(self):
        super().__init__("player_disconnect")
        self.__reason = "unknown"
    
    def trigger(self, player):
        r = self.__reason
        self.__reason = "unknown"
        super().trigger(player, r)

    def reason(self, reason):
        self.__reason = reason

class ChatEventHandler(EventHandler):
    """Event that triggers with chat.

    """
    def __init__(self):
        super().__init__("chat")
    
    def trigger(self, player, msg, channel):
        super().trigger(player, msg, channel)
        commands.handle_input(player, msg, channel)

class GameCountdownEventHandler(EventHandler):
    def __init__(self):
        super().__init__("game_countdown")
    
    def trigger(self):
        super().trigger()

class GameStartEventHandler(EventHandler):
    def __init__(self):
        super().__init__("game_start")
    
    def trigger(self, game):
        super().trigger(game)

class GameEndEventHandler(EventHandler):
    def __init__(self):
        super().__init__("game_end")
    
    def trigger(self, game, score, winner):
        super().trigger(game, score, winner)

class RoundCountdownEventHandler(EventHandler):
    def __init__(self):
        super().__init__("round_countdown")
    
    def trigger(self, round):
        super().trigger(round)

class RoundStartEventHandler(EventHandler):
    def __init__(self):
        super().__init__("round_start")
    
    def trigger(self, round):
        super().trigger(round)

class RoundEndEventHandler(EventHandler):
    def __init__(self):
        super().__init__("round_end")
    
    def trigger(self, score, winner):
        super().trigger(score, winner)

class TeamSwitchEventHandler(EventHandler):
    def __init__(self):
        super().__init__("team_switch")
    
    def trigger(self, player, old_team, new_team):
        super().trigger(player, old_team, new_team)

class MapEventHandler(EventHandler):
    def __init__(self):
        super().__init__("map")
    
    def trigger(self, map):
        super().trigger(map)

class VoteCalledEventHandler(EventHandler):
    def __init__(self):
        super().__init__("vote_called")
        self.__caller = None
    
    def trigger(self, vote, args):
        c = self.__caller
        self.__caller = None
        super().trigger(c, vote.lower(), args.lower())
    
    def caller(self, player):
        self.__caller = player

class VoteEndedEventHandler(EventHandler):
    def __init__(self):
        super().__init__("vote_ended")
    
    def trigger(self, passed):
        cs = minqlbot.get_configstring(9)
        if not cs:
            debug("vote_ended weird behavior.")
            return

        split_cs = cs.split()
        if len(split_cs) > 1:
            args = " ".join(split_cs[1:])
        else:
            args = None

        votes = (int(minqlbot.get_configstring(10)), int(minqlbot.get_configstring(11)))
        super().trigger(split_cs[0], args, votes, passed)
    
    def cancel(self):
        # Check if there's a current vote in the first place.
        cs = minqlbot.get_configstring(9, cached=False)
        if not cs:
            return

        res = re_vote.match(cs)
        vote = res.group("vote")
        args = res.group("args")
        votes = (int(minqlbot.get_configstring(10)), int(minqlbot.get_configstring(11)))
        # Return None if the vote's cancelled (like if the round starts before vote's over).
        super().trigger(votes, vote, args, None)

class UnloadEventHandler(EventHandler):
    def __init__(self):
        super().__init__("unload")
    
    def trigger(self, plugin):
        # We don't want to call every unload event, but just one plugin.
        if plugin in self.plugins.copy():
            for priority_level in self.plugins[plugin]:
                for handler in priority_level:
                    retval = handler()
                    if retval == minqlbot.RET_NONE or retval == None:
                        continue
                    elif retval == minqlbot.RET_STOP:
                        return
                    else:
                        debug("{}: {}@{} gave unexpected return value '{}'"
                            .format(self.name, handler.__name__, plugin, retval))

class RawEventHandler(EventHandler):
    def __init__(self):
        super().__init__("raw")
    
    def trigger(self, raw):
        super().trigger(raw)

class GamestateEventHandler(EventHandler):
    def __init__(self):
        super().__init__("gamestate")
    
    def trigger(self, index, configstring):
        super().trigger(index, configstring)

class ScoresEventHandler(EventHandler):
    def __init__(self):
        super().__init__("scores")
    
    def trigger(self, scores):
        super().trigger(scores)

class StatsEventHandler(EventHandler):
    def __init__(self):
        super().__init__("stats")
    
    def trigger(self, stats):
        super().trigger(stats)

class EventHandlerManager:
    """Holds all the event managers and provides a way to access them.

    """
    def __init__(self):
        self.__handlers = {}

    def __getitem__(self, key):
        return self.__handlers[key]

    def __contains__(self, key):
        return key in self.__handlers

    def add_handler(self, event_name, handler):
        if event_name in self:
            raise EventHandlerError("Event name already taken.")
        elif not isinstance(handler, EventHandler):
            raise EventHandlerError("Cannot add an event handler not based on EventHandler.")

        self.__handlers[event_name] = handler

    def remove_handler(self, event_name):
        if event_name not in self:
            raise EventHandlerError("Event name not found.")

        del self.__handlers[event_name]



event_handlers = EventHandlerManager()

event_handlers.add_handler("console",           ConsoleEventHandler())
event_handlers.add_handler("bot_connect",       BotConnectEventHandler())
event_handlers.add_handler("bot_disconnect",    BotDisonnectEventHandler())
event_handlers.add_handler("player_connect",    PlayerConnectEventHandler())
event_handlers.add_handler("player_disconnect", PlayerDisonnectEventHandler())
event_handlers.add_handler("chat",              ChatEventHandler())
event_handlers.add_handler("game_countdown",    GameCountdownEventHandler())
event_handlers.add_handler("game_start",        GameStartEventHandler())
event_handlers.add_handler("game_end",          GameEndEventHandler())
event_handlers.add_handler("round_countdown",   RoundCountdownEventHandler())
event_handlers.add_handler("round_start",       RoundStartEventHandler())
event_handlers.add_handler("round_end",         RoundEndEventHandler())
event_handlers.add_handler("team_switch",       TeamSwitchEventHandler())
event_handlers.add_handler("map",               MapEventHandler())
event_handlers.add_handler("vote_called",       VoteCalledEventHandler())
event_handlers.add_handler("vote_ended",        VoteEndedEventHandler())
event_handlers.add_handler("unload",            UnloadEventHandler())
event_handlers.add_handler("raw",               RawEventHandler())
event_handlers.add_handler("gamestate",         GamestateEventHandler())
event_handlers.add_handler("scores",            ScoresEventHandler())
event_handlers.add_handler("stats",             StatsEventHandler())

# Export event handler dictionary.
setattr(minqlbot, "EVENT_HANDLERS", event_handlers)

# ====================================================================
#                              PARSER    
# ====================================================================

re_chat = re.compile(r'"(?P<id>..) (?:(?P<clan>[^ \x19]+?) )?(?P<name>[^\x19]+?)..\x19: ..(?P<msg>.+)"')
re_tchat = re.compile(r'"(?P<id>..) \x19\((?:(?P<clan>[^ ]+?) )?(?P<name>.+?)..\x19\)(?: \(.+?\))?\x19: ..(?P<msg>.+)"')
re_tell = re.compile(r'"(?P<id>..) \x19\[(?:(?P<clan>[^ ]+?) )?(?P<name>.+?)\^7\x19\](?: \(.+?\))?\x19: ..(?P<msg>.+)"')
re_connect = re.compile(r'print "(?P<name>.+) connected')
re_disconnect = re.compile(r'print "(?P<name>.+) disconnected')
re_round_start = re.compile(r'cs 661 "(?P<cvars>.+)"')
re_round_end = re.compile(r'cs (?P<team>6|7) "(?P<score>.+)"')
re_game_change = re.compile(r'cs 0 "(?P<cvars>.*)"')
re_game_end = re.compile(r'cs 14 "(?P<value>.+)"')
re_kick = re.compile(r'print "(?P<name>.+) was kicked')
re_ragequit = re.compile(r'print "(?P<name>.+) \^1rage\^7quits')
re_timeout = re.compile(r'print "(?P<name>.+) timed out')
re_vote_called = re.compile(r'print "(?P<name>.+) called a vote.')
re_vote_called_ex = re.compile(r'cs 9 "(?P<vote>.+) "*(?P<args>.*?)"*"')
re_voted = re.compile(r'cs (?P<code>10|11) "(?P<count>.*)"')
re_vote_ended = re.compile(r'print "Vote (?P<result>passed|failed).')
re_player_change = re.compile(r'cs 5(?P<id>[2-5][0-9]) "(?P<cvars>.*)"')
re_scores_ca = re.compile(r'scores_ca (?P<total_players>.+?) (?P<red_score>.+?) (?P<blue_score>.+?) (?P<scores>.+)')
re_castats = re.compile(r'castats (?P<scores>.+)')

# bcs0 is a special case, as it's a configstring that's too big, so it's split into several parts.
# bcs0 indicates we start an incomplete configstring, bcs1 means we add it to the
# previous bcs0 or bcs1 string, bcs2 means the complete string has been sent.
# In our case, we'll wait until bcs2 has arrived and resend the whole cs to the handler as a normal cs.
re_bcs = re.compile(r'bcs(?P<mode>.) (?P<index>.*) "(?P<cvars>.*)"')
bcs_buffer = {} # Dict because we could possibly receive several bcs' simultaneously.

# Post-game stats are sent as separate commands, as opposed to regular scores, so we use a buffer
# and trigger the event when we receive them all.
castats_buffer = []
# The order of the players in castats depends on the scores_ca sent right before them, so we
# keep track of the order.
castats_order = []

def parse(cmdstr):
    """Parses server commands or gamestates"""
    cmd = cmdstr.split(" ", 1)
    if cmd[0] == "chat":
        rm = re_chat.match(cmd[1])
        if rm:
            # I tested the client ID passed through this command several times, and sooner
            # or later, it starts sending incorrect data. This applies for chat, tchat and tell.
            #cid = int(rm.group(1))
            player = get_player(rm.group("name"))
            msg = rm.group("msg")
            channel = minqlbot.CHAT_CHANNEL # Use static channel
            event_handlers["chat"].trigger(player, msg, channel)
            return
        else: # Check if it's \tell
            rm = re_tell.match(cmd[1])
            if rm:
                #cid = int(rm.group(1))
                player = get_player(rm.group("name"))
                msg = rm.group("msg")
                channel = TellChannel(player)
                event_handlers["chat"].trigger(player, msg, channel) 
                return
    elif cmd[0] == "tchat": # Team chat.
        rm = re_tchat.match(cmd[1])
        if rm:
            #cid = int(rm.group(1))
            player = get_player(rm.group("name"))
            msg = rm.group("msg")
            channel = minqlbot.TEAM_CHAT_CHANNEL # Use static channel
            event_handlers["chat"].trigger(player, msg, channel)
            return
    
    # big_configstring (bcs)
    res = re_bcs.match(cmdstr)
    if res:
        channel = int(res.group("mode"))
        index = int(res.group("index"))
        cvars = res.group("cvars")
        if channel == 0:
            bcs_buffer[index] = cvars
        elif channel == 1:
            bcs_buffer[index] += cvars
        elif channel == 2:
            full_cs = bcs_buffer[index] + cvars
            del bcs_buffer[index]
            handle_message('cs {} "{}"'.format(index, full_cs))
        return

    # player_connect
    res = re_connect.match(cmdstr)
    if res:
        #event_handlers["player_connect"].trigger(res.group("name"))
        return
    
    # player_disconnect
    res = re_disconnect.match(cmdstr)
    if res:
        event_handlers["player_disconnect"].reason("disconnect")
        return
    
    # round_start
    res = re_round_start.match(cmdstr)
    if res:
        cvars = parse_variables(res.group("cvars"))
        if cvars:
            round_number = int(cvars["round"])
            if round_number and "time" in cvars:
                if round_number == 1:  # This is the case when the first countdown starts.
                    event_handlers["round_countdown"].trigger(round_number)
                    return

                event_handlers["round_countdown"].trigger(round_number)
                return
            elif round_number:
                event_handlers["round_start"].trigger(round_number)
                return
    
    # round_end
    res = re_round_end.match(cmdstr)
    if res and int(res.group("score")) != 0:
        winner = minqlbot.TEAMS[int(res.group("team")) - 5] # Offset by 5
        score = (-1, -1)
        if winner == minqlbot.TEAMS[1]:
            score = (int(res.group("score")), int(minqlbot.get_configstring(7, cached=False)))
        elif winner == minqlbot.TEAMS[2]:
            score = (int(minqlbot.get_configstring(6, cached=False)), int(res.group("score")))

        # If the game was forfeited, it'll act as if the round ended, but with -999 score
        # followed by the actual score. We simply skip the -999 one, since game_ended is
        # triggered later anyway.
        if score[0] == -999 or score[1] == -999:
            return
        
        # Otherwise, regular round end.
        event_handlers["round_end"].trigger(score, winner)
        return
    
    # game_change
    res = re_game_change.match(cmdstr)
    if res:
        cvars = res.group("cvars")
        cs = minqlbot.get_configstring(0, cached=False)
        
        if cvars and cs:
            old_cvars = parse_variables(cs)
            new_cvars = parse_variables(cvars)
            old_state = old_cvars["g_gameState"]
            new_state = new_cvars["g_gameState"]
            
            if old_state != new_state:
                if old_state == "PRE_GAME" and new_state == "IN_PROGRESS":
                    event_handlers["vote_ended"].cancel() # Cancel current vote if any.
                    event_handlers["game_start"].trigger(minqlbot.Game())
                elif old_state == "PRE_GAME" and new_state == "COUNT_DOWN":
                    event_handlers["game_countdown"].trigger()
                elif old_state == "COUNT_DOWN" and new_state == "IN_PROGRESS":
                    event_handlers["vote_ended"].cancel() # Cancel current vote if any.
                    event_handlers["game_start"].trigger(minqlbot.Game())
                elif old_state == "IN_PROGRESS" and new_state == "PRE_GAME":
                    pass
                else:
                    debug("UNKNOWN GAME STATES: {} - {}".format(old_state, new_state))
            
        return
    
    # game_end
    res = re_game_end.match(cmdstr)
    if res:
        value = int(res.group("value"))
        if value == 1:
            red_score = int(minqlbot.get_configstring(6, cached=False))
            blue_score = int(minqlbot.get_configstring(7, cached=False))
            if red_score > blue_score:
                event_handlers["vote_ended"].cancel() # Cancel current vote if any.
                event_handlers["game_end"].trigger(minqlbot.Game(), (red_score, blue_score), minqlbot.TEAMS[1])
            elif red_score < blue_score:
                event_handlers["vote_ended"].cancel() # Cancel current vote if any.
                event_handlers["game_end"].trigger(minqlbot.Game(), (red_score, blue_score), minqlbot.TEAMS[2])
            else:
                debug("game_end: Weird behaviour!")
            return
    
    # kick
    res = re_kick.match(cmdstr)
    if res:
        event_handlers["player_disconnect"].reason("kick")
        return

    # ragequit
    res = re_ragequit.match(cmdstr)
    if res:
        event_handlers["player_disconnect"].reason("ragequit")
        return

    # timeout
    res = re_timeout.match(cmdstr)
    if res:
        event_handlers["player_disconnect"].reason("timeout")
        return
    
    # vote_called
    res = re_vote_called.match(cmdstr)
    if res:
        name = res.group("name")
        # Remove clan tag if any.
        n_split = name.split()
        if len(n_split) > 1:
            name = n_split[1]
        
        player = get_player(name)
        
        # We don't know yet what kind of vote it is, so no event trigger yet.
        event_handlers["vote_called"].caller(player)
        return
    
    # vote_called_ex
    res = re_vote_called_ex.match(cmdstr)
    if res:
        event_handlers["vote_called"].trigger(res.group("vote"), res.group("args"))
        return
    
    # vote_ended
    res = re_vote_ended.match(cmdstr)
    if res:
        if res.group("result") == "passed":
            event_handlers["vote_ended"].trigger(True)
        else:
            event_handlers["vote_ended"].trigger(False)
        return
    
    # player_change
    res = re_player_change.match(cmdstr)
    if res:
        cid = int(res.group("id")) - 29 # Offset by 29
        cvars = res.group("cvars")
        csn = cid + 529 # Configstring number
        cs = minqlbot.get_configstring(csn, cached=False)
        
        if cvars and cs:
            old_cvars = parse_variables(cs)
            new_cvars = parse_variables(cvars)
            
            old_team = minqlbot.TEAMS[int(old_cvars["t"])]
            new_team = minqlbot.TEAMS[int(new_cvars["t"])]
            
            if old_team != new_team:
                event_handlers["team_switch"].trigger(minqlbot.Player(cid), old_team, new_team)
        elif cvars:
            event_handlers["player_connect"].trigger(minqlbot.Player(cid))
        elif cs:
            # Make a Player instance without cached configstrings. This'll allow the plugin
            # to grab whatever info the player had before the instance is invalidated.
            event_handlers["player_disconnect"].trigger(minqlbot.Player(cid, cached=False))
            
        return

    # scores_ca
    res = re_scores_ca.match(cmdstr)
    if res:
        global castats_order
        total_players = int(res.group("total_players"))
        raw_scores = [int(i) for i in res.group("scores").split()]
        scores = []
        castats_order.clear()
        for i in range(total_players):
            castats_order.append(raw_scores[i*17])
            scores.append(minqlbot.CaScores(raw_scores[i*17:i*17+17]))
        event_handlers["scores"].trigger(scores)

    # castats
    res = re_castats.match(cmdstr)
    if res:
        global castats_buffer, castats_order
        raw_scores = [int(i) for i in res.group("scores").split()]
        cid = castats_order[0]
        del castats_order[0]
        castats_buffer.append(minqlbot.CaEndScores(cid, raw_scores))

        if not len(castats_order): # Are we ready to trigger?
            tmp = castats_buffer
            castats_buffer = []
            event_handlers["stats"].trigger(tmp)


# ====================================================================
#                       CONFIG AND PLUGIN LOADING
# ====================================================================

class PluginError(Exception):
    """Generic exception for plugin loading, unloading and such.

    """
    pass

config = configparser.ConfigParser()

def load_config():
    config_file = "python\\config.cfg"
    if os.path.isfile(config_file):
        config.read(config_file)
        config["DEFAULT"] = { 
                                "PluginsFolder" : "python\\plugins",
                                "DatabasePath"  : "python\\minqlbot.db",
                                "CommandPrefix" : "!"
                            }

        sys.path.append(os.path.dirname(config["Core"]["PluginsFolder"]))
        setattr(minqlbot, "NAME", config["Core"]["Nickname"].strip())
        setattr(minqlbot, "COMMAND_PREFIX", config["Core"]["CommandPrefix"].strip())
    else:
        raise(PluginError("Config file '{}' not found.".format(config_file)))

def reload_config():
    load_config()

def get_config():
    return config

def load_preset_plugins():
    if os.path.isdir(config["Core"]["PluginsFolder"]):
        for plugin in config["Core"]["Plugins"].split(","):
            load_plugin(plugin.strip())
    else:
        raise(PluginError("Cannot find the plugins folder."))

def load_plugin(plugin):
    debug("Loading plugin '{}'...".format(plugin))
    plugins = minqlbot.Plugin._Plugin__loaded_plugins
    if plugin in plugins:
        return reload_plugin(plugin)
    try:
        module = importlib.import_module("plugins." + plugin)
        plugin_class = getattr(module, plugin)
        if issubclass(plugin_class, minqlbot.Plugin):
            plugins[plugin] = plugin_class()
        else:
            raise(PluginError("Attempted to load a plugin that is not a subclass of 'minqlbot.Plugin'."))
    except:
        del sys.modules["plugins." + plugin]
        raise

def unload_plugin(plugin):
    debug("Unloading plugin '{}'...".format(plugin))
    plugins = minqlbot.Plugin._Plugin__loaded_plugins
    if plugin in plugins:
        event_handlers["unload"].trigger(plugin)

        # Close DB connection if any.
        plugins[plugin].db_close()

        # Unhook its hooks.
        for hook in plugins[plugin].hooks:
            plugins[plugin].remove_hook(*hook)

        # Unregister commands.
        for cmd in plugins[plugin].commands:
            plugins[plugin].remove_command(cmd.name, cmd.handler)
            
        del plugins[plugin]
        del sys.modules["plugins." + plugin]
    else:
        raise(PluginError("Attempted to unload a plugin that is not loaded."))

def reload_plugin(plugin):
    unload_plugin(plugin)
    load_plugin(plugin)

# Add these as part of the minqlbot module.
setattr(minqlbot, "reload_config", reload_config)
setattr(minqlbot, "get_config", get_config)
setattr(minqlbot, "load_plugin", load_plugin)
setattr(minqlbot, "unload_plugin", unload_plugin)
setattr(minqlbot, "reload_plugin", reload_plugin)

# ====================================================================
#                               HELPERS
# ====================================================================

def parse_variables(varstr):
    """Parses strings passed to and from the server with variables.

    Returns:
        A dictionary with the variables as keys and values as values.
    """
    res = {}
    vars = varstr.lstrip("\\").split("\\")
    try:
        for i in range(0, len(vars), 2):
            res[vars[i]] = vars[i + 1]
    except:
        debug("ERROR: parse_variables uneven number of variables.")
        debug(varstr)
        return res # Return incomplete dict.
    
    return res

# Add parse_variables as part of the minqlbot module.
setattr(minqlbot, "parse_variables", parse_variables)

def debug(dbgstr, only_debug=False):
    """A wrapper for minqlbot.debug ensuring the passed argument is a string.

    """
    if only_debug and not minqlbot.IS_DEBUG:
        return

    minqlbot.debug(str(dbgstr))

def get_player(name):
    for i in range(24):
        cs = minqlbot.get_configstring(i + 529)
        if cs:
            cvars = parse_variables(cs)
            if name == cvars["n"]:
                return minqlbot.Player(i)

    return None

# ====================================================================
#                                 MAIN
# ====================================================================
    
if __name__ == "__main__":
    # During reloading it might try to print to stderr if an error occurs, which raises
    # an exception since it does not exists. We create a dummy stderr to avoid that.
    from io import StringIO
    sys.stderr = StringIO()

    sys.path.append(os.getcwd() + "\\python")
    load_config()
    load_preset_plugins()


