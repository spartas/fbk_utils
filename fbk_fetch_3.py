#! /usr/bin/env python3

# fbk_sanitize_3.py -- A python script to sanitize wall posts from a facebook export file based on timestamp 
# 	(through a user-provided newline-separated timefile-filter file) or based on the privacy settings attached to 
# 	wall posts. 
#
# 	Created by Timothy Wright <spartas@gmail.com>
# 	Version: 1.0 [June 25th, 2011]
# 		* Stripped out hard-coded string values, to ready for publishing. 
# 		* Pulled out the hard-coded timestamp filter list into a user-specified external file.
# 		* Added (-P) privacy specifiers
# 		
# 	Version: 1.5 [July 3rd, 2011]
# 		* Factored out the logic for specifying privacy options, such that the user can choose which 
# 			privacy-level posts will show in the exported file. The default privacy level operates as before. 
# 			(-P option).
# 		* Support for hiding links to other pages using the -L option. By default, no additional links are hidden.
# 				Usage: "-L profile,friends"
# 		* Support for exporting pages other than the wall. NOTE: Currently the only pages with this support are 
# 			the wall and photos pages. By default, only the wall is exported. The -a options is used as follows:
# 				"-a wall,photos"
# 		* Added support for a config file, -f option, (either in addition to, or as an alternate to the timestamp 
# 			file). The config file is a JSON-structured file containing a single object, with string keys that this 
# 			script uses	for feature support. This script currently only recognizes two keys:
# 				1) "timefilter", another JSON-object that contains string keys and an array of timestamps to filter 
# 						from the wall page. The string keys within this object are ignored, they are useful for the user
# 						to specify groupings for the lists of timestamps.
#
# 				2) "albums", a JSON array containing names of the photo albums to filter from the photos page. Because 
# 					Facebook does not support exporting privacy levels for photo albums, this is the only way to control
# 					which photo albums are exported.
#
# 			See the included "config_filter.json" for example usage. NOTE: for JSON arrays and objects, be sure to 
# 			leave the comma (,) off the last element in the list, otherwise a JSON parsing error will occur.
#
# 		* The script now takes in the path to the "html" directory, and not simply the wall.html file. It will create
# 			a directory of the form html-%Y-%m-%d_%H_%M_%S, a timestamped html directory containing the timestamp when
# 			the script was run. If a file is specified, (i.e. wall.html, within the html directory), the parent 
# 			directory, "html" will be used. No alterations are made to the original "html" directory.
#
# 		* Restructured the script with functions to functional-ize some of the repeated processing. This is an area
# 			that will get improved in the future as well.
#
# 	Version 1.6 [September 5th, 2011]
# 		* Facebook changed the "Everyone" privacy value to "Public". "E" may still be used to specify "[E]veryone", 
# 			but it's been updated to use "Public". "P" has been added to support "[P]ublic as well.
# 		* Facebook appears to be using the hCard microformat in class names, so I've had to update the script to use
# 			these as well.
#
# 	Version 2.0 [September 18th, 2011]
# 		* Major changes to the infile. Now, the infile argument takes the raw facebook zip export file, rather than 
# 			requiring the user to extract it. Backwards compatibility is not provided. In previous versions, this 
# 			script operated on the "wall.html" and "html" infile arguments, in 1.0 and 1.5, respectively. This version
# 			operates on the zip export file itself.
# 			
# 		* Supports reading configuration options from a ".fbk" directory (within the user's home directory. Future 
# 			versions may allow a command-line option for specifying an arbitrary location for this directory. 
# 			Command-line options will supercede any files within this directory. 
# 				* Within this config directory, a "config_filter.json" file will automatically be used if it exists. 
# 				* If a style.css file exists, it will be copied into the output directory (otherwise the one within the
# 					zip file will be used).
#
# 		* Cleaned up the argument lists for non-modified variables within helper processing functions.
#
# 	Version 2.1 [March 24th, 2012]
#		* Facebook made some changes such that posts (not just on your own wall) will appear on the wall in the 
# 			export format. I may add a future configuration option to keep these posts, but I made a minor change to 
# 			intentionally strip them out, as it is confusing to see posts on other people's walls appear on your own.
#
# 		* I fixed a bug with outputting the photo pages; I was erroneously attempting to read from an incorrect 
# 			source location, which produced errors.
#		
#	Version 3.0 [March 4th, 2014]
#		* Has it really been over a year since I last updated? Facebook keeps changing their stylesheets and output
#			formats, which keeps me on my feet. No sooner than I can get a release out, they've gone and changed things
#			up again. Now, they've completely removed the post privacy, which makes the download utterly useless for
#			my purposes with fbk_sanitize.
#		
#		* Rewritten as fbk_sanitize_3 (to be used with Python 3+ and BeautifulSoup 4), along with the newfangled
#			Facebook output zip export files. Many changes are present in this release. Unless you have a privacy key
#			file, the privacy filters will no longer work properly.
#
#		* I've removed the old timelinefilter_format file completely. JSON parsing is the future.
#
#		* NOTE: The zipfile argument for parsing is now _optional_. As a result, the command-line specifier for it has 
#			changed. As of 3.0, it is necessary to specify -i INPUT_ZIPFILE 
#		
#		
#
#
# 		NOTE: BeautifulSoup and argparse may or may not be included with your Python distribution. This program 
# 					relies on both, and will not run without them.

from bs4 import BeautifulSoup, Tag
import zipfile
from zipfile import ZipFile
from datetime import datetime
import sys
import re
import argparse
import os
import json
import shutil
import urllib
import urllib.request
import time
from collections import OrderedDict


def extract_tab_links( bs, pages, suppressed_links ):
	tab_nav = bs.find(class_='nav').find('ul')
# 		* Factored out the logic for specifying privacy options, such that the user can choose which 
# 			privacy-level posts will show in the exported file. The default privacy operates as before. 
	for tab_link in tab_nav.findAll('a'):

		tab_name = tab_link['href'].split('.')[0]

		if( suppressed_links is not None and tab_name in suppressed_links ):
			tab_link.extract()
		elif( tab_name not in pages ):
			del(tab_link['href'])

def write_outfile( contents, outfilepath, filename ):
	outfile = open(os.path.join(outfilepath, filename), 'a')
	outfile.write( contents )
	outfile.close()


def zipfile_copy( zipfile, src_path, dest_path ):
	file_src = zipfile.open( src_path )
	file_target = file(dest_path, 'wb')

	shutil.copyfileobj( file_src, file_target )

	file_src.close()
	file_target.close()

def zip_process_wall( zip_infile, outfilepath, time_filter ):
	return 

def process_wall( zip_infile, outfilepath, time_filter ):
	# For this to work properly, the local version of images must be installed in ../images/icons/
	# If this becomes unweildy, it may be necessary to put this into a separate file as well
	icon_map = {
		'http://photos-c.ak.fbcdn.net/photos-ak-snc1/v43/97/32061240133/app_2_32061240133_2659.gif' : 'youtube.gif',
	}

	f = zip_infile.open('%s/wall.htm' % (basedirname), 'r')
	soup = BeautifulSoup( f.read() )
	f.close()

	node_profile_name = soup.find(class_='contents').find('h1')
	profile_name = node_profile_name.string

	# If we are adding a tagline, then add the tagline
#if obj_config['tagline'] != "":
#		node_tagline = node_profile_name.append( Tag(soup, "span", [('id', 'tagline')]) )
#		node_profile_name.find('span', id=tagline).append( obj_config['tagline'] )


	# Do work

	# If "[config_dir]/images/icons" exists, assume that the user has or will download the necessary icon files from 
	#	facebook, otherwise, just leave the facebook.com links in
	if ( use_configdir and os.path.exists(os.path.join(config_dir,'images', 'icons')) ):

		icon_src_regex = re.compile('^http://www.facebook.com/images/icons/')

		# Root facebook.com icon image sources to the local filesystem (stop giving facebook.com traffic to analyze)
		for icon_image in soup.findAll('img', attrs={'class': attr_classname_map['wall']['icon']}, src=icon_src_regex):
			icon_image['src'] = re.sub(r'http://www.facebook.com/', '../', icon_image['src']); 
			

		# A future version will check that the corresponding files exist, and will download them if not
		for logo_img in icon_map:
			for icon_image in soup.findAll('img', attrs={'class': attr_classname_map['wall']['icon']}, src=logo_img):
				icon_image['src'] = re.sub(re.compile(logo_img), '../images/icons/' + icon_map[logo_img], icon_image['src'])


	## Remove links to other pages on the left-hand sidebar ##

	# Remove the profile photo link
	profile_image_link = soup.find(class_='nav').find('img').findParent('a')

	# Newer versions of the download do not contain a linked profile picture
	if profile_image_link != None:
		del(profile_image_link['href'])

	# Remove the tab links
	extract_tab_links(soup, args.pages, args.suppress_links)


	# Extract all 'class="profile"' tags
	class_profile = soup.findAll(attrs={'class': attr_classname_map['wall']['profile']})

	# Remove all posts by anyone who is not the profile author
	for spantag in class_profile:
		if spantag.string != profile_name and None == spantag.findParent(attrs={'class' : attr_classname_map['wall']['comments']}):
			spantag.findParent(attrs={'class':attr_classname_map['wall']['feedentry']}).extract()

	# Remove all comments
	comments = soup.findAll(attrs={'class': attr_classname_map['wall']['comments']})
	[comment.extract() for comment in comments]


	# Remove the explicit time entries, as specified above
	for timestr in time_filter:
		time_entry = soup.find(attrs={'class': attr_classname_map['wall']['timerow']}, text=timestr)
		if( None == time_entry ):
			print(("No entry found for time: %s" % (timestr)))
		else:
			time_entry.findParent(attrs={'class': attr_classname_map['wall']['feedentry']}).extract()


	# Remove "walllink" class posts (TEMPORARY, until a better solution can be found without exposing private data)
	wall_links = soup.findAll(attrs={'class': attr_classname_map['wall']['walllink']})
	[wall_link.findParent(attrs={'class': attr_classname_map['wall']['feedentry']}).extract() for wall_link in wall_links]


	### REMOVE PRIVATE POSTS ###

	privacy_opt_regex_map = {
		'x' 	: '(E|e)xcept:? ',
		'F' 	: 'Friends( Only)?$',
		'M' 	: 'Only Me',
		'o' 	: 'Friends of Friends',
		'E' 	: 'Public',
		'P' 	: 'Public',
	}

	privacy_exceptions = []
	for privacy_specifier, regex in privacy_opt_regex_map.iteritems():
		if privacy_specifier in args.privacy:

			img_privacy = soup.findAll('img', attrs={'class': attr_classname_map['wall']['privacy']}, title=re.compile(regex))
			privacy_exceptions.extend( img_privacy )


	[privacy_exception.findParent(attrs={'class': attr_classname_map['wall']['feedentry']}).extract() for privacy_exception in privacy_exceptions]


	# Remove all posts without a privacy specifier (because these are more than likely posts on others' walls)
	timerows = soup.findAll('div', attrs={'class': attr_classname_map['wall']['timerow']})

	for row in timerows:
		img_privacy = row.find('img', attrs={'class': attr_classname_map['wall']['privacy']})

		# If there is no privacy specifier, delete the post
		if img_privacy == None:
			row.findParent('div').extract()
		else: # Remove the privacy icon
			img_privacy.extract()


	# Strip out the download notice
	soup.find(attrs={'class': attr_classname_map['wall']['downloadnotice']}).contents = ""

	# Write out the filtered wall page
	write_outfile(soup.prettify(), outfilepath, 'wall.html')


def process_photos( zip_infile, outfilepath, album_filter ):

	f = zip_infile.open('%s/photos.htm' % (basedirname), 'r')
	soup = BeautifulSoup( f.read() )
	f.close()


	## Remove links to other pages on the left-hand sidebar ##

	# Remove the profile photo link (We'll get better at handling this properly in the future based on
	# the absence/presence of the photos and the privacy of "Profile Pictures album)
	profile_image_link = soup.find(id='lhs').find('img').findParent('a')

	# Newer versions of the download do not contain a linked profile picture
	if profile_image_link != None:
		del(profile_image_link['href'])

	# Remove the tab links
	extract_tab_links(soup, args.pages, args.suppress_links)

	# ADDITION: 2011-09-05
	# This is necessary because BS can choke on photo album comments. So we'll remove them individually first and
	# then do the default action of removing the whole comment block as before.
	comments = soup.findAll(attrs={'class': 'comment hentry'})
	[comment.extract() for comment in comments]
	# END ADDITION

	# Remove all comments
	comments = soup.findAll(attrs={'class': attr_classname_map['photos']['comments']})
	[comment.extract() for comment in comments]


 	# Remove explicit albums, as specified in album_filter
	for albumstr in album_filter:
		node_album = soup.find('a', text=albumstr)

		# Protect against unlisted or hidden albums specified in the config file
		if node_album != None:
			node_album.findParent('div', attrs={'class': attr_classname_map['photos']['album']}).extract()
		else:
			print(("Album \"%s\" does not exist within the photos page." % (albumstr)))

	# Go over the remaining album pages and handle them as well
	for album_struct in soup.findAll('div', attrs={'class': attr_classname_map['photos']['album']}):
		album_filename = urllib.url2pathname(album_struct.find('a')['href'])
		
		f = zip_infile.open(os.path.join('%s/' % (basedirname), album_filename), 'r')
		album_soup = BeautifulSoup( f.read() )
		f.close()

		process_album( album_soup, outfilepath, album_filename )

	# Strip out the download notice
	soup.find(attrs={'class': attr_classname_map['photos']['downloadnotice']}).contents = ""

	# Write out the filtered photos page
	write_outfile(soup.prettify(), outfilepath, 'photos.htm')


def process_album( soup, outfilepath, album_filename ):
	# Remove the tab links from album pages
	extract_tab_links(soup, args.pages, args.suppress_links)

	# Remove the profile photo link
	profile_image_link = soup.find(id='nav').find('img').findParent('a')

	# Newer versions of the download do not contain a linked profile picture
	if profile_image_link != None:
		del(profile_image_link['href'])

	# Remove facebook.com links from the photo album timestamps
	album_fbk_regex = re.compile('^http://www.facebook.com/photo.php')
	for fbk_link in soup.findAll('a', href=album_fbk_regex):
		del(fbk_link['href'])

	# Remove all comments from album pages
	comments = soup.findAll(attrs={'class': attr_classname_map['photos']['comments']})
	[comment.extract() for comment in comments]

	if args.strip_GPS == True:
		photo_metadata = soup.findAll('div', attrs={'class': attr_classname_map['album']['photo_container']})
		for photo in photo_metadata:
			if len(photo.contents) >= 6:

				photo_str = photo.contents[5].prettify()
				photo_str = re.sub(r'^Latitude:[^\n]*[\n]<br />[\n]','', photo_str, 0, re.M)
				photo_str = re.sub(r'^Longitude:[^\n]*[\n]<br />[\n]','', photo_str, 0, re.M)
				photo.contents[5].replaceWith( photo_str )

	# Strip out the download notice
	soup.find(attrs={'class': attr_classname_map['photos']['downloadnotice']}).contents = ""

	write_outfile( soup.prettify(), outfilepath, album_filename )

def fbk_cache( ):
	import sqlite3

	#if ( use_configdir and os.path.exists(os.path.join(config_dir,'fbk_cache.db')) ):
	cxn = sqlite3.connect( os.path.join(config_dir, 'fbk_cache.db') )
	cur = cxn.cursor()

	sql_txn_create = """CREATE TABLE IF NOT EXISTS txn 
	(
		`id` INTEGER PRIMARY KEY AUTOINCREMENT,
		`datetime_requested` INTEGER,
		`return_code` INTEGER	
	)
	"""
	cur.execute( sql_txn_create )

	sql_posts_create = """CREATE TABLE IF NOT EXISTS posts 
	(
		`id` INTEGER PRIMARY KEY AUTOINCREMENT,
		`fbk_id` TEXT,
		`message` TEXT,
		`privacy_description` TEXT,
		`created_timestamp` TEXT,
		`type` TEXT
	)
	"""
	cur.execute( sql_posts_create )


	if obj_config['graph']['update_freq']:

		sql_cache_query = "SELECT `datetime_requested` FROM `txn` WHERE `return_code`=200 ORDER BY `id` DESC LIMIT 1"
		cur.execute(sql_cache_query)

		last_cache_time = cur.fetchone()

		if last_cache_time:
			last_cache_time = last_cache_time[0]
			if time.time() - last_cache_time < obj_config['graph']['update_freq']:
				print( "Using cache data instead.")
				sys.exit(12)


	# Set up fbk_cache_id
	cur.execute("SELECT fbk_id FROM posts")
	fbk_cache_id = [x for l in cur.fetchall() for x in l]


	graph_status_url = "https://graph.facebook.com/me/posts?access_token=%s&type=status&fields=id,message,privacy,type" % (obj_config['graph']['access_token'])

	with urllib.request.urlopen(graph_status_url) as r:

		cur.execute( "INSERT INTO txn (`datetime_requested`, `return_code`) VALUES (?, ?)", (time.time(), r.status) )
		cxn.commit()

		response = json.loads(r.read().decode('utf-8'))

	
	status_kv_schema = { 'fbk_id' : 'id', 'created_timestamp' : 'created_time' }
	status_kv_dict = { k : k for k in ('type', 'message') }
	
	status_kv_dict = (OrderedDict((list(status_kv_dict.items()) + list(status_kv_schema.items()))))

	posts = []
	for status in response['data']:

		if "message" not in status:
			continue

		# Don't add to the DB multiple times
		if status['id'] in fbk_cache_id:
			print("Skipped " + status['id'])
			continue

		post = OrderedDict( {k : status[v] for k,v in status_kv_dict.items()} )
		post['privacy_description'] = status['privacy']['description']

		posts.append(post)

	status_insert = []
	for p in posts:
		status_insert.append( ("(" + ",".join(["%s" % (v) for v in p.values()]) + ")") )

	# SQL
	sql_status_insert = """INSERT INTO posts 
	(%s) 
	VALUES 
	(:fbk_id, :created_timestamp, :type, :message, :privacy_description)
	;""" % (",".join( ('fbk_id', 'created_timestamp', 'type', 'message', 'privacy_description') ))
	# END SQL

	cur.executemany( sql_status_insert, posts )
	cxn.commit()


	cur.execute("select * from posts")

	cxn.close()

def process_profile( zip_infile, outfilepath ):

	f = zip_infile.open('%s/profile.htm' % (basedirname), 'r')
	soup = BeautifulSoup( f.read() )
	f.close()

	## Remove links to other pages on the left-hand sidebar ##

	# Remove the profile photo link (We'll get better at handling this properly in the future based on
	# the absence/presence of the photos and the privacy of "Profile Pictures album)
	profile_image_link = soup.find(class_='nav').find('img').findParent('a')

	# Newer versions of the download do not contain a linked profile picture
	if profile_image_link != None:
		del(profile_image_link['href'])

	# Remove the tab links
	extract_tab_links(soup, args.pages, args.suppress_links)

	
	# Pull out the "Family", "Groups", and "Other" blocks
	# 
	# in the future, this will be customizable via the configuration
	profile_table = soup.find('table', attrs={'class': attr_classname_map['profile']['profiletable']})
		
	for rem_group in ['Family', 'Groups', 'Other']:
		profile_table.find('td', attrs={'class': attr_classname_map['profile']['profile_label']}, text=rem_group + ":").findParent('tr').extract()

	# Strip out the download notice
	soup.find(attrs={'class': attr_classname_map['photos']['downloadnotice']}).contents = ""

	# Write out the filtered photos page
	write_outfile(soup.prettify(), outfilepath, 'profile.htm')

def mktreeoutput( basedirname ):
	file_path = '.'
	# Create the base filename (if it doesn't exist)
	if( not os.path.exists(os.path.join(os.path.dirname(file_path), basedirname)) ):
		if( not os.path.exists(os.path.join(os.path.dirname(file_path), basedirname)) ):
			os.mkdir( os.path.join(os.path.dirname(file_path), basedirname) )
		
	# Set up the date-stampped html directory
	str_outfile_dt = datetime.now().strftime('%Y-%m-%d_%H_%M_%S')
	outfile_path = os.path.join(os.path.dirname(file_path), basedirname, "html-" + str_outfile_dt)
	os.mkdir( outfile_path )

	return outfile_path

def process_graph():

	if( 'basedirname' in obj_config['graph'] ):
		basedirname = obj_config['graph']['basedirname']
	else:
		basedirname = "_fbk"

	outfile_path = mktreeoutput( basedirname )

	fbk_cache()
	



def process_zip_infile():

	# Open the zip file for reading, and figure out the base filename
	file_path = os.path.abspath(args.infile)
	zip_infile = zipfile.ZipFile( file_path, 'r' )
#print(zip_infile.namelist()[0])
#	sys.exit(15)

	

	basedirname = zip_infile.namelist()[0].split('/')[0]
	outfile_path = mktreeoutput( basedirname )

	# Copy 'style.css' to the target directory
	if( use_configdir and os.path.isfile(os.path.join(config_dir, 'style.css')) ):
		shutil.copy( os.path.join(config_dir, 'style.css'), outfile_path)
	else:
		zipfile_copy( zip_infile, '%s/style.css' % (basedirname), os.path.join(outfile_path, 'style.css') )


	if "wall" in pages:
		process_wall( zip_infile, outfile_path, obj_config['timefilter'] )
	if "photos" in pages:
		process_photos( zip_infile, outfile_path, obj_config['albums'] )
	if "profile" in pages:
		process_profile( zip_infile, outfile_path )

	zip_infile.close()

	return

# Main()
if __name__ == "__main__":

	# Set up the classname map
	attr_classname_map = {
		'profile' : {
			'profiletable' 		: 'profiletable',
			'profile_label'		: 'profile_label',
		},
		'wall' : {
			'album' 					: 'album',
			'comments' 				: 'comments hfeed',
			'downloadnotice' 	: 'downloadnotice',
			'feedentry' 			: 'feedentry hentry',
			'icon' 						: 'icon',
			'privacy' 				: 'privacy',
			'profile' 				: 'profile fn',
			'timerow' 				: 'timerow',
			'walllink' 				: 'walllink',
		},
		'photos' : {
			'album' 					: 'album',
			'comments' 				: 'comment hentry',
			'downloadnotice' 	: 'downloadnotice',
		},
		'album' : {
			'photo_container'	: re.compile('photo-container'),
		},
	}

	# Process arguments
	parser = argparse.ArgumentParser(description='Sanitize pages from a Facebook export file.')

	parser.add_argument('-a', '--pages', default="wall", 
			help='A comma-separated list of pages to process. Valid specifiers are profile,wall,photos,friends,notes,events,messages. The default is to only process the wall. Example usage: wall,photos')

	parser.add_argument('-L', '--suppress-links',
			help='A comma-separated list of page links remove from the left bar. Valid specifiers are profile,wall,photos,friends,notes,events,messages. The default is to hide nothing. Example usage: profile,friends,messages.')

	parser.add_argument('-G', '--strip-GPS', action='store_true',
			help='If specified, GPS data is stripped from the metadata table in album pages')

	parser.add_argument('-P', '--privacy', default="xMF", 
			help='Specify the post privacy to filter out. Valid specifiers are E[x]cept: (Privacy Group), Only [M]e, [F]riends Only, Friends [o]f Friends, and [E]veryone. The default is xMF.')

	parser.add_argument('-f', '--config-file', metavar='CONFIG_FILE', 
			help='A JSON-structured file containing photo album names and an array of time strings to filter from the output')

	parser.add_argument('--version', action='version', version='%(prog)s 3.0')

	parser.add_argument('-i', '--infile', metavar='ZIP_INFILE', help='The export zip file to process.')

	args = parser.parse_args()

	config_dir = os.path.join( os.path.expanduser('~'), '.fbk' )
	use_configdir = os.path.exists( config_dir )

	valid_pages = ['profile', 'wall', 'photos', 'friends', 'notes', 'events', 'messages']
	pages = args.pages.split(',')

	# Default obj_config
	default_obj_config = obj_config = {
		"timefilter"	: {},
		"albums" 		: [],
		"tagline"		: "",
		"graph"			: {},
	}

	
	file_configfile_filter = None
	if(args.config_file):
		file_configfile_filter = os.path.abspath(args.filter_configfile)
	elif( use_configdir and os.path.exists(os.path.join(config_dir, 'config_filter.json'))):
		file_configfile_filter = os.path.join(config_dir, 'config_filter.json')

	if(file_configfile_filter):

		if( not os.path.isfile(file_configfile_filter)):
			print("The specified config filter file, %s, does not exist." % (args.filter_configfile))
			sys.exit(1)

		configfile = open(file_configfile_filter, 'r')
		obj_config = json.load(open(file_configfile_filter, 'r'))
		configfile.close()

		# Re-generate the keys for un-specified values in the JSON config file
		for conf_key in default_obj_config:
			if conf_key not in obj_config:
				obj_config[conf_key] = default_obj_config[conf_key]

		temp_timefilter = []
		for k in obj_config['timefilter']:
			temp_timefilter.extend(obj_config['timefilter'][k])

		obj_config['timefilter'] = temp_timefilter		

	for page in pages:
		if page not in valid_pages:
			print("Invalid page specified: %s" % (page))
			sys.exit(1)

	if args.infile:
		process_zip_infile()

	if not obj_config['graph']:
		if args.infile:
			infile = os.path.abspath(args.infile)
		if( not args.infile or not os.path.exists(infile) ):
			print("The input file specified, %s, does not exist (and/or no graph API specified)." % (args.infile))
			sys.exit(1)
	else:
		process_graph()

#	if( not zipfile.is_zipfile(infile) ):
#		print("The input file specified, %s, is not a valid zip file." % (args.infile))
#		sys.exit(1)


	sys.exit(0)
