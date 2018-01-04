minqlbot
========

**NOTE: Development has been stalled because of the fact that the next big QL update will give us dedicated servers with a proper official API to administer servers. That means we'll be able to run servers and bots without having to have the overhead of a client. That said, I'm currently working on a new bot for said update, so hopefully I'll have a new bot ready for when the update hits.**

An administration bot for Quake Live, extensible with plugins.

This is the source of the DLL. When you compile this for release, it'll add the base of the Python
files as a resource and load them from there. When compiled for debug, it'll look for them in
`python` folder, relative to `quakelive.exe`.

The plugins for the bot can be found on a separate repository, https://github.com/MinoMino/minqlbot-plugins

Need help with the bot? Drop by [#minqlbot on Quakenet](http://webchat.quakenet.org/?channels=minqlbot) or open an issue here.

Installation
============

NOTE: The following instructions are for the standalone client. If you're using Steam, the QL executable is called "quakelive_steam.exe" and its installation path is not AppData, but wherever you've set Steam to install games. Other than that, it should work just fine with the Steam version as well.

1. You will need [Python 3.4 (x86)](https://www.python.org/ftp/python/3.4.2/python-3.4.2.msi) and [Visual C++ 2013 Redistributable Package (x86)](http://www.microsoft.com/en-us/download/details.aspx?id=40784). Note that regardless of whether you're on a 64-bit or 32-bit OS, you'll need the 32-bit versions of these. Check this box when prompted by Microsoft: ![redist_checkbox]
2. Download ```minqlbot.zip``` and ```minqlbot_dependencies.zip``` from [here](https://github.com/MinoMino/minqlbot/releases/latest) (developers might want to get the [debug build](#contribute)).
3. Find quakelive.exe and extract the contents of ```minqlbot_dependencies.zip``` in the same folder, then make these files __read-only__. Make a folder called "python" in the same folder. It should look more or less like this: ![qlexe_path]
4. Go to the [plugins repository](https://github.com/MinoMino/minqlbot-plugins) and click the "Download ZIP" button on the right. Open the archive and extract the __contents__ of the "minqlbot-plugins-master" folder into the "python" folder we made earlier. I repeat, not the contents of the archive, but the contents of the folder __inside__ the archive.
5. Open config.cfg in a text editor and make sure you set the `Nickname` field to whatever your account name on Quake Live is. You can go ahead and edit some other options as well, but it might be better to wait until you got the bot running correctly first, just in case you mess something up. Some plugins, such as the IRC plugin are deactivated by default. If you want them, you can add them to the plugin list in the config.
6. Now, in order to know if everything's running fine and in order to receive help from me if something goes wrong, get [DebugView](http://technet.microsoft.com/en-us/sysinternals/bb896647.aspx). When you run it, you might get a window titled "DebugView Filter". Fill the "Include" box with "MINQLBOT", like in the following screenshot, then press OK: ![dbgview]
7. Extract the contents of ```minqlbot.zip``` anywhere (if you decide to put these with quakelive.exe too, make sure they're read-only as well).
8. Launch Quake Live, log in, and once you see the Quake Live browser and whatnot, you can go ahead and inject. To do so, launch Minjection, write `minqlbot.dll` under "Module", and write `quakelive.exe` under "Target process name", then click "Inject". Like in the following screenshot:

![minjection]

DebugView should now start showing you lines with stuff prefixed with "MINQLBOT:". If everything goes well, you'll have something like the image below. However, if the injector for some reason fails to inject, you've most likely failed to put the DLLs you downloaded in the correct folder __or__ downloaded an incorrect version of Python or the VC++ redistributable package. You can use [Dependency Walker](http://www.dependencywalker.com/) to figure out what's missing (make sure you get the x86 version here as well).

![dbgview2]


If you had no issues in the previous steps, you're good to go. You can connect to a server, and as long as you have owner or referee status, you're good. Look at the [command list](http://github.com/MinoMino/minqlbot/wiki/Command-List) for further info on how to use the bot. If you want to make your buddies able to control the bot, use !setperm. As of February 8, 2015, the command list has all the commands, but has little to no info on the various commands, but I'll work on that. When you're done, make sure you type `\bot exit` in your console before closing Quake Live to ensure the bot exits safely.


Known Issues
============

I'm happy to announce that I've addressed all the major issues I had with the old minqlbot, and most issues
I have with this one are quite minor:
* `Py_Finalize()` is a pain in the ass and leads to crashes and weird bugs, so I don't use it until you unload the module. I've added a restart command to the console, but it just reloads the script from the hard drive and runs it in
the same namespace after calling the cleanup functions. Can probably improve that further, though.
* Because Python doesn't like to be unloaded, QL might crash if you unload and reinject the module. QL might also keep running in the background without properly shutting down if you quit QL while running the bot. To avoid this, type `\bot exit` in the console before shutting down. This ensures the bot cleans up properly before exiting.
* There's a good chance that after disconnecting from a server, instead of the server recognizing that you've disconnected, you'll end up timing out instead. The same reason will cause `\reconnect` in the console to get stuck in the loading screen. This is likely related to the outgoing message queue system I use on the bot. I'll look into it, but it's such a minor issue that it might take a while until this is fixed.


Additional Notes
================
Some of the events are not implemented yet! This is still in an early stage.

Contribute
==========
If you'd like to contribute with code, you can fork this or the plugin repository and create pull requests for changes. The release page also has debug builds of the bot. The debug version is a lot more verbose and will also look for `minqlbot.py` and `plugin.py` in the `python` folder instead of using the ones built in the DLL. This will allow you to use `\bot restart` to reload these files instead of having to recompile the DLL all the time.

If you found a bug, please open an issue here on Github.

[redist_checkbox]:http://minomino.org/screenshots/2015-01-02_19-45-39.png
[qlexe_path]:http://minomino.org/screenshots/2015-01-02_19-56-57.png
[dbgview]:http://minomino.org/screenshots/2015-01-02_20-17-42.png
[dbgview2]:http://minomino.org/screenshots/2015-01-02_20-38-15.png
[minjection]:http://minomino.org/screenshots/2015-01-02_20-23-35.png
