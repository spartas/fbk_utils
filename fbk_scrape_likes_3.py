#! /usr/bin/env python3

# fbk_scrape_likes_3.py -- Uses the Facebook Graph API to grab and store posts' likes locally.
#
# 	Created by Timothy Wright <spartas@gmail.com>
#		Version 1.0 [April 23rd, 2016]
#		*  Initial version

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

	likes = []
	person = []
	uniq_person_id = []
	skipped = 0
	invalid = 0
	for status in res['data']:

		like = {}

		post_fbk_id = status['id']

		sql_fbk_id = "SELECT `id` FROM `posts` WHERE `fbk_id`='" + post_fbk_id + "'"
		cur.execute(sql_fbk_id)
		post_id = cur.fetchone()

		if post_id == None:
			continue

		post_id = int(post_id[0])

		if not 'likes' in status:
			continue

		#fbk_cache_id = [x for l in cur.fetchall() for x in l]
		for status_liker in status['likes']['data']:
			person_id = int(status_liker['id'])
			like = {
				'person_id' : person_id,
				'posts_id' 	: post_id
			}
			likes.append(like)

			if person_id not in uniq_person_id:
				liker = {
					'person_id'	: person_id,
					'name'		: status_liker['name']
				}

				person.append(liker)
				uniq_person_id.append(person_id)

	# SQL
	sql_like_insert = """INSERT OR IGNORE INTO posts_likes
	(%s)
	VALUES
	(:person_id, :posts_id)
	;""" % (",".join( ('person_id', 'posts_id') ))
	# END SQL

	cur.executemany( sql_like_insert, likes )
	cxn.commit()

	# SQL
	sql_person_insert = """INSERT OR IGNORE INTO person
	(%s)
	VALUES
	(:person_id, :name)
	;""" % (",".join( ('id', 'name') ))
	# END SQL

	cur.executemany( sql_person_insert, person )
	cxn.commit()

	cxn.close()

	return

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

def fbk_fetch_insert( endpoint="posts", type_="status", fields=['id','likes'], since=None, until=None, limit=None, **kwargs):

	cxn = sqlite3.connect( os.path.join(config_dir, 'fbk_cache.db') )
	cur = cxn.cursor()

	# Set up fbk_cache_id
	#cur.execute("SELECT id, fbk_id FROM posts")
	#fbk_cache_id = [x for l in cur.fetchall() for x in l]

	url_params = (endpoint, obj_config['graph']['access_token'], type_, ",".join(fields))
	url = "https://graph.facebook.com/me/%s?access_token=%s&type=%s&fields=%s" % url_params

	if(since):
		url += "&since=%s" % (since)
	if(limit):
		url += "&limit=%s" % (limit)
	if(until):
		url += "&until=%s" % (until)

	fbk_insert_response( fbk_fetch_url(url))

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

	sql_postslikes_create = """CREATE TABLE IF NOT EXISTS posts_likes
	(
		`person_id` INTEGER,
		`posts_id` INTEGER,
		PRIMARY KEY (`person_id`,`posts_id`)
	)
	"""
	cur.execute( sql_postslikes_create )

	sql_person_create = """CREATE TABLE IF NOT EXISTS person
	(
		`id` INTEGER PRIMARY KEY,
		`name` TEXT
	)
	"""
	cur.execute( sql_person_create )

	# Set up fbk_cache_id
	cur.execute("SELECT fbk_id FROM posts")
	fbk_cache_id = [x for l in cur.fetchall() for x in l]


	graph_status_url = "https://graph.facebook.com/me/posts?access_token=%s&type=status&fields=id,likes" % (obj_config['graph']['access_token'])
	#graph_status_url += "&__paging_token=enc_AdBNF7zntHiM7nLEpUOkHOfPlydiAVYn5A5JHN6RhH6N10kubwEr5RxgbV2NnyttA8i4dYey1b2GX9joP9xzPlbq&access_token=CAAAAAIz3DV0BAEdDmcawhSClCnDKeIo4SdXwU92xbgPNcZCOeOZBVBiYpPa440Crekk5ZCDJ90wZBdT1ZAY0HvMoGLuNBuhwPViZAHr8NVkg34qAGkPhkIfpVgdR8IOJmCdPxdLZAbdVZBIhqV4AZClR01VeoZCkv4of35KqQGaQXCWVUdJiVblSvzSMyAdhQRpHb78YT7kzZC22QZDZD&until=1226285728"
	#graph_status_url += "&limit=200"

	debug_print("Fetch URL: %s" % (graph_status_url), 4)


	#
	iteration = 0
	fetch_loop_max = 1 # At some point in the future, this will represent a complete fetch loop
	while iteration < fetch_loop_max and graph_status_url:

		response = fbk_fetch_url(graph_status_url)

		debug_print(response['paging']['next'], 2)

		fbk_insert_response( response, fbk_cache_id)

		graph_status_url = response['paging']['next']

		iteration = iteration + 1

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

def process_graph_likes():

	if( 'basedirname' in obj_config['graph'] ):
		basedirname = obj_config['graph']['basedirname']
	else:
		basedirname = "_fbk"

	fbk_cache()

# Main()
if __name__ == "__main__":

	# Process arguments
	parser = argparse.ArgumentParser(description='Scrape likes for content from Facebook\'s Graph API')

	parser.add_argument('-A', '--access-token',
			help='The access token to use for making Facebook Graph API requests.')

	parser.add_argument('-C', '--client-id', type=int,
			help='The Facebook application\'s client ID to use for making Facebook Graph API requests.')

	parser.add_argument('-f', '--config-file', metavar='CONFIG_FILE',
			help='A JSON-structured file containing configuration directives to use for the script')

	parser.add_argument('-v', '--verbosity', action="count",
			help="Increase output verbosity")

	parser.add_argument('--version', action='version', version='%(prog)s 1.0')

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

	process_graph_likes()

	sys.exit(0)
