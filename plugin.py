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

import minqlbot
import sqlite3
import threading
import datetime
import re

# Export hook priority levels.
setattr(minqlbot, "PRI_HIGHEST", 0)
setattr(minqlbot, "PRI_HIGH",    1)
setattr(minqlbot, "PRI_NORMAL",  2)
setattr(minqlbot, "PRI_LOW",     3)
setattr(minqlbot, "PRI_LOWEST",  4)

# Configstring cache. See get_configstring() for details.
cs_cache = {}
cache_lock = threading.Lock()
setattr(minqlbot, "_CS_CACHE", cs_cache)
setattr(minqlbot, "_CS_CACHE_LOCK", cache_lock)

def get_configstring(index, cached=True):
    """Wraps minqlbot._configstring and gives the option of cached configstrings.

    When a "cs" command is sent by the server, the client will replace its configstring
    with the one sent by the server. However, we parse those before the client has had
    time to do so. This means that if a plugin that hooks "game_start", for instance,
    calls Plugin.game() that uses minqlbot._configstring, the Game instance will have
    outdated information. This function solves the issue by storing configstrings on
    the Python side of things as well and returning those unless explicitly told not to
    with the "cached" keyword.

    """
    global cs_cache
    with cache_lock:
        if cached and index not in cs_cache:
            cs = minqlbot._configstring(index)
            cs_cache[index] = cs
            return cs
        elif not cached:
            return minqlbot._configstring(index)
        else:
            return cs_cache[index]

setattr(minqlbot, "get_configstring", get_configstring)

# Export special channel for commands that will trigger on all channels.
setattr(minqlbot, "CMD_ALL_CHANNELS",  0)

class NonexistentPlayerError(Exception):
    pass

class Player():
    """A class that represents a player on the server the bot's connected to.

    """
    def __init__(self, cid, cached=True, configstring_func=get_configstring):
        if cid < 0 or cid > 31:
            raise ValueError("The client ID should be a value between 0 and 31.")
        self.cached = cached
        self.__id = cid
        self.__valid = True
        self.__name = ""
        self.configstring = configstring_func
        try:
            self.__name = self.clean_name
        except NonexistentPlayerError:
            self.__invalidate("Tried to initialize a Player instance of a nonexistant player.")    

    def __repr__(self):
        try:
            return "{}({}:'{}'@'{}'')".format(self.__class__.__name__, self.__id, self.clean_name, self.team)
        except NonexistentPlayerError:
            return "{}(INVALID:'{}')".format(self.__class__.__name__, self.clean_name)

    def __str__(self):
        return self.name

    def __contains__(self, key):
        if not self.__valid:
            self.__invalidate()

        cs = self.configstring(529 + self.__id, self.cached)
        if not cs:
            self.__invalidate()

        cvars = minqlbot.parse_variables(cs)
        return key in cvars

    def __getitem__(self, key):
        if not self.__valid:
            self.__invalidate()

        cs = self.configstring(529 + self.__id, self.cached)
        if not cs:
            self.__invalidate()

        cvars = minqlbot.parse_variables(cs)
        # Could still be invalid, so we need to check the name.
        if self.__name and self.__name.lower() != re.sub(r"\^[0-9]", "", cvars["n"]).lower():
            self.__invalidate()
        return cvars[key]

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.clean_name.lower() == other.clean_name.lower()
        else:
            return self.clean_name.lower() == str(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __invalidate(self, e="The player does not exist anymore. Did the player disconnect?"):
        self.__valid = False
        raise NonexistentPlayerError(e)
    
    @property
    def id(self):
        if self.valid:
            return self.__id
        else:
            raise NonexistentPlayerError()
    
    @property
    def name(self):
        try:
            return self["n"]
        except NonexistentPlayerError:
            return self.__name

    @property
    def clean_name(self):
        """Removes color tags from the name."""
        return re.sub(r"\^[0-9]", "", self.name)

    @property
    def name_with_clantag(self):
        tag = self.clantag
        if not tag:
            return self.name
        else:
            return "{} {}".format(self.clantag, self.name)

    @property
    def clantag(self):
        """Returns the clan tag."""
        return self["cn"]

    @property
    def clan(self):
        """Returns the full clan name.

        """
        return self["xcn"]
    
    @property
    def team(self):
        return minqlbot.TEAMS[int(self["t"])]
    
    @property
    def colors(self):
        return float(self["c1"]), float(self["c2"])
    
    @property
    def model(self):
        return self["model"]

    @property
    def country(self):
        return self["c"]

    @property
    def valid(self):
        try:
            self["n"]
            return True
        except NonexistentPlayerError:
            return False

    def tell(self, msg):
        return Plugin.tell(msg, self)

    def kick(self):
        return Plugin.kick(self)

    def kickban(self):
        return Plugin.kickban(self)

    def op(self):
        return Plugin.op(self)

    def deop(self):
        return Plugin.deop(self)

    def mute(self):
        return Plugin.mute(self)

    def unmute(self):
        return Plugin.unmute(self)

    def put(self, team):
        return Plugin.put(self, team)

    def switch(self, other_player):
        return Plugin.switch(self, other_player)

    def follow(self):
        return Plugin.follow(self)

class DummyPlayer(Player):
    def __init__(self, name):
        self.cs = (
            "n\\{}\\t\\0\\model\\major\\hmodel\\major\\"
            "c1\\2\\c2\\2\\hc\\100\\w\\0\\l\\0\\skill\\4.00\\"
            "tt\\0\\tl\\0\\rp\\1\\p\\0\\so\\0\\pq\\0\\wp\\rl\\"
            "ws\\mg\\cn\\\\su\\0\\xcn\\\\c\\"
        ).format(name)
        super().__init__(31, configstring_func=self.dummy_configstring)

    def dummy_configstring(self, id, cached):
        return self.cs

    @property
    def id(self):
        return -1


class NonexistentGameError(Exception):
    """An exception raised when accessing properties on an invalid game.

    """
    pass

class Game():
    """Holds information about the game and the server itself.

    """
    def __init__(self, cached=True):
        self.cached = cached
        self.__valid = True
        cs = minqlbot.get_configstring(0, self.cached)
        if not cs:
            self.__valid = False
            raise NonexistentPlayerError("Tried to initialize a Game instance with no active game.")

    def __repr__(self):
        try:
            return "{}({}@{})".format(self.__class__.__name__, self.short_type, self.short_map)
        except NonexistentGameError:
            return "{}(N/A@N/A)".format(self.__class__.__name__)

    def __str__(self):
        try:
            return "{} on {}".format(self.type, self.map)
        except NonexistentGameError:
            return "Invalid game"

    def __contains__(self, key):
        cs = minqlbot.get_configstring(0, self.cached)
        if not cs:
            self.__valid = False
            raise NonexistentGameError("Invalid game. Did the bot disconnect?")
            
        cvars = minqlbot.parse_variables(cs)
        return key in cvars

    def __getitem__(self, key):
        cs = minqlbot.get_configstring(0, self.cached)
        if not cs:
            self.__valid = False
            raise NonexistentGameError("Invalid game. Did the bot disconnect?")

        cvars = minqlbot.parse_variables(cs)
        return cvars[key]

    @property
    def type(self):
        return minqlbot.GAMETYPES[int(self["g_gametype"])]

    @property
    def short_type(self):
        return minqlbot.GAMETYPES_SHORT[int(self["g_gametype"])]

    @property
    def map(self):
        return minqlbot.get_configstring(3, self.cached)

    @property
    def short_map(self):
        return self["mapname"]

    @property
    def red_score(self):
        return int(minqlbot.get_configstring(6, self.cached))

    @property
    def blue_score(self):
        return int(minqlbot.get_configstring(7, self.cached))

    @property
    def state(self):
        s = self["g_gameState"]
        if s == "PRE_GAME":
            return "warmup"
        elif s == "COUNT_DOWN":
            return "countdown"
        elif s == "IN_PROGRESS":
            return "in_progress"
        else:
            return self["g_gameState"]

    @property
    def location(self):
        return self["sv_location"]

    @property
    def hostname(self):
        return self["sv_hostname"]

    @property
    def is_instagib(self):
        return bool(int(self["g_instaGib"]))

    @property
    def is_premium(self):
        return bool(int(self["sv_premium"]))

    @property
    def maxclients(self):
        return int(self["sv_maxclients"])

    @property
    def ruleset(self):
        return minqlbot.RULESETS[int(self["ruleset"])]

    @property
    def timelimit(self):
        return int(self["timelimit"])

    @property
    def fraglimit(self):
        return int(self["fraglimit"])

    @property
    def roundlimit(self):
        return int(self["roundlimit"])

    @property
    def roundtimelimit(self):
        return int(self["roundtimelimit"])

    @property
    def scorelimit(self):
        return int(self["scorelimit"])

    @property
    def skillrating(self):
        return int(self["sv_skillrating"])

    @property
    def capturelimit(self):
        return int(self["capturelimit"])

    @property
    def teamsize(self):
        return self["teamsize"]

    @staticmethod
    def abort():
        return Plugin.abort()

    @staticmethod
    def timeout():
        return Plugin.timeout()

    @staticmethod
    def timein():
        return Plugin.timein()

    @staticmethod
    def pause():
        return Plugin.pause()

    @staticmethod
    def unpause():
        return Plugin.unpause()

    @staticmethod
    def scores():
        return Plugin.scores()

class Scores():
    def __init__(self, cid, score, ping):
        self.player = Player(cid)
        self.score = score
        self.ping = ping

class Stats():
    def __init__(self, cid):
        self.player = Player(cid)

class CaScores(Scores):
    def __init__(self, scores):
        super().__init__(scores[0], scores[3], scores[4])
        self.team = minqlbot.TEAMS[scores[1]]
        self.premium = bool(scores[2])
        self.time = scores[5]
        self.kills = scores[6]
        self.deaths = scores[7]
        self.accuracy = scores[8]
        self.best_weapon = scores[9]
        self.best_weapon_accuracy = scores[10]
        self.damage_done = scores[11]
        self.impressives = scores[12]
        self.excellents = scores[13]
        self.humiliations = scores[14]
        self.perfect = scores[15]
        self.alive = bool(scores[16])

class CaEndStats(Stats):
    def __init__(self, id_, scores):
        super().__init__(id_)
        self.damage_done = scores[1]
        self.damage_received = scores[2]
        self._gaunt_accuracy = scores[3]
        self.gaunt_kills = scores[4]
        self.mg_accuracy = scores[5]
        self.mg_kills = scores[6]
        self.sg_accuracy = scores[7]
        self.sg_kills = scores[8]
        self.gl_accuracy = scores[9]
        self.gl_kills = scores[10]
        self.rl_accuracy = scores[11]
        self.rl_kills = scores[12]
        self.lg_accuracy = scores[13]
        self.lg_kills = scores[14]
        self.rg_accuracy = scores[15]
        self.rg_kills = scores[16]
        self.pg_accuracy = scores[17]
        self.pg_kills = scores[18]
        self._wpn9_accuracy = scores[19]
        self._wpn9_kills = scores[20]
        self._wpn10_accuracy = scores[21]
        self._wpn10_kills = scores[22]
        self._wpn11_accuracy = scores[23]
        self._wpn11_kills = scores[24]
        self._wpn12_accuracy = scores[25]
        self._wpn12_kills = scores[26]
        self._wpn13_accuracy = scores[27]
        self._wpn13_kills = scores[28]
        self.hmg_accuracy = scores[29]
        self.hmg_kills = scores[30]
        self._wpn15_accuracy = scores[31]
        self._wpn15_kills = scores[32]

class RaceScores(Scores):
    def __init__(self, scores):
        super().__init__(scores[0], scores[2], scores[3])
        self.team = self.player.team
        self._unk = scores[1]
        self.time = scores[4]

    @property
    def best_time(self):
        """Return the best time as a string, like the QL scoreboard, rather than the raw integer scores_race uses."""
        td = self.best_time_timedelta
        if td == None:
            return "-"

        hours = td.seconds // 3600
        if hours:
            return "{:d}:{:d}:{:02d}.{:03d}".format(hours, (td.seconds // 60) % 60, td.seconds % 60, (td.microseconds // 1000) % 1000)
        else:
            return "{:d}:{:02d}.{:03d}".format((td.seconds // 60) % 60, td.seconds % 60, (td.microseconds // 1000) % 1000)

    @property
    def best_time_timedelta(self):
        """Return the player's best time in the form of a timedelta instance."""
        if self.score == -1: # -1 is when a player hasn't finished a lap.
            return None

        score_string = str(self.score)
        return datetime.timedelta(seconds=int(score_string[:-3]), milliseconds=int(score_string[-3:]))
    

class Plugin():
    """The base plugin class.

    Every plugin must inherit this or a subclass of this.
    """
    # Static dictionary of plugins currently loaded for the purpose of inter-plugin communication.
    __loaded_plugins = {}

    def __init__(self):
        self.__hooks = []
        self.__commands = []
        self.db_connections = {}
        self.db_lock = threading.Lock()

    @property
    def name(self):
        return self.__class__.__name__
    
    @property
    def plugins(self):
        return self.__loaded_plugins.copy()

    @property
    def hooks(self):
        if not hasattr(self, "_Plugin__hooks"):
            self.__hooks = []
        return self.__hooks.copy()

    @property
    def commands(self):
        if not hasattr(self, "_Plugin__commands"):
            self.__commands = []
        return self.__commands.copy()
    
    @classmethod
    def __player_configstrings(cls):
        players = {}
        for i in range(24):
            cs = minqlbot.get_configstring(i + 529)
            if cs:
                players[i] = cs
        
        return players

    @classmethod
    def __dummy_player(cls, name):
        """Return a Player instance with the bot's name, but generic cvars and invalid client id.

        """
        return DummyPlayer(name)

    def add_hook(self, event, handler, priority=minqlbot.PRI_NORMAL):
        if not hasattr(self, "_Plugin__hooks"):
            self.__hooks = []
            
        self.__hooks.append((event, handler, priority))
        minqlbot.EVENT_HANDLERS[event].add_hook(self.name, handler, priority)

    def remove_hook(self, event, handler, priority=minqlbot.PRI_NORMAL):
        if not hasattr(self, "_Plugin__hooks"):
            self.__hooks = []
            return
        
        minqlbot.EVENT_HANDLERS[event].remove_hook(self.name, handler, priority)
        self.__hooks.remove((event, handler, priority))

    def add_command(self, name, handler, permission=0, channels=minqlbot.CMD_ALL_CHANNELS, exclude_channels=(), priority=minqlbot.PRI_NORMAL, usage=""):
        if not hasattr(self, "_Plugin__commands"):
            self.__commands = []
        
        cmd = minqlbot.Command(self, name, handler, permission, channels, exclude_channels, usage)    
        self.__commands.append(cmd)
        minqlbot.COMMANDS.add_command(cmd, priority)

    def remove_command(self, name, handler):
        if not hasattr(self, "_Plugin__commands"):
            self.__commands = []
            return
        
        for cmd in self.__commands:
            if cmd.name == name and cmd.handler == handler:
                minqlbot.COMMANDS.remove_command(cmd)
    
    @classmethod
    def players(cls):
        """Get a list of all the players on the server.
        
        """
        player_list = []
        players_cs = cls.__player_configstrings()
        for index in players_cs:
            player_list.append(Player(index))
        
        return player_list

    @classmethod
    def player(cls, name, player_list=None):
        """Get the player instance of a single player.
        
        """
        # In case 'name' isn't a string.
        if isinstance(name, Player):
            return name
        elif isinstance(name, int):
            return Player(name)


        if not player_list:
            players = cls.players()
        else:
            players = player_list

        # When we're disconnected, the list should be empty, so if 'name' is the bot itself,
        # we make a dummy player instance. This is useful for functions that also should
        # work while disconnected by perhaps expect a Player instance to check the name or whatnot.
        if not players and name == minqlbot.NAME:
            return cls.__dummy_player(name)

        cid = cls.client_id(name, players)

        for p in players:
            if p.id == cid:
                return p

        return None

    @classmethod
    def game(cls):
        """Get a Game instance.

        """
        try:
            return Game()
        except NonexistentGameError:
            return None
        
    @classmethod
    def debug(cls, msg, only_debug=False):
        """Send a debug string that can be picked up by DebugView or similar applications.
        
        Args:
            msg (str): The string to be passed.
            only_debug (bool, optional): If true, only send if this is a debug build.
                Send otherwise.
        
        """
        if only_debug and not minqlbot.IS_DEBUG:
            return
        else:
            minqlbot.debug("[{}] {}".format(cls.__name__, str(msg)))

    @classmethod
    def send_command(cls, cmd):
        """minqlbot.send_command is a C++ function, so we wrap it for Python debugging purposes.

        """
        minqlbot.send_command(cmd)
    
    @classmethod
    def msg(cls, msg, chat_channel="chat"):
        """Send a message to the chat, private message, or the console.
        
        """
        if isinstance(chat_channel, minqlbot.AbstractChannel):
            chat_channel.reply(msg)
        elif chat_channel == minqlbot.CHAT_CHANNEL:
            minqlbot.CHAT_CHANNEL.reply(msg)
        elif chat_channel == minqlbot.TEAM_CHAT_CHANNEL:
            minqlbot.TEAM_CHAT_CHANNEL.reply(msg)
        elif chat_channel == minqlbot.CONSOLE_CHANNEL:
            minqlbot.CONSOLE_CHANNEL.reply(msg)
    
    @classmethod
    def console(cls, text):
        """Send text to be printed by the console.
        
        """
        minqlbot.console_print(str(text))

    @classmethod
    def clean_text(cls, text):
        """Removes color tags from text.
        
        """
        return re.sub(r"\^[^\^]", "", text)

    @classmethod
    def clean_name(cls, name, clan=False):
        """Removes color tags from names. Removes clantags by default.

        Args:
            name (str): The name to clean.
            clan (bool): Whether to keep or remove clantags if present.
        
        """
        clean = cls.clean_text(name)
        split = clean.split()
        if not clan and len(split) > 1:
            return split[1]
        else:
            return clean
    
    @classmethod
    def colored_name(cls, name, clan=False, player_list=None):
        """Get the colored name of a decolored name.
        
        """
        if isinstance(name, Player):
            return name.name

        if not player_list:
            players = cls.players()
        else:
            players = player_list
        
        clean = cls.clean_name(name).lower()
        for p in players:
            if p.clean_name.lower() == clean:
                    split = p.name.split()
                    if not clan and len(split) > 1:
                        return split[1]
                    else:
                        return split[0]

        return None

    @classmethod
    def client_id(cls, name, player_list=None):
        """Get a player's client id from the name or Player object.

        """
        if isinstance(name, int):
            return name
        elif isinstance(name, Player):
            return name.id

        if not player_list:
            players = cls.players()
        else:
            players = player_list

        clean = cls.clean_name(name).lower()
        for p in players:
            if p.clean_name.lower() == clean:
                return p.id

        return None

    @classmethod
    def player_name(cls, cid, player_list=None):
        """Get a player's name from a client id.

        """
        if not player_list:
            players = cls.players()
        else:
            players = player_list

        for p in players:
            if p.id == cid:
                return p.name

        return None

    @classmethod
    def find_player(cls, begins, player_list=None):
        """Find a player based on what the name starts with.

        Args:
            begins: The beginning of a player's full name.

        """
        if not player_list:
            players = cls.players()
        else:
            players = player_list

        # Try the exact name first.
        clean = cls.clean_name(begins).lower()
        for p in players:
            if p.clean_name.lower() == clean:
                return p

        # Search with regex
        r = re.compile("{}.*".format(clean))
        for p in players:
            if r.match(p.clean_name.lower()):
                return p
        return None

    @classmethod
    def teams(cls, player_list=None):
        """Get a dictionary with the teams as keys and players as values

        """
        if not player_list:
            players = cls.players()
        else:
            players = player_list

        res = dict.fromkeys(minqlbot.TEAMS)
        for key in res:
            res[key] = []

        for p in players:
            res[p.team].append(p)

        return res

    @classmethod
    def tell(cls, msg, recipient):
        """Send a tell (private message) to someone.

        """
        cid = cls.client_id(recipient)

        if cid != None:
            cls.send_command('tell {} "{}"'.format(cid, msg))
            return True
        else:
            return False

    @classmethod
    def delay(cls, interval, function, args=[], kwargs={}):
        """Delay a function call by a certain amount of time

        """
        t = threading.Timer(interval, function, args, kwargs)
        t.start()
        return t

    @classmethod
    def is_vote_active(cls):
        if minqlbot.get_configstring(9):
            return True
        else:
            return False

    @classmethod
    def current_vote_count(cls):
        yes = get_configstring(10)
        no = get_configstring(11)
        if yes and no:
            return (int(yes), int(no))
        else:
            return None

    @classmethod
    def callvote(cls, vote):
        cls.send_command("callvote {}".format(vote))
        return True
    
    @classmethod
    def vote_yes(cls):
        cls.send_command("vote yes")
        return True
    
    @classmethod
    def vote_no(cls):
        cls.send_command("vote no")
        return True

    @classmethod
    def change_name(cls, name):
        cls.send_command("name {}".format(name))
        return True

    @classmethod
    def teamsize(cls, size):
        if not cls.is_vote_active():
            cls.callvote("teamsize {}".format(size))
            cls.vote_yes()
            return True
        else:
            return False

    @classmethod
    def kick(cls, player):
        player = cls.player(player) #cls.player() can handle str, Player and int
        if not cls.is_vote_active():
            cls.callvote("kick {}".format(player.clean_name))
            cls.vote_yes()
            return True
        else:
            return False
    
    @classmethod
    def shuffle(cls):
        if not cls.is_vote_active():
            cls.callvote("shuffle")
            cls.vote_yes()
            return True
        else:
            return False

    @classmethod
    def cointoss(cls):
        if not cls.is_vote_active():
            cls.callvote("cointoss")
            cls.vote_yes()
            return True
        else:
            return False

    @classmethod
    def changemap(cls, map_):
        if not cls.is_vote_active():
            cls.callvote("map {}".format(map_))
            cls.vote_yes()
            return True
        else:
            return False

    @classmethod
    def ruleset(cls, ruleset):
        if not cls.is_vote_active():
            cls.callvote("ruleset {}".format(ruleset))
            cls.vote_yes()
            return True
        else:
            return False
    
    @classmethod
    def switch(cls, p1, p2, player_list=None):
        if not player_list:
            players = cls.players()
        else:
            players = player_list

        p1_p = cls.player(p1, players)
        p2_p = cls.player(p2, players)

        if not p1_p or not p2_p:
            return False

        if p1_p.team == "red" and p2_p.team == "blue":
            cls.put(p1_p, "spectator")
            cls.put(p2_p, "red")
            cls.put(p1_p, "blue")
            return True
        elif p2_p.team == "red" and p1_p.team == "blue":    
            cls.put(p1_p, "spectator")
            cls.put(p2_p, "blue")
            cls.put(p1_p, "red")
            return True
        else:
            return False

    @classmethod
    def follow(cls, name):
        cid = cls.client_id(name)

        if cid != None:
            cls.send_command("follow {}".format(cid))
            return True
        return False

    @classmethod
    def scores(cls):
        cls.send_command("score")
        return True

    # ====================================================================
    #                       OWNER AND OP COMMANDS
    # ====================================================================
    
    @classmethod
    def op(cls, name):
        cid = cls.client_id(name)

        if cid != None:
            cls.send_command("op {}".format(cid))
            return True
        return False
    
    @classmethod
    def deop(cls, name):
        cid = cls.client_id(name)
            
        if cid != None:
            cls.send_command("deop {}".format(cid))
            return True
        return False
    
    @classmethod
    def mute(cls, name):
        cid = cls.client_id(name)
            
        if cid != None:
            cls.send_command("mute {}".format(cid))
            return True
        return False
    
    @classmethod
    def unmute(cls, name):
        cid = cls.client_id(name)
            
        if cid != None:
            cls.send_command("unmute {}".format(cid))
            return True
        return False
    
    @classmethod
    def opsay(cls, msg):
        cls.send_command('opsay "{0}"'.format(msg))
        return True
    
    @classmethod
    def abort(cls):
        cls.send_command('abort')
        return True
    
    @classmethod
    def allready(cls):
        cls.send_command('allready')
        return True
    
    @classmethod
    def timeout(cls):
        cls.send_command('timeout')
        return True
    
    @classmethod
    def timein(cls):
        cls.send_command('timein')
        return True
    
    @classmethod
    def pause(cls):
        cls.send_command('pause')
        return True
    
    @classmethod
    def unpause(cls):
        cls.send_command('unpause')
        return True
        
    @classmethod
    def lock(cls, team=None):
        # You can lock both teams when no argument is passed.
        if not team:
            cls.send_command('lock')
        else:
            cls.send_command('lock {}'.format(team))
        return True
    
    @classmethod
    def unlock(cls, team=None):
        # You can unlock both teams when no argument is passed.
        if not team:
            cls.send_command('unlock')
        else:
            cls.send_command('unlock {}'.format(team))
        return True
    
    @classmethod
    def stopserver(cls):
        cls.send_command('stopserver')
        return True
    
    @classmethod
    def banlist(cls):
        cls.send_command('banlist')
        return True
    
    @classmethod
    def put(cls, player, team):
        cid = cls.client_id(player)
            
        if cid != None:
            cls.send_command("put {} {}".format(cid, team))
            return True
        return False
    
    @classmethod
    def kickban(cls, player):
        cid = cls.client_id(player)
            
        if cid != None:
            cls.send_command("kickban {}".format(cid))
            return True
        return False


    # ====================================================================
    #                          DATABASE STUFF
    # ====================================================================

    
    def db_query(self, query, *params):
        """Execute a database query to whatever database is specified in the config.

        Plugins share the bot's connection. Threads should create a new one.

        """
        c = self.db_connect().cursor()
        return c.execute(query, params)
    
    def db_querymany(self, query, *params):
        c = self.db_connect().cursor()
        return c.executemany(query, params)

    def db_connect(self):
        """Returns a connection for the current thread.

        """
        thread = threading.current_thread()
        if not self.db_is_connected(thread):
            db = minqlbot.get_config()["Core"]["DatabasePath"]
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON") # Enforce foreign keys.
            cursor.execute("PRAGMA busy_timeout = 5000") # Wait 5s if it gets locked.
            with self.db_lock:
                self.db_connections[thread] = conn
            return conn
        else:
            with self.db_lock:
                return self.db_connections[thread]

    def db_is_connected(self, thread=None):
        """Check if the current thread has a connection open.

        """
        if thread == None:
            thread = threading.current_thread()

        # A lock for accessing the connections dictionary.
        if not hasattr(self, "db_lock"):
            self.db_lock = threading.Lock()

        with self.db_lock:
            if not hasattr(self, "db_connections"):
                self.db_connections = {}

            if thread in self.db_connections:
                return True
            else:
                return False
    
    def db_commit(self):
        """Commit database changes on the plugin's connection.

        """
        if self.db_is_connected():
            self.db_connect().commit()
    
    def db_close(self):
        """Close the database connection of the current thread.

        Connections can be left open, but keep in mind that open transactions will
        be discarded if the connection is unreferenced by the time the garbage collector
        comes around. However, considering we keep a dictionary with the connections,
        we could potentially end up with a lot of open connections on dead threads.
        To avoid that, we make this function also check for dead threads and remove
        the reference to them.

        """
        if self.db_is_connected():
            self.db_connect().close()
            thread = threading.current_thread()
            del self.db_connections[thread]

        self.db_check_dead_threads()


    def db_check_dead_threads(self):
        """Check for dead threads and remove the reference to its connection.

        """
        # A lock for accessing the connections dictionary.
        if not hasattr(self, "db_lock"):
            self.db_lock = threading.Lock()

        with self.db_lock:
            for thread in self.db_connections.copy():
                # threading.current_thread() returns a _DummyThread instance if it's a thread not
                # created by Python. Unfortunately, calling is_alive() on one will throw an exception.
                # It's some really fucked up behavior by Python, because even __repr__() calls
                # is_alive() at some point, meaning we can't even use str() on the god damn instance.
                # Luckily, we don't really make threads outside of Python that die, so if an
                # AssertionError exception is raised, we know it's a dummy thread we can skip.
                try:
                    if not thread.is_alive():
                        self.debug("Thread reference '{}' deleted!".format(thread.ident))
                        del self.db_connections[thread]
                except AssertionError:
                    continue

    
    def get_permission(self, player):
        """Get a player's permission level.

        """
        if isinstance(player, str):
            clean = self.clean_name(player).lower()
        elif isinstance(player, Player):
            clean = player.clean_name.lower()
        elif isinstance(player, int):
            clean = self.player(player).clean_name.lower()
        else:
            return None

        if clean == minqlbot.NAME.lower():
            return 999
        
        c = self.db_query("SELECT permission FROM Players WHERE name=?", clean)
        row = c.fetchone()
        if row:
            return row[0]
        else:
            return None

    def has_permission(self, player, level=5):
        """Check if a player has at least a certain permission level.

        """
        # if level is 0, just return True right away.
        if level == 0:
            return True

        lvl = self.get_permission(player)

        if lvl != None and lvl >= level:
            return True
        else:
            return False


# Export the classes.
setattr(minqlbot, "Player",  Player)
setattr(minqlbot, "DummyPlayer", DummyPlayer)
setattr(minqlbot, "Game",  Game)
setattr(minqlbot, "Scores",  Scores)
setattr(minqlbot, "Stats",  Stats)
setattr(minqlbot, "CaScores",  CaScores)
setattr(minqlbot, "CaEndStats",  CaEndStats)
setattr(minqlbot, "RaceScores",  RaceScores)
setattr(minqlbot, "Plugin",  Plugin)

# ====================================================================
#                               HELPERS
# ====================================================================

