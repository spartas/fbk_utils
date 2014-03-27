#!/usr/bin/env python3
#
# fbk_publish_3.py -- Uses the Facebook Graph API to grab and store posts locally. 
#
# 	Created by Timothy Wright <spartas@gmail.com>
#		Version 1.0 [March 4th, 2014]
#		* Has it really been over a year since I last updated? Facebook keeps changing their stylesheets and output
#			formats, which keeps me on my feet. No sooner than I can get a release out, they've gone and changed things
#			up again. Now, they've completely removed the post privacy, which makes the download utterly useless for
#			my purposes with fbk_sanitize.
#
#		Version 1.1 [March 26th, 2014]
#		* I've really been trying to keep the non-standard dependencies short on this one. Alas, I added the 
#			requirement that '''tzlocal''' be installed to support converting between timezones for the local user.
#			This is one of those cases where I can't really justify adding in the requirement, but I feel that it adds 
#			a good bit to the user experience that I'm leaving it in.
#
#		* Commented a few ambitiousities, and cleaned up some of the hard-coded strings that were specific to my use 
#			case.

import argparse
import os
from bs4 import BeautifulSoup, Tag
import sqlite3
import sys
import re
import json
from fbk_config import fbk_config
from datetime import datetime
from tzlocal import get_localzone

def write_outfile( contents, outfilepath, filename ):
	outfile = open(os.path.join(outfilepath, filename), 'w')
	outfile.write( contents )
	outfile.close()

def transform(o_post):
	ts = datetime.strptime(o_post[1], "%Y-%m-%dT%H:%M:%S%z")
		
	ts = ts.astimezone( local_tz )

	dy = ts.strftime("%e").strip()
	hr = ts.strftime("%l").strip()
	ap = ts.strftime("%p").lower()

	strts = ts.strftime("%A, %B " + dy + ", %Y at " + hr + ":%M" + ap + " %Z")
	sants = ts.strftime("%B " + dy + ", %Y at " + hr + ":%M " + ap )


	return {
		'message' 				: o_post[0],
		'created_timestamp'		: o_post[1],
		'privacy_description'	: o_post[2],
		'formatted_timestamp'	: strts,
		'sanitized_timestamp'	: sants,
	}

# This is called sanitize_publish for a reason. It will _ONLY_ operate properly on old-style Facebook export data
# formats, which were supported by fbk_sanitize. I hope that this method will go away completely in the future.
def sanitize_publish(fname):

	cxn = sqlite3.connect( os.path.join(config_dir, 'fbk_cache.db') )
	cur = cxn.cursor()

	f = open(fname, 'r')
	soup = BeautifulSoup( f.read() )
	f.close()

	# "merge_where" / "merge_compat_id"
	# This is a hackish shim to support old "Downloaded" file data directly from Facebook. This data used to be 
	# useful, and it was the primary method of operation for fbk_sanitize, however, recently Facebook changed their 
	# output format, crippling it in the process.
	# 
	# That said, if you have an old-style output format, as well as a recent dump of your Facebook data from Graph,
	# you can use this to "merge" the two. It's hackish, unsupported, and it doesn't work all that well either (well 
	# it doesn't work at all, except in a very small number of cases).
	#
	# The _right_ way to do this would be to compare timestamps in SQLite, however, SQLite doesn't support the 
	# timestamp format that Facebook provides. I _will_ rewrite this one day.
	merge_where = ""
	if obj_config['graph']['merge_compat_id']:
		merge_where += "AND `id` < %s" % (obj_config['graph']['merge_compat_id'])


	sql_fetch_query = """SELECT `message`,`created_timestamp`,`privacy_description` FROM `posts` WHERE `privacy_description`='Public' AND `type`='status' 
	%s ORDER BY `created_timestamp` DESC""" % (merge_where)
	
	cur.execute(sql_fetch_query)

	str_posts = ''
	for post in cur.fetchall():
		p = transform(post)
	
		str_posts = str_posts +  """<div class="feedentry hentry">
		         <span class="author vcard">
		          <span class="profile fn">
		           %s
		          </span>
		         </span>
		         <span class="entry-title entry-content">
		          %s
		         </span>
		         <div class="timerow">
		          <abbr class="time published" title="%s">
		           %s
		          </abbr>
		         </div>
		        </div>""" % (obj_config['name'], p['message'], p['created_timestamp'], p['sanitized_timestamp'])


	cxn.close()


	content_tag = soup.find(id='content') 
	if not content_tag:
		print("No suitable content ID found in the source document. Exiting.")
		sys.exit(7)

	posts = BeautifulSoup("<div>" + str_posts + "</div>").find('div').contents + content_tag.contents
	#posts = content_tag.contents
	#posts = BeautifulSoup("<div id='contents'>" + str_posts + "</div>").find('div').contents

	content_tag.contents = posts

	str_outfile_dt = datetime.now().strftime('%Y-%m-%d_%H_%M_%S')
	dest_path = "wall-%s.html" % str_outfile_dt
	write_outfile(soup.prettify(), '', dest_path)


def publish():
	cxn = sqlite3.connect( os.path.join(config_dir, 'fbk_cache.db') )
	cur = cxn.cursor()
	local_tz = get_localzone() 


	sql_fetch_query = """SELECT `message`,`created_timestamp`,`privacy_description` FROM `posts` WHERE `privacy_description`='Public' AND `type`='status' 
	ORDER BY `created_timestamp` DESC"""
	cur.execute(sql_fetch_query)


	soup = BeautifulSoup( """<html><head><title>Wall</title>
			<meta charset="utf-8">
			<link rel="stylesheet" href="style.css" type="text/css">
			</head>
			<body><table id="main"><thead /><tfoot /><tbody /></table></body></html>""")

	body = soup.find('body')

	h1 = soup.new_tag('h1')
	h1.string = obj_config['name']

	if obj_config['tagline']:
		

		span = soup.new_tag('span')
		span['id'] = "tagline"
		span.string = obj_config['tagline']

		h1.append(span)


	body.append(h1)

	main = BeautifulSoup( '<main /></body></html>' )
	body.append(main)
	mbody = main.find('main')

	for post in cur.fetchall():

		p = transform(post)

		post_div = soup.new_tag('div')
		name_span = soup.new_tag('span')
		name_span.string = obj_config['name']
		post_div.append(name_span)

		status_content = soup.new_tag('span')
		status_content.string = p['message']
		post_div.append(status_content)

		ts_div = soup.new_tag('div')
		ts_div.string = p['formatted_timestamp'] + " | " + p['privacy_description']
		post_div.append(ts_div)

		mbody.append(post_div)

	write_outfile( soup.prettify(), '.', 'wall-basic.html' )
	cxn.close()

	return

# Main()
if __name__ == "__main__":
	global local_tz

	# Process arguments
	parser = argparse.ArgumentParser(description='Publish content from _fetch to html pages')

	parser.add_argument('-f', '--config-file', metavar='CONFIG_FILE', 
			help='A JSON-structured file containing configuration directives to use for the script')

	parser.add_argument('-s', '--sanitize-publish', metavar='SANITIZE_PUBLISH',
			help="""Use the sanitize publish feature (an older HTML format) instead. 
			Specify the old wall.html with this feature""")

	parser.add_argument('--version', action='version', version='%(prog)s 1.0')

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

	if( args.sanitize_publish and not(os.path.exists(args.sanitize_publish)) ):
		print("File (%s) does not exist" % args.sanitize_publish)
		sys.exit(3)

	local_tz = get_localzone()


	if( args.sanitize_publish):
		sanitize_publish(args.sanitize_publish)
	else:
		publish()

	sys.exit(0)
