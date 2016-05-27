#! /usr/bin/env python3.4

# fbk_fetch_3.py -- Uses the Facebook Graph API to grab and store posts locally. 
#
# 	Created by Timothy Wright <spartas@gmail.com>
#		Version 1.0 [March 4th, 2014]
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
# 		Version 1.1 [March 20th, 2014]
#	 	* The previous version was heavily influenced by fbk_sanitize_3.py, with only minor adjustments to make it 
# 			play nice with graph. This is a cleanup release. I've dropped all of the version history (which referred to
# 			fbk_sanitize{,_3}.py instead.
# 	
#	 	* Despite what v1.0 implies, this really is fbk_fetch_3.py, and not fbk_sanitize.py.
#
#	 	* As a result of cleaning up teh old _sanitize code, I've also removed a lot of unused dependencies. Also, a
# 			work in progress.
#	
#		Version 1.2 [March 26th, 2014]
#		* Bump the limit for Graph API responses to 200 to receive much more data in fewer steps. This parameter is
#			expected to be configurable in the future.
#
#		* Issue requests for paginated requests to support getting a larger set of un-seen requests. This is currently
#			hard-coded, but will be configurable in a future version.
#		
#		Version 1.3 [April 1st, 2014]
#		* Added a --verbosity/-v option and a debug_print method, which respects verbosity levels.
#
#		* Clarified some of the textual output.
#
# 		NOTE: argparse may or may not be included with your Python distribution. This program 
# 					relies on both, and will not run without them.

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
from fbk_config import fbk_config
import sqlite3

def debug_print(msg, verbose_threshold):
	if args.verbosity:
		if args.verbosity >= verbose_threshold:
			print(msg)

def fbk_fetch_prior( ):

	cxn = sqlite3.connect( os.path.join(config_dir, 'fbk_cache.db') )
	cur = cxn.cursor()

	sql_fetch_query = """SELECT `created_timestamp` FROM `posts`
	ORDER BY `created_timestamp` ASC LIMIT 1"""
	cur.execute(sql_fetch_query)

	str_earliest_ts = cur.fetchone()[0]
	earliest_ts = int(datetime.strptime(str_earliest_ts, "%Y-%m-%dT%H:%M:%S%z").strftime('%s'))
	print(str_earliest_ts)
	fbk_fetch_insert(until=earliest_ts, limit=200)
	cxn.close()

	sys.exit(32)

	return

def fbk_insert_response( res, fbk_cache_id=[] ):
	cxn = sqlite3.connect( os.path.join(config_dir, 'fbk_cache.db') )
	cur = cxn.cursor()

	status_kv_schema = { 'fbk_id' : 'id', 'created_timestamp' : 'created_time' }
	status_kv_dict = { k : k for k in ('type', 'message') }
	
	status_kv_dict = (OrderedDict((list(status_kv_dict.items()) + list(status_kv_schema.items()))))

	posts = []
	skipped = 0
	invalid = 0
	for status in res['data']:

		if "message" not in status:
			invalid += 1
			continue

		if "privacy" not in status:
			invalid += 1
			continue

		if "description" not in status['privacy']:
			invalid += 1
			continue

		#process_post_likes(cxn, status['id'], status['likes'])

		# Don't add to the DB multiple times
		if status['id'] in fbk_cache_id:
			skipped += 1
			continue

		post = OrderedDict( {k : status[v] for k,v in status_kv_dict.items()} )
		post['privacy_description'] = status['privacy']['description']

		posts.append(post)

	debug_print("Skipped, %s posts; invalid" % (invalid), 2)
	debug_print("Skipped, %s posts; previously added" % (skipped), 3)

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

	cxn.close()
	return (invalid,skipped,len(posts))

def fbk_fetch_url(url):
	cxn = sqlite3.connect( os.path.join(config_dir, 'fbk_cache.db') )
	cur = cxn.cursor()

	debug_print("Fetch URL: %s" % (url), 4)

	with urllib.request.urlopen(url) as r:

		cur.execute( "INSERT INTO txn (`datetime_requested`, `return_code`) VALUES (?, ?)", (time.time(), r.status) )
		cxn.commit()

		response = json.loads(r.read().decode('utf-8'))
	
	debug_print("Loaded %s responses" % (len(response['data'])), 3)
	cxn.close()

	return response

def fbk_fetch_insert( endpoint="posts", type_="status", fields=['id','message','privacy','type','likes'], since=None, until=None, limit=None, **kwargs):

	cxn = sqlite3.connect( os.path.join(config_dir, 'fbk_cache.db') )
	cur = cxn.cursor()

	# Set up fbk_cache_id
	cur.execute("SELECT fbk_id FROM posts")
	fbk_cache_id = [x for l in cur.fetchall() for x in l]

	url_params = (endpoint, obj_config['graph']['access_token'], type_, ",".join(fields))
	url = "https://graph.facebook.com/me/%s?access_token=%s&type=%s&fields=%s" % url_params

	if(since):
		url += "&since=%s" % (since)
	if(limit):
		url += "&limit=%s" % (limit)
	if(until):
		url += "&until=%s" % (until)

	fbk_insert_response( fbk_fetch_url(url), fbk_cache_id)

	cxn.close()

	return

def fbk_cache( ):
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

	last_cache_time = None
	if args.ignore_last_cache_time == False: 
		if obj_config['graph']['update_freq']:
			if obj_config['graph']['update_freq'] > 0:

				sql_cache_query = "SELECT `datetime_requested` FROM `txn` WHERE `return_code`=200 ORDER BY `id` DESC LIMIT 1"
				cur.execute(sql_cache_query)

				last_cache_time = cur.fetchone()

				if last_cache_time:
					last_cache_time = last_cache_time[0]
					if not force_update and time.time() - last_cache_time < obj_config['graph']['update_freq']:
						print( "Fetch request aborted. Use cache data. You may override with -R")
						sys.exit(12)


	# Set up fbk_cache_id
	cur.execute("SELECT fbk_id FROM posts")
	fbk_cache_id = [x for l in cur.fetchall() for x in l]


	graph_status_url = "https://graph.facebook.com/me/posts?access_token=%s&type=status&fields=id,message,privacy,type,likes" % (obj_config['graph']['access_token'])

	if last_cache_time is not None:
		graph_status_url += "&since=%s" % ( int(last_cache_time) )
	#else:
	#	graph_status_url += "&limit=200"

	debug_print("Fetch URL: %s" % (graph_status_url), 4)


	# 
	iteration = 0
	fetch_loop_max = 1 # At some point in the future, this will represent a complete fetch loop
	while iteration < fetch_loop_max and graph_status_url:

		response = fbk_fetch_url(graph_status_url)

		(num_invalid,num_skipped,num_inserted) = fbk_insert_response( response, fbk_cache_id)

		if not force_update:
			graph_status_url = response['paging']['next']
		else:
			graph_status_url = None

		iteration = iteration + 1

		if num_inserted > 0:
			print("Inserted %s updated posts" % num_inserted)
		else:
			print("No additional posts were fetched.")

	cxn.close()

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

def process_post_likes(cxn, id, likes):
	print("Process likes.")
	return

def process_graph():

	if( 'basedirname' in obj_config['graph'] ):
		basedirname = obj_config['graph']['basedirname']
	else:
		basedirname = "_fbk"

	fbk_cache()
	
# Main()
if __name__ == "__main__":

	# Process arguments
	parser = argparse.ArgumentParser(description='Fetch content from Facebook\'s Graph API')

	parser.add_argument('-A', '--access-token', 
			help='The access token to use for making Facebook Graph API requests.')

	parser.add_argument('-C', '--client-id', type=int,
			help='The Facebook application\'s client ID to use for making Facebook Graph API requests.')

	parser.add_argument('-R', '--force', action="store_true",
			help='Force a re-update of the local data, despite the cache timeout.')

	parser.add_argument('-T', '--ignore-last-cache-time', action="store_true",
			help='Ignore the local cache timeout.')

	parser.add_argument('-f', '--config-file', metavar='CONFIG_FILE', 
			help='A JSON-structured file containing configuration directives to use for the script')

	parser.add_argument('-v', '--verbosity', action="count",
			help="Increase output verbosity")

	parser.add_argument('--version', action='version', version='%(prog)s 1.3')

	args = parser.parse_args()


	config_dir = ".fbk"
	use_configdir = os.path.exists( config_dir )
	
	if use_configdir == False:
		config_dir = os.path.join( os.path.expanduser('~'), '.fbk' )
		use_configdir = os.path.exists( config_dir )

	# Default obj_config
	
	file_configfile = None
	if(args.config_file):
		file_configfile = os.path.abspath(args.config_file)
	elif( use_configdir and os.path.exists(os.path.join(config_dir, 'config.json'))):
		file_configfile = os.path.join(config_dir, 'config.json')

	if(file_configfile):
		obj_config = fbk_config.parse_config( file_configfile, True )

	if(args.access_token):
		obj_config['graph']['access_token'] = args.access_token

	if(args.client_id):
		obj_config['graph']['client_id'] = args.client_id

	if(args.force):
		force_update = True
	else:
		force_update = False
		#obj_config['graph']['update_freq'] = 0

	process_graph()

	sys.exit(0)
