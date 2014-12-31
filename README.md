minqlbot
========

An administration bot for Quake Live, extensible with plugins.

This is the source of the DLL. When you compile this for release, it'll add the base of the Python
files as a resource and load them from there. When compiled for debug, it'll look for them in
"python" folder, relative to quakelive.exe.

The plugins for the bot can be found on a separate repository, https://github.com/MinoMino/minqlbot-plugins

Release binary download: http://minomino.org/quake/minqlbot_bin.zip


Installation
============

COMING SOON


Known Issues
============

I'm happy to announce that I've addressed all the major issues I had with the old minqlbot, and most issues
I have with this one are quite minor:
* Py_Finalize() is a pain in the ass and leads to crashes and weird bugs, so I don't use it until you unload the module.
I've added a restart command to the console, but it just reloads the script from the hard drive and runs it in
the same namespace after calling the cleanup functions. Can probably improve that further, though.


Additional Notes
================
Some of the events are not implemented yet! This is still in an early stage.
