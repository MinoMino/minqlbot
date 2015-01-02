# minqlbot - A Quake Live server administrator bot.
# Copyright (C) Mino <mino@minomino.org>

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

# Export hook priority levels.
setattr(minqlbot, "PRI_HIGHEST", 0)
setattr(minqlbot, "PRI_HIGH",    1)
setattr(minqlbot, "PRI_NORMAL",  2)
setattr(minqlbot, "PRI_LOW",     3)
setattr(minqlbot, "PRI_LOWEST",  4)

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
        if self.__valid:
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
    
    def __player_configstrings(self):
        players = {}
        for i in range(24):
            cs = minqlbot.get_configstring(i + 529)
            if cs:
                players[i] = cs
        
        return players

    def __dummy_player(self, name):
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
    
    def players(self):
        """Get a list of all the players on the server.
        
        """
        player_list = []
        players_cs = self.__player_configstrings()
        for index in players_cs:
            player_list.append(Player(index))
        
        return player_list

    def player(self, name, player_list=None):
        """Get the player instance of a single player.
        
        """
        # In case 'name' isn't a string.
        if isinstance(name, Player):
            return name
        elif isinstance(name, int):
            return Player(name)


        if not player_list:
            players = self.players()
        else:
            players = player_list

        # When we're disconnected, the list should be empty, so if 'name' is the bot itself,
        # we make a dummy player instance. This is useful for functions that also should
        # work while disconnected by perhaps expect a Player instance to check the name or whatnot.
        if not players and name == minqlbot.NAME:
            return self.__dummy_player(name)

        cid = self.client_id(name, players)

        for p in players:
            if p.id == cid:
                return p

        return None

    def game(self):
        """Get a Game instance.

        """
        try:
            return Game()
        except NonexistentGameError:
            return None
        
    def debug(self, msg, only_debug=False):
        """Send a debug string that can be picked up by DebugView or similar applications.
        
        Args:
            msg (str): The string to be passed.
            only_debug (bool, optional): If true, only send if this is a debug build.
                Send otherwise.
        
        """
        if only_debug and not minqlbot.IS_DEBUG:
            return
        else:
            minqlbot.debug("[{}] {}".format(type(self).__name__, str(msg)))

    def send_command(self, cmd):
        """minqlbot.send_command is a C++ function, so we wrap it for Python debugging purposes.

        """
        #self.debug("=> " + cmd, only_debug=True)
        minqlbot.send_command(cmd)
    
    def msg(self, msg, chat_channel="chat"):
        """Send a message to the chat, private message, or the console.
        
        """
        if chat_channel == "chat":
            self.send_command('say "{}"'.format(msg))
        elif chat_channel == "team_chat":
            self.send_command('say_team "{}"'.format(msg))
        elif chat_channel == "console":
            # Append newline since that's how chat behaves.
            self.console(msg + '\n')
    
    def console(self, text):
        """Send text to be printed by the console.
        
        """
        minqlbot.console_print(str(text))

    def clean_text(self, text):
        """Removes color tags from text.
        
        """
        return re.sub(r"\^[^\^]", "", text)

    def clean_name(self, name, clan=False):
        """Removes color tags from names. Removes clantags by default.

        Args:
            name (str): The name to clean.
            clan (bool): Whether to keep or remove clantags if present.
        
        """
        clean = self.clean_text(name)
        split = clean.split()
        if not clan and len(split) > 1:
            return split[1]
        else:
            return clean
    
    def colored_name(self, name, clan=False, player_list=None):
        """Get the colored name of a decolored name.
        
        """
        if isinstance(name, Player):
            return name.name

        if not player_list:
            players = self.players()
        else:
            players = player_list
        
        clean = self.clean_name(name).lower()
        for p in players:
            if p.clean_name.lower() == clean:
                    split = p.name.split()
                    if not clan and len(split) > 1:
                        return split[1]
                    else:
                        return split[0]

        return None

    def client_id(self, name, player_list=None):
        """Get a player's client id from the name or Player object.

        """
        if isinstance(name, int):
            return name
        elif isinstance(name, Player):
            return name.id

        if not player_list:
            players = self.players()
        else:
            players = player_list

        clean = self.clean_name(name).lower()
        for p in players:
            if p.clean_name.lower() == clean:
                return p.id

        return None

    def player_name(self, cid, player_list=None):
        """Get a player's name from a client id.

        """
        if not player_list:
            players = self.players()
        else:
            players = player_list

        for p in players:
            if p.id == cid:
                return p.name

        return None

    def find_player(self, begins, player_list=None):
        """Find a player based on what the name starts with.

        Args:
            begins: The beginning of a player's full name.

        """
        if not player_list:
            players = self.players()
        else:
            players = player_list

        # Try the exact name first.
        clean = self.clean_name(begins).lower()
        for p in players:
            if p.clean_name.lower() == clean:
                return p

        # Search with regex
        r = re.compile("{}.*".format(clean))
        for p in players:
            if r.match(p.clean_name.lower()):
                return p
        return None

    def teams(self, player_list=None):
        """Get a dictionary with the teams as keys and players as values

        """
        if not player_list:
            players = self.players()
        else:
            players = player_list

        res = dict.fromkeys(minqlbot.TEAMS)
        for key in res:
            res[key] = []

        for p in players:
            res[p.team].append(p)

        return res

    def tell(self, msg, recipient):
        """Send a tell (private message) to someone.

        """
        cid = self.client_id(recipient)

        if cid != None:
            self.send_command('tell {} "{}"'.format(cid, msg))
            return True
        else:
            return False

    def delay(self, interval, function, args=[], kwargs={}):
        """Delay a function call by a certain amount of time

        """
        t = threading.Timer(interval, function, args, kwargs)
        t.start()
        return t

    def is_vote_active(self):
        if minqlbot.get_configstring(9):
            return True
        else:
            return False

    def current_vote_count(self):
        yes = get_configstring(10)
        no = get_configstring(11)
        if yes and no:
            return (int(yes), int(no))
        else:
            return None

    def callvote(self, vote):
        self.send_command("callvote {}".format(vote))
    
    def vote_yes(self):
        self.send_command("vote yes")
    
    def vote_no(self):
        self.send_command("vote no")

    def change_name(self, name):
        self.send_command("name {}".format(name))

    def teamsize(self, size):
        if not self.is_vote_active():
            self.callvote("teamsize {}".format(size))
            self.vote_yes()
            return True
        else:
            return False

    def kick(self, player):
        player = self.player(player) #self.player() can handle str, Player and int
        if not self.is_vote_active():
            self.callvote("kick {}".format(player.clean_name))
            self.vote_yes()
            return True
        else:
            return False
    
    def shuffle(self):
        if not self.is_vote_active():
            self.callvote("shuffle")
            self.vote_yes()
            return True
        else:
            return False

    def cointoss(self):
        if not self.is_vote_active():
            self.callvote("cointoss")
            self.vote_yes()
            return True
        else:
            return False

    def changemap(self, map_):
        if not self.is_vote_active():
            self.callvote("callvote map {}".format(map_))
            self.vote_yes()
            return True
        else:
            return False

    def ruleset(self, ruleset):
        if not self.is_vote_active():
            self.callvote("ruleset {}".format(ruleset))
            self.vote_yes()
            return True
        else:
            return False
    
    def switch(self, p1, p2, player_list=None):
        if not player_list:
            players = self.players()
        else:
            players = player_list

        p1_p = self.player(p1, players)
        p2_p = self.player(p2, players)

        if not p1_p or not p2_p:
            return False

        if p1_p.team == "red" and p2_p.team == "blue":
            self.put(p1_p, "spectator")
            self.put(p2_p, "red")
            self.put(p1_p, "blue")
            return True
        elif p2_p.team == "red" and p1_p.team == "blue":    
            self.put(p1_p, "spectator")
            self.put(p2_p, "blue")
            self.put(p1_p, "red")
            return True
        else:
            return False

    # ====================================================================
    #                       OWNER AND OP COMMANDS
    # ====================================================================
    
    def op(self, name):
        cid = self.client_id(name)

        if cid != None:
            self.send_command("op {}".format(cid))
    
    def deop(self, name):
        cid = self.client_id(name)
            
        if cid != None:
            self.send_command("deop {}".format(cid))
    
    def mute(self, name):
        cid = self.client_id(name)
            
        if cid != None:
            self.send_command("mute {}".format(cid))
    
    def unmute(self, name):
        cid = self.client_id(name)
            
        if cid != None:
            self.send_command("unmute {}".format(cid))
    
    def opsay(self, msg):
        self.send_command('opsay "{0}"'.format(msg))
    
    def abort(self):
        self.send_command('abort')
    
    def allready(self):
        self.send_command('allready')
    
    def timeout(self):
        self.send_command('timeout')
    
    def timein(self):
        self.send_command('timein')
    
    def pause(self):
        self.send_command('pause')
    
    def unpause(self):
        self.send_command('unpause')
        
    def lock(self, team):
        self.send_command('lock {}'.format(team))
    
    def unlock(self, team):
        self.send_command('unlock {}'.format(team))
    
    def stopserver(self):
        self.send_command('stopserver')
    
    def banlist(self):
        self.send_command('banlist')
    
    def put(self, player, team):
        cid = self.client_id(player)
            
        if cid != None:
            self.send_command("put {} {}".format(cid, team))
    
    def kickban(self, player):
        cid = self.client_id(player)
            
        if cid != None:
            self.send_command("kickban {}".format(cid))


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
setattr(minqlbot, "Plugin",  Plugin)

# ====================================================================
#                               HELPERS
# ====================================================================

