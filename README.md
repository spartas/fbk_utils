fbk_utils
=========

fbk_utils, a repository of general-purpose Facebook utilities. I write these 
types of utilites, mostly in Python, to fulfill a particular need, and only 
sparingly do I use them. They can be somewhat useful, and while they are 
horribly un-documented, I am aiming to change a lot of this by publishing it 
publicly.

For this public release, I'm releasing all code under an MIT license, that is,
do whatever you would like to with the code, including using it for commercial 
purposes, but I will not be responsible for damages.

Configuration
-------------

* config.json

	A sample (optional) configuration file, which is used by all scripts. Normally, 
	this can reside in a _.fbk_ directory in one's home directory ( ~/.fbk ). 
	Alternatively, each of the utilities should support a _-f_ runtime parameter 
	to allow specifying the configuration file on the command line, e.g.
		$ ./fbk_fetch_3.py -f /some/absolute/path/config.json

Utils
-----

* fbk_sanitize.py 

	The original sanitization script. While this script is not currently 
	available, the _sanitize script is the original inspiration for this project.

	This script will become available if necessary, or if/when time allows.

* fbk_sanitize_3.py

	I re-wrote _sanitize under Python 3. That is this particular version.

* fbk_fetch_3.py

	Realizing that certain data is no longer available using the data downloader, 
	I re-wrote _sanitize_3 a bit to do Graph API calls instead. The code has more 
	than a few dependencies, which will be fleshed out over the course of this 
	project.


	I'm releasing 1.1, which is a much cleaner version of fbk_fetch_3.py.

Tim Wright
2011–14

