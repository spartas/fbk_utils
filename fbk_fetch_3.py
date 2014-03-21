#! /usr/bin/env python3

# fbk_fetch.py -- Uses the Facebook Graph API to grab and store posts locally. 
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
# 	Version 1.1 [March 20, 2014]
# 	* The previous version was heavily influenced by fbk_sanitize_3.py, with only minor adjustments to make it 
# 		play nice with graph. This is a cleanup release. I've dropped all of the version history (which referred to
# 		fbk_sanitize{,_3}.py instead.
# 	
# 	* Despite what v1.0 implies, this really is fbk_fetch_3.py, and not fbk_sanitize.py.
#
# 	* As a result of cleaning up teh old _sanitize code, I've also removed a lot of unused dependencies. Also, a
# 		work in progress.
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
		if obj_config['graph']['update_freq'] > 0:

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

	parser.add_argument('-f', '--config-file', metavar='CONFIG_FILE', 
			help='A JSON-structured file containing configuration directives to use for the script')

	parser.add_argument('--version', action='version', version='%(prog)s 1.1')

	args = parser.parse_args()


	config_dir = os.path.join( os.path.expanduser('~'), '.fbk' )
	use_configdir = os.path.exists( config_dir )

	# Default obj_config
	
	file_configfile = None
	if(args.config_file):
		file_configfile = os.path.abspath(args.config_file)
	elif( use_configdir and os.path.exists(os.path.join(config_dir, 'config.json'))):
		file_configfile = os.path.join(config_dir, 'config.json')

	if(file_configfile):
		obj_config = fbk_config.parse_config( file_configfile )

	if(args.access_token):
		obj_config['graph']['access_token'] = args.access_token

	if(args.client_id):
		obj_config['graph']['client_id'] = args.client_id

	if(args.force):
		obj_config['graph']['update_freq'] = 0

	process_graph()

	sys.exit(0)
