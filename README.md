fbk_utils
=========

fbk_utils, a repository of general-purpose Facebook utilities. I write these 
types of utilites, mostly in Python, to fulfill a particular need, and only 
sparingly do I use them. They can be somewhat useful, and while they are 
horribly un-documented, I am aiming to change a lot of this by publishing it 
publicly.

For this public release, I'm releasing all code under an MIT license, that isl
do whatever you would like to with the code, including using it for commercial 
purposes, but I will not be responsible for damages.

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

Tim Wright
2011–14

